from hypothesis import strategies as st

# Helper strategies for fields
id_strategy = st.integers(-2**31, 2**31 - 1)

# "amount" is a string, but try edge cases: numbers, empty, weird unicode, leading zeros, etc.
amount_strategy = st.one_of(
    st.text(min_size=0, max_size=32),  # normal/empty/long strings
    st.integers(-999999999, 999999999).map(str),  # numeric-looking strings
    st.just("000123.45"),  # leading zeros
    st.just("NaN"),        # special float string
    st.just("Infinity"),
    st.just("-Infinity"),
    st.just(" "),          # whitespace
    st.just("\u2028\u2029"),  # line/paragraph separators
)

# "name" is string or null, but try edge cases: empty, long, numbers as string, etc.
name_strategy = st.one_of(
    st.none(),
    st.text(min_size=0, max_size=32),
    st.just("null"),  # string "null"
    st.just("123"),   # string number
    st.just(""),      # empty string
)

# "status" is one of three strings, but try case, extra whitespace, or wrong type
status_strategy = st.one_of(
    st.sampled_from(["active", "inactive", "unknown"]),
    st.sampled_from(["Active", "INACTIVE", "UNKNOWN"]),  # case variants
    st.just(" active "),  # whitespace
    st.just(""),          # empty string
    st.integers(-1, 2).map(str),  # numeric as string
    st.integers(-1, 2),           # wrong type: int
    st.just("null"),              # string "null"
)

# "tags" is array of strings, but try empty, nulls, non-string, duplicates, etc.
tags_strategy = st.one_of(
    st.lists(st.text(min_size=0, max_size=16), max_size=5),
    st.just([]),
    st.lists(st.sampled_from(["", "tag", "null", "123", ""]), min_size=1, max_size=5),
    st.lists(st.integers(0, 10).map(str), min_size=1, max_size=3),  # numeric strings
    st.lists(st.integers(0, 10), min_size=1, max_size=3),           # wrong type: int
    st.lists(st.none(), min_size=1, max_size=2),                    # wrong type: null
)

# Recursion for "child"
@st.composite
def record_strategy(draw, depth=0):
    # Only allow one level of recursion
    child = None
    if depth < 1:
        child = draw(st.one_of(
            st.none(),
            record_strategy(depth=1)
        ))
    else:
        child = None

    # Compose the record as a dict
    record = {
        "id": draw(id_strategy),
        "amount": draw(amount_strategy),
        "name": draw(name_strategy),
        "status": draw(status_strategy),
        "tags": draw(tags_strategy),
        "child": child,
    }
    return record

# Helper to encode Python objects to JSON (limited, no import)
def py_to_json(val):
    if val is None:
        return "null"
    elif isinstance(val, bool):
        return "true" if val else "false"
    elif isinstance(val, int):
        return str(val)
    elif isinstance(val, str):
        # Escape backslash and double quote, and control chars
        s = val.replace('\\', '\\\\').replace('"', '\\"')
        s = ''.join(
            c if 0x20 <= ord(c) <= 0x10FFFF and c not in '\b\f\n\r\t'
            else '\\u%04x' % ord(c)
            for c in s
        )
        return '"' + s + '"'
    elif isinstance(val, list):
        return "[" + ",".join(py_to_json(x) for x in val) + "]"
    elif isinstance(val, dict):
        return "{" + ",".join(
            py_to_json(str(k)) + ":" + py_to_json(v) for k, v in val.items()
        ) + "}"
    else:
        # Should not happen
        return "null"

@st.composite
def generated_json(draw):
    record = draw(record_strategy())
    json_str = py_to_json(record)
    return json_str.encode("utf-8")