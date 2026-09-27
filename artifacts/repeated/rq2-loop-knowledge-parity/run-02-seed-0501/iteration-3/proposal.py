from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status field
    status_values = ["active", "inactive", "unknown"]

    # Helper to produce a JSON string literal with proper escaping of quotes and backslashes
    def json_string_literal(s: str) -> str:
        # Escape backslash and double quotes for JSON string
        esc = s.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{esc}"'

    # Helper to produce JSON array of strings
    def json_array_of_strings(lst):
        # lst is list of strings
        return "[" + ",".join(json_string_literal(x) for x in lst) + "]"

    # Recursive strategy for the "child" field, bounded to one level of recursion
    # We produce a JSON object string or "null"
    # To avoid infinite recursion, child.child is always null
    def record_json(level=0):
        # id: integer or double (to exploit id decoding difference)
        # We produce either an int or a float that represents an integer (e.g. 1.0)
        # or a float outside int64 range to test saturation behavior
        # We'll produce int64 range values and some out-of-range doubles
        # int64 range: -2**63 to 2**63-1
        int64_min = -(2**63)
        int64_max = 2**63 - 1

        # id strategy: either int in range or float representing int or out-of-range float
        id_int = st.integers(min_value=int64_min, max_value=int64_max)
        # float representing an integer (e.g. 1.0)
        id_float_int = st.integers(min_value=-1000, max_value=1000).map(lambda x: float(x))
        # out-of-range float (outside int64 range)
        id_float_out_of_range = st.one_of(
            st.floats(min_value=float(int64_max) + 1e5, max_value=1e20, allow_infinity=False, allow_nan=False),
            st.floats(min_value=-1e20, max_value=float(int64_min) - 1e5, allow_infinity=False, allow_nan=False),
        )
        id_choice = st.one_of(
            id_int,
            id_float_int,
            id_float_out_of_range,
        )

        # amount: string, allow empty or non-empty
        amount_str = st.text(min_size=0, max_size=20)

        # name: nullable string (string or null)
        name_str = st.one_of(st.none(), st.text(min_size=0, max_size=20))

        # status: one of known strings or (rarely) an unknown string to test rejection
        # But unknown status is rejected by all four, so no divergence there
        # So we only produce known status values
        status_str = st.sampled_from(status_values)

        # tags: array of strings, or missing (to test built_value accepting missing tags)
        # But missing tags is rejected by manual, json_serializable, freezed
        # So to get divergence, we sometimes omit tags field
        # But the problem states all six fields always present in well-formed documents,
        # so we produce tags present but sometimes empty or non-empty
        # To test divergence, we produce tags as empty list or non-empty list of strings
        tags_list = st.lists(st.text(min_size=0, max_size=10), max_size=5)

        # child: nullable record, one level recursion only
        # child.child is always null to bound recursion
        if level == 0:
            child_val = st.one_of(
                st.none(),
                record_json(level=1)
            )
        else:
            # level 1: child.child is always null
            child_val = st.none()

        # Now draw all fields
        id_v = draw(id_choice)
        amount_v = draw(amount_str)
        name_v = draw(name_str)
        status_v = draw(status_str)
        tags_v = draw(tags_list)
        child_v = draw(child_val)

        # Build JSON string for each field

        # id: if int, output as integer literal; if float, output as float literal
        if isinstance(id_v, int):
            id_json = str(id_v)
        else:
            # float: output with decimal point, no exponent to avoid jsonDecode converting to int
            # but jsonDecode will parse "1.0" as double anyway
            # format with repr to preserve precision
            id_json = repr(id_v)
            # Ensure decimal point present
            if '.' not in id_json and 'e' not in id_json and 'E' not in id_json:
                id_json += ".0"

        amount_json = json_string_literal(amount_v)
        if name_v is None:
            name_json = "null"
        else:
            name_json = json_string_literal(name_v)
        status_json = json_string_literal(status_v)
        tags_json = json_array_of_strings(tags_v)
        if child_v is None:
            child_json = "null"
        else:
            child_json = child_v

        # Compose JSON object string with all six fields present
        # To test divergence, we sometimes produce tags as missing (omit the field)
        # But problem states all six fields always present in well-formed documents,
        # so we do not omit tags here.

        # Compose JSON object string with fields in fixed order
        json_obj = (
            "{" +
            f'"id":{id_json},' +
            f'"amount":{amount_json},' +
            f'"name":{name_json},' +
            f'"status":{status_json},' +
            f'"tags":{tags_json},' +
            f'"child":{child_json}' +
            "}"
        )
        return json_obj

    # Draw the top-level record JSON string
    top_json_str = draw(record_json(level=0))

    # Return as bytes (UTF-8 encoded)
    return top_json_str.encode("utf-8")