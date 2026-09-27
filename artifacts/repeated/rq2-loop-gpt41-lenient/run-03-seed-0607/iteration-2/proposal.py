from hypothesis import strategies as st

# Helper strategies for each field, including edge cases and near-misses.
id_field = st.one_of(
    st.integers(min_value=-2**31, max_value=2**31-1),  # valid int
    st.floats(allow_nan=False, allow_infinity=False).filter(lambda f: f != int(f)),  # float, not int
    st.text(),  # string instead of int
    st.none(),  # null instead of int
)

amount_field = st.one_of(
    st.text(),  # valid string
    st.integers(),  # int instead of string
    st.floats(allow_nan=False, allow_infinity=False),  # float instead of string
    st.none(),  # null instead of string
    st.lists(st.text()),  # array instead of string
)

name_field = st.one_of(
    st.text(),  # valid string
    st.none(),  # null
    st.integers(),  # int instead of string/null
    st.lists(st.text()),  # array instead of string/null
)

status_field = st.one_of(
    st.sampled_from(["active", "inactive", "unknown"]),  # valid
    st.text().filter(lambda s: s not in {"active", "inactive", "unknown"}),  # invalid string
    st.integers(),  # int instead of string
    st.none(),  # null instead of string
)

tags_field = st.one_of(
    st.lists(st.text(), max_size=4),  # valid
    st.lists(st.integers(), min_size=1, max_size=3),  # ints instead of strings
    st.text(),  # string instead of array
    st.none(),  # null instead of array
    st.lists(st.none(), min_size=1, max_size=2),  # array of nulls
)

# Bounded recursion for "child"
@st.composite
def child_field(draw, depth=0):
    if depth > 0 and draw(st.booleans()):
        return "null"
    else:
        # 70% chance of null, 30% chance of object (if depth==0)
        if draw(st.integers(min_value=0, max_value=9)) < 7:
            return "null"
        else:
            # Recursively build a child object, but only one level deep
            child_json = draw(record_json(depth=1))
            return child_json

# Compose the record as a JSON object string
@st.composite
def record_json(draw, depth=0):
    id_val = draw(id_field)
    amount_val = draw(amount_field)
    name_val = draw(name_field)
    status_val = draw(status_field)
    tags_val = draw(tags_field)
    child_val = draw(child_field(depth=depth))

    def to_json(val):
        if isinstance(val, str):
            # Already a JSON string or object
            if val == "null" or val.startswith("{"):
                return val
            else:
                # Properly escape string
                return '"' + val.replace('\\', '\\\\').replace('"', '\\"') + '"'
        elif val is None:
            return "null"
        elif isinstance(val, bool):
            return "true" if val else "false"
        elif isinstance(val, int) or isinstance(val, float):
            return str(val)
        elif isinstance(val, list):
            return "[" + ",".join(to_json(x) for x in val) + "]"
        else:
            # Should not happen
            return "null"

    json_obj = (
        "{"
        f"\"id\":{to_json(id_val)},"
        f"\"amount\":{to_json(amount_val)},"
        f"\"name\":{to_json(name_val)},"
        f"\"status\":{to_json(status_val)},"
        f"\"tags\":{to_json(tags_val)},"
        f"\"child\":{child_val}"
        "}"
    )
    return json_obj

@st.composite
def generated_json(draw):
    # Top-level record, always as bytes
    json_str = draw(record_json())
    return json_str.encode("utf-8")