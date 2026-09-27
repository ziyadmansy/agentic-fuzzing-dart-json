from hypothesis import strategies as st

# Helper strategies for each field
id_strategy = st.integers(min_value=-(2**31), max_value=2**31-1)

# amount: usually a string, but try edge cases (e.g. numbers, null, empty string)
amount_strategy = st.one_of(
    st.text(min_size=0, max_size=20),  # normal string
    st.just(""),                      # empty string
    st.integers().map(str),           # integer as string
    st.floats(allow_nan=False, allow_infinity=False).map(lambda f: str(f)),  # float as string
    st.just(None),                    # null (should be rejected, but some may accept)
    st.integers(),                    # raw integer (wrong type)
    st.floats(allow_nan=False, allow_infinity=False),  # raw float (wrong type)
)

# name: string or null, but try numbers, empty string, missing, etc.
name_strategy = st.one_of(
    st.text(min_size=0, max_size=20),
    st.just(None),
    st.integers(),
    st.floats(allow_nan=False, allow_infinity=False),
)

# status: valid enum, but try wrong-case, extra, null, number, etc.
status_strategy = st.one_of(
    st.sampled_from(["active", "inactive", "unknown"]),
    st.text(min_size=0, max_size=10).filter(lambda s: s not in {"active", "inactive", "unknown"}),
    st.just(None),
    st.integers(),
)

# tags: array of strings, but try mixed types, empty, null, missing, etc.
tags_strategy = st.one_of(
    st.lists(st.text(min_size=0, max_size=10), min_size=0, max_size=4),
    st.lists(st.integers(), min_size=1, max_size=3),  # wrong type in array
    st.just([]),
    st.just(None),
    st.lists(
        st.one_of(st.text(min_size=0, max_size=10), st.integers(), st.just(None)),
        min_size=1, max_size=3
    ),
)

# Recursion for child
@st.composite
def record_strategy(draw, depth=0):
    # Limit recursion depth to 1 (child is either null or a record with child=null)
    child = None
    if depth < 1:
        child = draw(st.one_of(st.just(None), record_strategy(depth=1)))
    else:
        child = None

    # Build each field
    id_val = draw(id_strategy)
    amount_val = draw(amount_strategy)
    name_val = draw(name_strategy)
    status_val = draw(status_strategy)
    tags_val = draw(tags_strategy)

    # JSON encoding helpers
    def encode_json(val):
        if val is None:
            return "null"
        elif isinstance(val, str):
            # Escape backslashes and quotes
            return '"' + val.replace('\\', '\\\\').replace('"', '\\"') + '"'
        elif isinstance(val, bool):
            return "true" if val else "false"
        elif isinstance(val, (int, float)):
            return str(val)
        elif isinstance(val, list):
            return "[" + ",".join(encode_json(x) for x in val) + "]"
        elif isinstance(val, dict):
            return "{" + ",".join(f"{encode_json(k)}:{encode_json(v)}" for k, v in val.items()) + "}"
        else:
            # Should not happen
            return "null"

    # Compose the record as a dict
    record = {
        "id": id_val,
        "amount": amount_val,
        "name": name_val,
        "status": status_val,
        "tags": tags_val,
        "child": child,
    }
    return record

# Compose the JSON as bytes
@st.composite
def generated_json(draw):
    record = draw(record_strategy())
    # JSON encoding helpers (repeat here for scope)
    def encode_json(val):
        if val is None:
            return "null"
        elif isinstance(val, str):
            return '"' + val.replace('\\', '\\\\').replace('"', '\\"') + '"'
        elif isinstance(val, bool):
            return "true" if val else "false"
        elif isinstance(val, (int, float)):
            return str(val)
        elif isinstance(val, list):
            return "[" + ",".join(encode_json(x) for x in val) + "]"
        elif isinstance(val, dict):
            return "{" + ",".join(f"{encode_json(k)}:{encode_json(v)}" for k, v in val.items()) + "}"
        else:
            return "null"
    json_str = encode_json(record)
    return json_str.encode("utf-8")