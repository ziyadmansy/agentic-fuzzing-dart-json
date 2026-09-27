from hypothesis import strategies as st

# Helper strategies for field values
id_strategy = st.integers(min_value=-2**31, max_value=2**31-1)

# For amount, try valid and boundary-adjacent strings, and some edge cases
amount_strategy = st.one_of(
    st.text(min_size=1, max_size=16),  # normal string
    st.just(""),                       # empty string
    st.just("0"),                      # looks like a number
    st.just("null"),                   # string "null"
    st.just("NaN"),                    # string "NaN"
    st.just("Infinity"),               # string "Infinity"
    st.just("-Infinity"),              # string "-Infinity"
    st.just("1e10"),                   # string that looks like a float
)

# For name, try string, null, and some edge cases
name_strategy = st.one_of(
    st.text(min_size=0, max_size=16),
    st.just(""),          # empty string
    st.just("null"),      # string "null"
    st.just(None),        # actual null
)

# For status, try valid values, and some off-spec ones
status_strategy = st.one_of(
    st.sampled_from(["active", "inactive", "unknown"]),
    st.just(""),          # empty string
    st.just("null"),      # string "null"
    st.just(None),        # actual null
    st.just("ACTIVE"),    # case variant
    st.just("Active"),    # case variant
    st.just("inactive "), # trailing space
)

# For tags, try normal arrays, empty, arrays with nulls, and wrong types
tags_strategy = st.one_of(
    st.lists(st.text(min_size=0, max_size=16), max_size=4),
    st.just([]),  # empty array
    st.lists(st.one_of(st.text(min_size=0, max_size=16), st.just(None)), min_size=1, max_size=4),  # with nulls
    st.just([None]),  # array of null
    st.just([""]),    # array with empty string
    st.just(["null"]),# array with string "null"
    st.just([1]),     # array with wrong type
    st.just([[]]),    # array with array
)

# For child, allow null or a recursive record (one level only)
@st.composite
def record_strategy(draw, allow_child=True):
    # Draw fields
    id_val = draw(id_strategy)
    amount_val = draw(amount_strategy)
    name_val = draw(name_strategy)
    status_val = draw(status_strategy)
    tags_val = draw(tags_strategy)
    if allow_child:
        # 50% chance of null, 50% chance of a nested record (with allow_child=False)
        child_val = draw(st.one_of(st.just(None), record_strategy(allow_child=False)))
    else:
        child_val = None

    # Build JSON string for this record
    def json_escape(s):
        # Minimal escaping for JSON strings
        return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

    def to_json(val):
        if val is None:
            return "null"
        elif isinstance(val, str):
            return json_escape(val)
        elif isinstance(val, bool):
            return "true" if val else "false"
        elif isinstance(val, int):
            return str(val)
        elif isinstance(val, list):
            return "[" + ",".join(to_json(x) for x in val) + "]"
        elif isinstance(val, dict):
            return "{" + ",".join(json_escape(k) + ":" + to_json(v) for k, v in val.items()) + "}"
        elif isinstance(val, bytes):
            return json_escape(val.decode("utf-8", errors="replace"))
        else:
            # Should not happen
            return "null"

    # Compose the record as a dict for easier JSON construction
    record = {
        "id": id_val,
        "amount": amount_val,
        "name": name_val,
        "status": status_val,
        "tags": tags_val,
        "child": child_val,
    }

    # Build JSON object string
    json_obj = (
        '{'
        + ','.join(
            json_escape(k) + ':' + to_json(v)
            for k, v in record.items()
        )
        + '}'
    )
    return json_obj.encode("utf-8")

@st.composite
def generated_json(draw) -> bytes:
    # Draw a single record as the top-level object
    return draw(record_strategy())