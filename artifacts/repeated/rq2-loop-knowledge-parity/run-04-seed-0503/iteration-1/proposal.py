from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Helper: JSON string with proper escaping for quotes and backslashes only (minimal)
    # We keep strings simple: no control chars, no unicode escapes, just ascii letters/digits/spaces
    def json_string():
        # safe chars for JSON string: letters, digits, space, dash, underscore
        safe_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -_"
        return st.text(alphabet=safe_chars, min_size=0, max_size=10).map(
            lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'
        )

    # JSON array of strings (tags)
    def json_string_array():
        # array of 0 to 3 strings
        return st.lists(json_string(), min_size=0, max_size=3).map(
            lambda lst: "[" + ",".join(lst) + "]"
        )

    # JSON null or JSON object (for child)
    # We'll limit recursion depth to 1 (child.child always null)
    def json_record(depth=0):
        # id: integer or double (to trigger divergence)
        # manual and built_value require int; json_serializable and freezed accept double.toInt()
        # We produce either an int literal or a double literal that is an integer value
        # Also try out-of-range int as double to test saturation behavior
        id_choice = draw(st.integers(min_value=-(2**63), max_value=2**63 - 1))
        # With some probability, produce a double that is integer-valued (e.g. 42.0)
        # or a double outside int64 range (e.g. 2**63 as double)
        id_is_double = draw(st.booleans())
        if id_is_double:
            # produce double literal as string
            # either integer-valued double within int64 range or out-of-range double
            out_of_range = draw(st.booleans())
            if out_of_range:
                # double outside int64 range (e.g. 2**63 or -2**63-1)
                val = 2**63 if draw(st.booleans()) else -(2**63) - 1
                id_json = str(float(val))  # e.g. "9223372036854775808.0"
            else:
                # integer-valued double within int64 range
                val = id_choice
                id_json = str(float(val))  # e.g. "42.0"
        else:
            # int literal
            id_json = str(id_choice)

        # amount: string (non-null)
        amount_json = draw(json_string())

        # name: string or null (nullable)
        name_is_null = draw(st.booleans())
        if name_is_null:
            name_json = "null"
        else:
            name_json = draw(json_string())

        # status: one of "active", "inactive", "unknown"
        # Also try unrecognized string to confirm rejection (but that scores zero)
        # So mostly pick valid status, but sometimes invalid to test rejection
        status_valid = draw(st.booleans())
        if status_valid:
            status_val = draw(st.sampled_from(["active", "inactive", "unknown"]))
            status_json = '"' + status_val + '"'
        else:
            # invalid status string (should be rejected by all)
            invalid_status = draw(st.text(min_size=1, max_size=5).filter(lambda s: s not in {"active","inactive","unknown"}))
            status_json = '"' + invalid_status.replace('"', '\\"') + '"'

        # tags: array of strings or missing (to test built_value vs others)
        # We produce either present tags or missing tags
        tags_present = draw(st.booleans())
        if tags_present:
            tags_json = draw(json_string_array())
        else:
            tags_json = None  # missing field

        # child: null or nested record (depth limited to 1)
        child_is_null = draw(st.booleans())
        if child_is_null or depth >= 1:
            child_json = "null"
        else:
            child_json = json_record(depth=depth+1)

        # Compose fields as list of key:value strings
        fields = []
        fields.append('"id":' + id_json)
        fields.append('"amount":' + amount_json)
        if name_json == "null":
            fields.append('"name":null')
        else:
            fields.append('"name":' + name_json)
        fields.append('"status":' + status_json)
        if tags_json is not None:
            fields.append('"tags":' + tags_json)
        # else omit tags field to test built_value behavior
        fields.append('"child":' + child_json)

        # Shuffle fields order to avoid positional bias
        # Hypothesis does not have a shuffle strategy, so we do a random permutation via sampled_from
        # But we cannot import random, so just keep order fixed (acceptable)
        json_obj = "{" + ",".join(fields) + "}"

        return json_obj

    # Generate top-level record JSON string
    json_text = draw(json_record(depth=0))

    # Return as bytes
    return json_text.encode("utf-8")