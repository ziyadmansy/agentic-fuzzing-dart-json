from hypothesis import strategies as st

# We produce JSON text for a Record with the given schema:
# {
#   "id": <integer>,
#   "amount": <string>,
#   "name": <string or null>,
#   "status": <"active"|"inactive"|"unknown">,
#   "tags": <array of strings>,
#   "child": <Record or null>
# }
#
# We produce syntactically valid JSON text only.
# We vary presence/absence of "tags" (to trigger built_value acceptance vs others rejecting).
# We vary "id" as int or double (to trigger manual/built_value vs json_serializable/freezed divergence).
# We vary null vs string for "name" and "child".
# We vary "status" with only valid strings (no unknown).
# We vary "amount" as string always.
# We produce bounded recursion for "child" (max depth 1).
#
# We produce a single JSON object text as bytes.

# Helpers to produce JSON text for values:

def json_string(s: str) -> str:
    # Escape backslash and double quote minimally for JSON string
    # Also escape control chars \b \f \n \r \t minimally
    # Hypothesis strings are unicode, but we keep it simple and safe with ascii subset
    # We produce only ascii printable chars except backslash and double quote escaped.
    esc = s.replace('\\', '\\\\').replace('"', '\\"').replace('\b', '\\b').replace('\f', '\\f').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
    return '"' + esc + '"'

def json_null() -> str:
    return "null"

def json_bool(b: bool) -> str:
    return "true" if b else "false"

def json_int(n: int) -> str:
    return str(n)

def json_float(f: float) -> str:
    # Use repr to get shortest decimal form
    # But repr(1.0) -> '1.0' which is valid JSON number
    # We avoid scientific notation for simplicity
    s = repr(f)
    # If scientific notation, convert to decimal notation with format
    if 'e' in s or 'E' in s:
        s = format(f, 'f').rstrip('0').rstrip('.')
        if s == '':
            s = '0'
    return s

def json_array(items: list[str]) -> str:
    return "[" + ",".join(items) + "]"

def json_object(pairs: list[tuple[str, str]]) -> str:
    # pairs: list of (key, value) strings, keys must be JSON strings
    # keys are always ASCII simple strings, so we can json_string them
    items = []
    for k, v in pairs:
        items.append(json_string(k) + ":" + v)
    return "{" + ",".join(items) + "}"

# Strategy for "status" field: one of three strings
status_strat = st.sampled_from(["active", "inactive", "unknown"]).map(json_string)

# Strategy for "amount": always a string, nonempty ascii printable
amount_strat = st.text(min_size=1, max_size=10).map(json_string)

# Strategy for "name": string or null
name_strat = st.one_of(st.none(), st.text(min_size=0, max_size=10)).map(
    lambda v: json_null() if v is None else json_string(v)
)

# Strategy for "tags": array of strings (strings nonempty ascii printable)
tags_strat = st.lists(st.text(min_size=1, max_size=10), max_size=5).map(
    lambda lst: json_array([json_string(s) for s in lst])
)

# Strategy for "id": either int or double (to trigger divergence)
# We pick int in 64-bit signed range, or double that is integer-valued or not
# We produce a tuple (is_double, number) to distinguish
def id_strategy():
    # int64 range
    int64_min = -(2**63)
    int64_max = 2**63 - 1
    # We produce either:
    # - int in int64 range
    # - double outside int64 range (to cause jsonDecode to produce double)
    # - double inside int64 range but fractional (to cause manual/built_value reject)
    # We produce a union of these cases
    int_case = st.integers(min_value=int64_min, max_value=int64_max).map(lambda i: ("int", i))
    # double fractional inside int64 range
    double_frac_case = st.floats(min_value=float(int64_min), max_value=float(int64_max), allow_infinity=False, allow_nan=False).filter(lambda f: not f.is_integer()).map(lambda f: ("double", f))
    # double integer-valued outside int64 range (to cause saturation in toInt)
    double_outside_case = st.one_of(
        st.floats(min_value=float(int64_max)+1, max_value=1e20, allow_infinity=False, allow_nan=False),
        st.floats(min_value=-1e20, max_value=float(int64_min)-1, allow_infinity=False, allow_nan=False)
    ).filter(lambda f: f.is_integer()).map(lambda f: ("double", f))
    return st.one_of(int_case, double_frac_case, double_outside_case)

# Strategy for "child": either null or a Record (one level recursion)
# We limit recursion depth to 1 by passing a parameter
def record_strategy(depth: int) -> st.SearchStrategy[str]:
    # If depth == 0, child is always null
    if depth <= 0:
        child_strat = st.just(json_null())
    else:
        # child is either null or a record with depth-1
        child_strat = st.one_of(st.just(json_null()), record_strategy(depth - 1))
    # We produce fields:
    # "id": from id_strategy
    # "amount": amount_strat
    # "name": name_strat
    # "status": status_strat
    # "tags": either present or missing (to trigger built_value divergence)
    # We produce a boolean to decide presence of "tags"
    tags_presence = st.booleans()
    # Compose all fields except tags first
    base_fields = st.tuples(
        id_strategy(),
        amount_strat,
        name_strat,
        status_strat,
        child_strat,
        tags_presence
    )
    def build_record(t):
        (id_val, amount_val, name_val, status_val, child_val, tags_present) = t
        # id_val is ("int" or "double", number)
        id_type, id_num = id_val
        if id_type == "int":
            id_json = json_int(id_num)
        else:
            # double
            id_json = json_float(id_num)
        # tags: if present, produce tags array, else omit field
        if tags_present:
            # produce tags array with 0 to 3 strings
            # We produce a small tags array here to keep size small
            # We reuse tags_strat but limit max_size=3
            tags_arr = st.lists(st.text(min_size=1, max_size=5), max_size=3).map(
                lambda lst: json_array([json_string(s) for s in lst])
            ).example()
            # We must not use .example() in strategy, so instead we inline tags generation here
            # So we must rewrite build_record to be a flatmap
            # To fix this, we move tags array generation out of build_record
            # So instead, we produce tags array as a separate strategy and pass it in
            # We'll fix this below
            pass
        else:
            tags_arr = None
        # Compose pairs
        pairs = [
            ("id", id_json),
            ("amount", amount_val),
            ("name", name_val),
            ("status", status_val),
            ("child", child_val)
        ]
        if tags_present:
            pairs.append(("tags", tags_arr))
        return json_object(pairs)

    # Because we need tags array to be generated as a strategy, we rewrite:
    # We produce tags array strategy here:
    tags_arr_strat = st.lists(st.text(min_size=1, max_size=5), max_size=3).map(
        lambda lst: json_array([json_string(s) for s in lst])
    )
    # Now we flatmap base_fields and tags_arr_strat to build record
    return base_fields.flatmap(
        lambda t: tags_arr_strat.map(
            lambda tags_arr: build_record_with_tags(t, tags_arr)
        )
    )

def build_record_with_tags(t, tags_arr):
    (id_val, amount_val, name_val, status_val, child_val, tags_present) = t
    id_type, id_num = id_val
    if id_type == "int":
        id_json = json_int(id_num)
    else:
        id_json = json_float(id_num)
    pairs = [
        ("id", id_json),
        ("amount", amount_val),
        ("name", name_val),
        ("status", status_val),
        ("child", child_val)
    ]
    if tags_present:
        pairs.append(("tags", tags_arr))
    # else omit tags field
    return json_object(pairs)

@st.composite
def generated_json(draw) -> bytes:
    # Produce a record with depth=1 recursion max
    # This means child is either null or a record with child=null
    # We produce the JSON text as str, then encode utf-8 bytes
    # We use record_strategy(1)
    # record_strategy returns str JSON text
    # We draw one record
    rec = draw(record_strategy(1))
    return rec.encode("utf-8")