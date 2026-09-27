from hypothesis import strategies as st

# We produce syntactically valid JSON objects as bytes.
# We carefully vary one or two fields at a time around the known edge cases:
# - tags missing vs present (built_value accepts missing tags, others reject)
# - id as int vs double (manual and built_value require int, others accept double)
# - id as int64 out-of-range encoded as double (to trigger saturation differences)
# - nullable fields missing vs null vs present
# - status with valid vs invalid strings
# - child null vs present (one level recursion)
# We keep the JSON minimal and well-formed, only one or two fields off at a time.

# Helper: produce JSON string literal from a Python string (no escapes except \")
def json_string_literal(s: str) -> str:
    # Escape backslash and double quote minimally
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

# Helper: produce JSON array of strings
def json_array_of_strings(lst):
    # lst is list of strings
    return '[' + ','.join(json_string_literal(s) for s in lst) + ']'

# Helper: produce JSON object from dict of key->value strings (values are JSON text)
def json_object(d):
    # d: dict[str,str], values are JSON text (already serialized)
    items = []
    for k, v in d.items():
        items.append(json_string_literal(k) + ':' + v)
    return '{' + ','.join(items) + '}'

# Strategy for "status" field: valid or invalid strings
status_valid = st.sampled_from(["active", "inactive", "unknown"])
status_invalid = st.text(min_size=1).filter(lambda s: s not in {"active", "inactive", "unknown"})
status_field = st.one_of(
    status_valid.map(lambda s: (True, json_string_literal(s))),
    status_invalid.map(lambda s: (False, json_string_literal(s))),
)

# Strategy for "name" field: null, missing, or string
# But missing nullable fields are accepted by all four, so no divergence there.
# We'll vary null vs string only.
name_field = st.one_of(
    st.just((True, "null")),  # present null
    st.text(min_size=1).map(lambda s: (True, json_string_literal(s))),
    # missing handled by omitting key in object construction
)

# Strategy for "tags" field:
# Present as array of strings (possibly empty)
# Or missing (built_value accepts missing tags, others reject)
tags_present = st.lists(st.text(min_size=1), max_size=3).map(json_array_of_strings)
tags_field = st.one_of(
    tags_present.map(lambda arr: (True, arr)),
    st.just((False, None)),  # missing tags
)

# Strategy for "id" field:
# Manual and built_value require int (Dart int)
# json_serializable and freezed accept double and convert to int via toInt()
# jsonDecode turns integer literals outside 64-bit range into double
# toInt() saturates to int64 min/max instead of throwing
# So we produce:
# - int in 64-bit range (accepted by all)
# - int64 out-of-range encoded as double (accepted by json_serializable/freezed, rejected by manual/built_value)
# - double with fractional part (rejected by all)
# We'll produce JSON numbers as strings (no quotes)
# JSON numbers can be integer literals or floating point literals

# 64-bit signed int range
INT64_MIN = -2**63
INT64_MAX = 2**63 - 1

# Produce int64 in-range integer as JSON number string
int64_in_range = st.integers(min_value=INT64_MIN, max_value=INT64_MAX).map(str)

# Produce int64 out-of-range integer as double literal (JSON number with decimal point)
# We pick values just outside the 64-bit range, encoded as double
int64_out_of_range_double = st.one_of(
    st.integers(min_value=INT64_MAX + 1, max_value=INT64_MAX + 10),
    st.integers(min_value=INT64_MIN - 10, max_value=INT64_MIN - 1),
).map(lambda v: f"{float(v):.1f}")

# Produce double with fractional part (not integer)
double_fractional = st.floats(allow_infinity=False, allow_nan=False).filter(
    lambda f: abs(f) <= 1e10 and not f.is_integer()
).map(lambda f: f"{f:.6g}")

id_field = st.one_of(
    int64_in_range.map(lambda s: (True, s)),
    int64_out_of_range_double.map(lambda s: (False, s)),
    double_fractional.map(lambda s: (False, s)),
)

# Strategy for "amount" field: string, always present
# We'll keep it simple: decimal string, or empty string (valid string)
amount_field = st.text(min_size=1, max_size=10).map(json_string_literal)

# Strategy for "child" field: null, missing, or nested record (one level recursion)
# Missing nullable fields accepted by all four, so no divergence there.
# We'll produce either null or a nested record with no further recursion.
# To avoid infinite recursion, child record has child=null always.
# We'll reuse the top-level record strategy but with child=null forced.

# We'll define a helper to produce a record JSON text with child=null (no recursion)
@st.composite
def record_no_child(draw):
    # id
    id_ok, id_val = draw(id_field)
    # amount
    amount_val = draw(amount_field)
    # name
    name_ok, name_val = draw(name_field)
    # status
    status_ok, status_val = draw(status_field)
    # tags
    tags_ok, tags_val = draw(tags_field)
    # child null
    child_val = "null"
    # Build dict with keys present or missing for nullable fields
    d = {
        "id": id_val,
        "amount": amount_val,
        "status": status_val,
    }
    if name_ok:
        d["name"] = name_val
    # tags: present or missing
    if tags_ok:
        d["tags"] = tags_val
    d["child"] = child_val
    return json_object(d)

# Now child field strategy: null or nested record_no_child
child_field = st.one_of(
    st.just((True, "null")),
    record_no_child().map(lambda s: (True, s)),
    # missing child handled by omitting key
)

@st.composite
def generated_json(draw) -> bytes:
    # We produce a top-level record JSON object as bytes

    # id field
    id_ok, id_val = draw(id_field)
    # amount field
    amount_val = draw(amount_field)
    # name field: present null or string, or missing (nullable)
    name_choice = draw(st.integers(min_value=0, max_value=2))
    if name_choice == 0:
        name_ok, name_val = True, "null"
    elif name_choice == 1:
        name_ok, name_val = True, draw(st.text(min_size=1).map(json_string_literal))
    else:
        name_ok, name_val = False, None  # missing

    # status field: valid or invalid string
    status_ok, status_val = draw(status_field)

    # tags field: present or missing
    tags_ok, tags_val = draw(tags_field)

    # child field: present null, present nested record, or missing
    child_choice = draw(st.integers(min_value=0, max_value=2))
    if child_choice == 0:
        child_ok, child_val = True, "null"
    elif child_choice == 1:
        child_ok, child_val = True, draw(record_no_child())
    else:
        child_ok, child_val = False, None  # missing

    # Build dict with keys present or missing for nullable fields
    d = {
        "id": id_val,
        "amount": amount_val,
        "status": status_val,
    }
    if name_ok:
        d["name"] = name_val
    if tags_ok:
        d["tags"] = tags_val
    if child_ok:
        d["child"] = child_val

    # Compose JSON object string
    json_text = json_object(d)

    # Return as bytes
    return json_text.encode("utf-8")