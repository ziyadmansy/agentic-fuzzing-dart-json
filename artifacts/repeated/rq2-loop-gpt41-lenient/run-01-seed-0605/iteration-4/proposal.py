from hypothesis import strategies as st

# Helper strategies for field values
status_values = st.sampled_from(["active", "inactive", "unknown"])

# Some "almost right" values for each field, to provoke divergence
id_variants = st.one_of(
    st.integers(min_value=-(2**31), max_value=2**31-1),  # normal int
    st.floats(allow_nan=False, allow_infinity=False).filter(lambda f: f.is_integer()).map(lambda f: str(int(f))),  # int as string
    st.text(min_size=1, max_size=10),  # string instead of int
)

amount_variants = st.one_of(
    st.text(min_size=0, max_size=20),  # normal string
    st.integers(min_value=-(2**31), max_value=2**31-1).map(str),  # int as string
    st.integers(min_value=-(2**31), max_value=2**31-1),  # int instead of string
    st.none(),  # null instead of string
)

name_variants = st.one_of(
    st.text(min_size=0, max_size=20),  # normal string
    st.none(),  # null
    st.integers(min_value=-(2**31), max_value=2**31-1),  # int instead of string/null
    st.booleans(),  # bool instead of string/null
)

status_variants = st.one_of(
    status_values,  # valid
    st.text(min_size=0, max_size=10).filter(lambda s: s not in {"active", "inactive", "unknown"}),  # invalid string
    st.integers(min_value=0, max_value=10),  # int instead of string
    st.none(),  # null instead of string
)

tags_variants = st.one_of(
    st.lists(st.text(min_size=0, max_size=10), max_size=5),  # normal
    st.lists(st.integers(min_value=0, max_value=100), max_size=5),  # ints instead of strings
    st.text(min_size=0, max_size=20),  # string instead of list
    st.none(),  # null instead of list
)

# Recursion for 'child' field, with bounded depth
def record_strategy(max_depth):
    if max_depth == 0:
        child = st.just("null")
    else:
        # 60% chance of null, 40% chance of another record
        child = st.one_of(
            st.just("null"),
            st.deferred(lambda: record_strategy(max_depth - 1))
        )
    # For each field, 80% chance of "normal" value, 20% chance of "almost right" value
    id_field = st.one_of(
        st.integers(min_value=-(2**31), max_value=2**31-1).map(str),  # normal int as JSON number
        id_variants
    )
    amount_field = st.one_of(
        st.text(min_size=0, max_size=20),  # normal string
        amount_variants
    )
    name_field = st.one_of(
        st.text(min_size=0, max_size=20),
        name_variants
    )
    status_field = st.one_of(
        status_values,
        status_variants
    )
    tags_field = st.one_of(
        st.lists(st.text(min_size=0, max_size=10), max_size=5),
        tags_variants
    )

    # Compose the record as a JSON object string
    @st.composite
    def record(draw):
        id_val = draw(id_field)
        amount_val = draw(amount_field)
        name_val = draw(name_field)
        status_val = draw(status_field)
        tags_val = draw(tags_field)
        child_val = draw(child)

        def json_value(val):
            if isinstance(val, str):
                # If already a JSON literal (e.g., "null" or a nested object), don't double quote
                if val == "null" or val.startswith("{"):
                    return val
                else:
                    return '"' + val.replace('\\', '\\\\').replace('"', '\\"') + '"'
            elif val is None:
                return "null"
            elif isinstance(val, bool):
                return "true" if val else "false"
            elif isinstance(val, int):
                return str(val)
            elif isinstance(val, float):
                return str(val)
            elif isinstance(val, list):
                return "[" + ",".join(json_value(x) for x in val) + "]"
            else:
                # Fallback: try str
                return '"' + str(val).replace('\\', '\\\\').replace('"', '\\"') + '"'

        # Compose JSON object
        json_obj = (
            "{"
            f"\"id\":{json_value(id_val)},"
            f"\"amount\":{json_value(amount_val)},"
            f"\"name\":{json_value(name_val)},"
            f"\"status\":{json_value(status_val)},"
            f"\"tags\":{json_value(tags_val)},"
            f"\"child\":{child_val}"
            "}"
        )
        return json_obj

    return record()

@st.composite
def generated_json(draw) -> bytes:
    # Limit recursion to 1 or 2 levels
    max_depth = draw(st.integers(min_value=0, max_value=1))
    json_str = draw(record_strategy(max_depth))
    return json_str.encode("utf-8")