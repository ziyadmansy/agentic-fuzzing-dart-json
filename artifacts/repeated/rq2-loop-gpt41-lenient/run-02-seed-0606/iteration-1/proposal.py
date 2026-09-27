from hypothesis import strategies as st

# Helper strategies for field values
status_values = st.sampled_from(["active", "inactive", "unknown"])

# For "amount", try valid and boundary cases (e.g., numbers as strings, empty, weird float formats)
amount_strings = st.one_of(
    st.just("0"),
    st.just("0.0"),
    st.just("-0"),
    st.just("1e10"),
    st.just("-1e-10"),
    st.just("NaN"),
    st.just("Infinity"),
    st.just("-Infinity"),
    st.text(min_size=0, max_size=8),  # random short string, could be invalid number
)

# For "name", try string and null, and edge cases (empty string, whitespace, unicode)
name_values = st.one_of(
    st.none(),
    st.just(""),
    st.just(" "),
    st.just("\u2028"),  # line separator
    st.text(min_size=1, max_size=8),
)

# For "tags", try empty, single, multiple, and weird strings
tag_strings = st.one_of(
    st.just(""),
    st.just(" "),
    st.text(min_size=1, max_size=8),
)
tags_values = st.one_of(
    st.lists(tag_strings, min_size=0, max_size=3),
    st.just([]),
    st.just([""]),
    st.just(["", ""]),
)

# For "id", try valid and boundary integer values, and some floats-as-integers
id_values = st.one_of(
    st.integers(min_value=-1, max_value=2**31),
    st.just(0),
    st.just(-1),
    st.just(1),
    st.just(2**31 - 1),
    st.just(-2147483648),
)

# For "child", allow null or a recursive record, but limit recursion depth
def record_strategy(max_depth):
    @st.composite
    def _record(draw):
        # At max depth, force child to null
        child_val = None if max_depth <= 0 else draw(
            st.one_of(
                st.none(),
                record_strategy(max_depth - 1)
            )
        )

        # Vary one or two fields at a time for divergence
        # Randomly pick a field to "perturb" in this record
        perturb_field = draw(st.sampled_from([
            "id", "amount", "name", "status", "tags", "child", None
        ]))

        # Default values (well-formed)
        id_val = draw(id_values)
        amount_val = draw(amount_strings)
        name_val = draw(name_values)
        status_val = draw(status_values)
        tags_val = draw(tags_values)

        # Apply perturbation: for the chosen field, use a "wrong" type or boundary value
        if perturb_field == "id":
            # Use a float, string, or null instead of int
            id_val = draw(st.one_of(
                st.floats(allow_nan=True, allow_infinity=True),
                st.text(min_size=0, max_size=6),
                st.none(),
            ))
        elif perturb_field == "amount":
            # Use a number, null, or array instead of string
            amount_val = draw(st.one_of(
                st.integers(),
                st.floats(allow_nan=True, allow_infinity=True),
                st.none(),
                st.lists(st.text(), min_size=0, max_size=2),
            ))
        elif perturb_field == "name":
            # Use a number, array, or object instead of string/null
            name_val = draw(st.one_of(
                st.integers(),
                st.lists(st.text(), min_size=0, max_size=2),
                st.dictionaries(st.text(min_size=1, max_size=3), st.integers(), min_size=0, max_size=2),
            ))
        elif perturb_field == "status":
            # Use a string not in allowed set, or a number/null/array
            status_val = draw(st.one_of(
                st.just(""),
                st.just("deleted"),
                st.text(min_size=1, max_size=8).filter(lambda s: s not in ["active", "inactive", "unknown"]),
                st.integers(),
                st.none(),
                st.lists(st.text(), min_size=0, max_size=2),
            ))
        elif perturb_field == "tags":
            # Use a string, null, or object instead of array
            tags_val = draw(st.one_of(
                st.text(min_size=0, max_size=8),
                st.none(),
                st.dictionaries(st.text(min_size=1, max_size=3), st.integers(), min_size=0, max_size=2),
            ))
        elif perturb_field == "child":
            # Use a number, string, or array instead of object/null
            child_val = draw(st.one_of(
                st.integers(),
                st.text(min_size=0, max_size=8),
                st.lists(st.integers(), min_size=0, max_size=2),
            ))

        # JSON encoding for each field
        def json_val(val):
            if val is None:
                return "null"
            elif isinstance(val, str):
                # Escape backslashes and quotes
                return '"' + val.replace('\\', '\\\\').replace('"', '\\"') + '"'
            elif isinstance(val, bool):
                return "true" if val else "false"
            elif isinstance(val, (int, float)):
                # Use repr to preserve NaN/Infinity
                return repr(val)
            elif isinstance(val, list):
                return "[" + ",".join(json_val(x) for x in val) + "]"
            elif isinstance(val, dict):
                return "{" + ",".join(
                    json_val(str(k)) + ":" + json_val(v) for k, v in val.items()
                ) + "}"
            else:
                # Fallback: treat as string
                return '"' + str(val).replace('\\', '\\\\').replace('"', '\\"') + '"'

        # Compose the record as a JSON object
        json_obj = (
            "{"
            f"\"id\":{json_val(id_val)},"
            f"\"amount\":{json_val(amount_val)},"
            f"\"name\":{json_val(name_val)},"
            f"\"status\":{json_val(status_val)},"
            f"\"tags\":{json_val(tags_val)},"
            f"\"child\":{json_val(child_val)}"
            "}"
        )
        return json_obj

    return _record()

@st.composite
def generated_json(draw):
    # Limit recursion depth to 1 or 2 for "child"
    json_str = draw(record_strategy(max_depth=1))
    # Return as bytes
    return json_str.encode("utf-8")