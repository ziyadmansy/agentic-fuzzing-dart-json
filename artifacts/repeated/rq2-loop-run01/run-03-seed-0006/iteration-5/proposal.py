from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status enum
    statuses = ["active", "inactive", "unknown"]

    # Helper to produce a JSON string literal (with minimal escaping)
    def json_string(s: str) -> str:
        # Escape backslash and double quote minimally
        s = s.replace("\\", "\\\\").replace('"', '\\"')
        # Also escape control chars (simple approach)
        s = s.replace("\b", "\\b").replace("\f", "\\f").replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
        return '"' + s + '"'

    # Helper to produce JSON array of strings
    def json_string_array(strings):
        return "[" + ",".join(json_string(s) for s in strings) + "]"

    # Recursive record generator with bounded depth
    def record(depth=0):
        # id: integer normally, but to induce divergence, allow sometimes string or float or null
        # but keep JSON valid and field present always
        # We'll produce id as integer or stringified integer or float (as string) or null (rare)
        id_choice = draw(st.one_of(
            st.integers(min_value=0, max_value=2**31-1).map(str),
            st.integers(min_value=0, max_value=2**31-1),
            st.floats(allow_nan=False, allow_infinity=False, width=32).map(lambda f: format(f, '.6g')),
            st.just("null"),
        ))
        # id must be present and integer or string or float or null (string "null" means JSON null)
        if id_choice == "null":
            id_json = "null"
        elif isinstance(id_choice, int):
            id_json = str(id_choice)
        else:
            # id_choice is string (either stringified int or float)
            # To induce divergence, sometimes quote it, sometimes not
            # But id must be a JSON value, so if string, quote it
            # We'll randomly decide to quote or not to induce divergence
            quote_id = draw(st.booleans())
            if quote_id:
                id_json = json_string(id_choice)
            else:
                id_json = id_choice

        # amount: string normally, but sometimes number or null or empty string
        # amount is always present
        amount_val = draw(st.one_of(
            st.text(min_size=1, max_size=10).filter(lambda s: all(32 <= ord(c) <= 126 for c in s)),  # printable ascii
            st.integers(min_value=0, max_value=100000).map(str),
            st.floats(allow_nan=False, allow_infinity=False, width=32).map(lambda f: format(f, '.6g')),
            st.just("null"),
            st.just(""),  # empty string
        ))
        if amount_val == "null":
            amount_json = "null"
        elif amount_val == "":
            amount_json = json_string("")
        else:
            # amount normally string, so quote it
            amount_json = json_string(str(amount_val))

        # name: string or null
        # To induce divergence, sometimes omit quotes on null, sometimes quote "null" string
        name_val = draw(st.one_of(
            st.none(),
            st.text(min_size=0, max_size=20).filter(lambda s: all(32 <= ord(c) <= 126 for c in s)),
            st.just("null"),  # string "null"
        ))
        if name_val is None:
            name_json = "null"
        elif name_val == "null":
            # sometimes quoted, sometimes unquoted (invalid JSON if unquoted, so always quote)
            name_json = json_string("null")
        else:
            name_json = json_string(name_val)

        # status: one of the three strings normally
        # To induce divergence, sometimes uppercase, sometimes misspelled, sometimes null
        status_val = draw(st.one_of(
            st.sampled_from(statuses),
            st.sampled_from([s.upper() for s in statuses]),
            st.sampled_from(["active ", "inactive ", "unknown ", "actve", "inactiv", "unknwn"]),
            st.none(),
        ))
        if status_val is None:
            status_json = "null"
        else:
            status_json = json_string(status_val)

        # tags: array of strings, always present
        # To induce divergence, sometimes empty array, sometimes array with null, sometimes array with numbers as strings or numbers unquoted
        tags_len = draw(st.integers(min_value=0, max_value=3))
        tags_list = []
        for _ in range(tags_len):
            tag_val = draw(st.one_of(
                st.text(min_size=1, max_size=10).filter(lambda s: all(32 <= ord(c) <= 126 for c in s)),
                st.none(),
                st.integers(min_value=0, max_value=100).map(str),
                st.floats(allow_nan=False, allow_infinity=False, width=32).map(lambda f: format(f, '.6g')),
            ))
            if tag_val is None:
                tags_list.append("null")
            elif isinstance(tag_val, str):
                # sometimes quote, sometimes not (to induce divergence)
                quote_tag = draw(st.booleans())
                if quote_tag:
                    tags_list.append(json_string(tag_val))
                else:
                    # unquoted string is invalid JSON, so quote always
                    tags_list.append(json_string(tag_val))
            else:
                # number as string, quote it
                tags_list.append(json_string(str(tag_val)))
        tags_json = "[" + ",".join(tags_list) + "]"

        # child: either null or another record (one level recursion max)
        if depth >= 1:
            child_json = "null"
        else:
            child_present = draw(st.booleans())
            if not child_present:
                child_json = "null"
            else:
                child_json = record(depth=depth+1)

        # Compose the JSON object fields in random order to induce divergence on order-sensitive parsers (unlikely but possible)
        fields = [
            ('"id"', id_json),
            ('"amount"', amount_json),
            ('"name"', name_json),
            ('"status"', status_json),
            ('"tags"', tags_json),
            ('"child"', child_json),
        ]
        # Shuffle fields order
        fields = draw(st.permutations(fields))

        json_obj = "{" + ",".join(f"{k}:{v}" for k, v in fields) + "}"
        return json_obj.encode("utf-8")

    return record()