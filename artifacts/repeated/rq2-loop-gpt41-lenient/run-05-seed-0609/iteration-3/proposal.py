from hypothesis import strategies as st

# Helper strategies for field values
status_values = st.sampled_from(['active', 'inactive', 'unknown'])

# Some "almost correct" values for each field, to probe type boundaries and nullability
id_values = st.one_of(
    st.integers(min_value=-2**31, max_value=2**31-1),  # valid
    st.text(min_size=1, max_size=8),                   # wrong type: string instead of int
    st.floats(allow_nan=False, allow_infinity=False).filter(lambda f: not f.is_integer()),  # float instead of int
)

amount_values = st.one_of(
    st.text(min_size=0, max_size=12),                  # valid
    st.integers(min_value=-999999, max_value=999999).map(str),  # int as string (valid)
    st.none(),                                         # null instead of string
    st.booleans().map(lambda b: "true" if b else "false"),  # "true"/"false" as string
)

name_values = st.one_of(
    st.text(min_size=0, max_size=10),                  # valid
    st.none(),                                         # valid
    st.integers(min_value=-100, max_value=100),        # wrong type: int
    st.booleans(),                                     # wrong type: bool
)

status_field_values = st.one_of(
    status_values,                                     # valid
    st.text(min_size=0, max_size=8).filter(lambda s: s not in {'active', 'inactive', 'unknown'}),  # wrong value
    st.integers(min_value=0, max_value=10),            # wrong type: int
    st.none(),                                         # null instead of string
)

tags_values = st.one_of(
    st.lists(st.text(min_size=0, max_size=8), max_size=4),  # valid
    st.lists(st.integers(min_value=0, max_value=100), min_size=1, max_size=3),  # wrong type: ints
    st.none(),                                              # null instead of array
    st.text(min_size=0, max_size=10),                       # wrong type: string
)

# For child, we want to sometimes recurse, sometimes use null, sometimes wrong type
def child_strategy(recursion):
    return st.one_of(
        st.none(),  # valid
        st.deferred(lambda: record_strategy(recursion - 1)) if recursion > 0 else st.none(),
        st.text(min_size=0, max_size=10),  # wrong type: string
        st.integers(min_value=0, max_value=100),  # wrong type: int
        st.lists(st.text(min_size=0, max_size=8), max_size=2),  # wrong type: array
    )

# Compose the record as a dict of field: value
def record_strategy(recursion):
    # For divergence, sometimes omit a field (simulate missing field)
    # But only one at a time, and not always.
    fields = ['id', 'amount', 'name', 'status', 'tags', 'child']
    # Choose 0 or 1 field to omit (simulate missing field)
    omit_field = st.none() | st.sampled_from(fields)
    @st.composite
    def _record(draw):
        omit = draw(omit_field)
        record = {}
        if omit != 'id':
            record['id'] = draw(id_values)
        if omit != 'amount':
            record['amount'] = draw(amount_values)
        if omit != 'name':
            record['name'] = draw(name_values)
        if omit != 'status':
            record['status'] = draw(status_field_values)
        if omit != 'tags':
            record['tags'] = draw(tags_values)
        if omit != 'child':
            record['child'] = draw(child_strategy(recursion))
        return record
    return _record()

# JSON encoding helpers (no json.dumps allowed)
def json_escape_string(s):
    # Escape backslash and double quote, and control chars
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"').replace('\b', '\\b').replace('\f', '\\f').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t') + '"'

def encode_json_value(val):
    if val is None:
        return 'null'
    elif isinstance(val, bool):
        return 'true' if val else 'false'
    elif isinstance(val, int):
        return str(val)
    elif isinstance(val, float):
        # Use JSON float formatting
        return repr(val)
    elif isinstance(val, str):
        return json_escape_string(val)
    elif isinstance(val, list):
        return '[' + ','.join(encode_json_value(v) for v in val) + ']'
    elif isinstance(val, dict):
        return '{' + ','.join(
            json_escape_string(str(k)) + ':' + encode_json_value(v)
            for k, v in val.items()
        ) + '}'
    else:
        # Should not happen, but fallback
        return 'null'

@st.composite
def generated_json(draw) -> bytes:
    # Limit recursion to 1 level for child
    record = draw(record_strategy(recursion=1))
    json_str = encode_json_value(record)
    return json_str.encode('utf-8')