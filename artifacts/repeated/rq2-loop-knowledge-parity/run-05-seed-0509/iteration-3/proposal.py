from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status field
    statuses = ["active", "inactive", "unknown"]

    # Helper: generate a JSON string literal with proper escaping of " and \
    def json_string(s: str) -> str:
        # minimal escaping for " and \
        return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

    # Helper: generate JSON array of strings
    def json_array_of_strings(lst):
        return "[" + ",".join(json_string(x) for x in lst) + "]"

    # Recursive record generator, depth limited to 1 (child can be null or record with child=null)
    def record_json(depth=0):
        # id: integer or double (to trigger divergence on id decoding)
        # We produce either an int literal or a float literal that is an integer value
        # or a float literal that is out of int64 range (to test saturation)
        id_type = draw(st.sampled_from(["int", "float_int", "float_out_of_range"]))
        if id_type == "int":
            # int in safe 64-bit range (to avoid jsonDecode turning it into double)
            id_val = draw(st.integers(min_value=-(2**53), max_value=2**53))
            id_json = str(id_val)
        elif id_type == "float_int":
            # float with integer value (e.g. 42.0)
            int_val = draw(st.integers(min_value=-(2**53), max_value=2**53))
            id_json = str(float(int_val))  # e.g. "42.0"
        else:
            # float out of int64 range (to test built_value int strictness vs others)
            # Use a float literal > 2**63 or < -2**63
            out_of_range_val = draw(
                st.one_of(
                    st.floats(min_value=2**63 + 1, max_value=1e20, allow_infinity=False, allow_nan=False),
                    st.floats(min_value=-1e20, max_value=-(2**63 + 1), allow_infinity=False, allow_nan=False),
                )
            )
            id_json = repr(out_of_range_val)
            # repr may produce scientific notation, which is valid JSON number

        # amount: string, always present, non-null
        # Use simple decimal strings or edge cases like empty string or "0"
        amount_val = draw(st.one_of(
            st.text(min_size=1, max_size=10).filter(lambda s: all(c.isdigit() or c in ".-" for c in s)),
            st.just("0"),
            st.just(""),
            st.just("123.45"),
            st.just("-0.99"),
        ))
        amount_json = json_string(amount_val)

        # name: nullable string, can be null or string or missing (missing accepted by all)
        # To maximize disagreement, sometimes omit name, sometimes null, sometimes string
        name_choice = draw(st.sampled_from(["present_string", "present_null", "missing"]))
        if name_choice == "present_string":
            name_val = draw(st.text(min_size=0, max_size=10))
            name_json = json_string(name_val)
            name_field = f'"name":{name_json}'
        elif name_choice == "present_null":
            name_field = '"name":null'
        else:
            name_field = None  # omit name field

        # status: one of the three valid strings or invalid string (to test rejection)
        status_choice = draw(st.sampled_from(["valid", "invalid"]))
        if status_choice == "valid":
            status_val = draw(st.sampled_from(statuses))
            status_json = json_string(status_val)
        else:
            # invalid string (not in statuses)
            status_val = draw(st.text(min_size=1, max_size=10).filter(lambda s: s not in statuses))
            status_json = json_string(status_val)
        status_field = f'"status":{status_json}'

        # tags: array of strings, always present or missing (missing accepted only by built_value)
        # To maximize disagreement, sometimes omit tags, sometimes present empty, sometimes present with strings
        tags_choice = draw(st.sampled_from(["present_empty", "present_nonempty", "missing"]))
        if tags_choice == "present_empty":
            tags_field = '"tags":[]'
        elif tags_choice == "present_nonempty":
            tags_list = draw(st.lists(st.text(min_size=1, max_size=5), min_size=1, max_size=5))
            tags_field = f'"tags":{json_array_of_strings(tags_list)}'
        else:
            tags_field = None  # omit tags field

        # child: nullable record or null or missing (missing accepted by all)
        # To maximize disagreement, sometimes omit child, sometimes null, sometimes a record with child=null
        child_choice = draw(st.sampled_from(["present_record", "present_null", "missing"]))
        if child_choice == "present_record" and depth == 0:
            # child record with child=null (depth=1)
            child_rec = record_json(depth=1)
            child_field = f'"child":{child_rec}'
        elif child_choice == "present_null":
            child_field = '"child":null'
        else:
            child_field = None  # omit child field

        # Compose fields in random order, always include id, amount, status
        fields = [f'"id":{id_json}', f'"amount":{amount_json}', status_field]
        if name_field is not None:
            fields.append(name_field)
        if tags_field is not None:
            fields.append(tags_field)
        if child_field is not None:
            fields.append(child_field)

        # Shuffle fields to avoid positional bias
        fields = draw(st.permutations(fields))

        json_obj = "{" + ",".join(fields) + "}"
        return json_obj

    # Generate top-level record JSON string
    json_text = record_json(depth=0)

    # Return as bytes
    return json_text.encode("utf-8")