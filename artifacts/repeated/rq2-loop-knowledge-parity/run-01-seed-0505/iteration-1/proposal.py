from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status field
    statuses = ["active", "inactive", "unknown"]

    # Recursive record generator with depth limit 1 for "child"
    # Returns a dict with all six fields present and well-formed
    def record(depth=0):
        # id: integer (within 64-bit signed range)
        # To exploit the difference in id decoding, sometimes produce int64-range int,
        # sometimes produce a number outside int64 range as a JSON number (which jsonDecode
        # will parse as double).
        # 64-bit signed int range: -2**63 to 2**63-1
        int64_min = -2**63
        int64_max = 2**63 - 1

        # Choose id as int inside range or as a large int outside range (encoded as JSON number)
        id_choice = draw(st.booleans())
        if id_choice:
            # inside 64-bit range int
            id_val = draw(st.integers(min_value=int64_min, max_value=int64_max))
        else:
            # outside 64-bit range, produce a large integer literal that jsonDecode will parse as double
            # Use a number > 2**63 or < -2**63, but represent as JSON number (no quotes)
            # Hypothesis integers can be arbitrarily large, but we must produce JSON text here.
            # We'll produce a string representing the number, then embed it as JSON number.
            # We'll do this later in the final string construction.
            # For now, just mark it as a string to be inserted raw.
            # We'll return a special wrapper to indicate raw number insertion.
            # But since we must produce JSON text, we must handle this carefully.
            # Instead, we can produce a string representing the number and later insert it raw.
            # So here, id_val can be a string representing a large integer literal.
            # We'll distinguish it by type.
            large_int = draw(
                st.one_of(
                    st.integers(min_value=int64_max + 1, max_value=int64_max + 10**6),
                    st.integers(min_value=int64_min - 10**6, max_value=int64_min - 1),
                )
            )
            id_val = str(large_int)  # string to be inserted raw as JSON number

        # amount: string, non-null, arbitrary string but valid JSON string
        # To test subtle differences, sometimes produce numeric strings, sometimes empty, sometimes normal
        amount_val = draw(st.text(min_size=1, max_size=20))

        # name: nullable string, so either null or string
        name_val = draw(st.one_of(st.none(), st.text(max_size=20)))

        # status: one of the three allowed strings, or sometimes an unrecognized string to test rejection
        # But unrecognized status is rejected by all four, so no divergence there.
        # So only produce valid status strings.
        status_val = draw(st.sampled_from(statuses))

        # tags: array of strings, always present
        # To test missing tags (which built_value accepts but others reject), we must sometimes omit tags field.
        # But the problem states all six fields always present in well-formed document.
        # We want to produce syntactically valid JSON objects always.
        # To test divergence, sometimes omit tags field (to trigger known difference).
        # But the problem states "all six fields always present in a well-formed document".
        # So to produce disagreement, we can produce documents with tags missing (to trigger known divergence),
        # but the problem states "all six fields always present in a well-formed document".
        # So we must produce always six fields present.
        # So we produce tags always present, but sometimes empty list, sometimes non-empty.
        tags_len = draw(st.integers(min_value=0, max_value=3))
        tags_val = draw(st.lists(st.text(min_size=1, max_size=10), min_size=tags_len, max_size=tags_len))

        # child: nullable record, one level recursion only
        if depth == 0:
            child_val = draw(st.one_of(st.none(), record(depth=1)))
        else:
            child_val = None

        # Compose dict with all fields present
        # For id_val, if it's a string representing a large int, we must insert it as raw JSON number,
        # so we cannot just json.dumps the dict.
        # We'll build JSON text manually later.
        return {
            "id": id_val,
            "amount": amount_val,
            "name": name_val,
            "status": status_val,
            "tags": tags_val,
            "child": child_val,
        }

    # Generate a record at top level
    rec = record()

    # Now build JSON text manually as a string, carefully:
    # id: if int, output as number literal
    # if string (large int), output as number literal (no quotes)
    # amount: JSON string
    # name: null or JSON string
    # status: JSON string
    # tags: JSON array of strings
    # child: null or nested record (recursive call to a helper)

    def json_string(s):
        # Escape JSON string characters minimally
        # Replace backslash and quote and control chars
        # For simplicity, only escape backslash and quote and control chars \b\f\n\r\t
        # Hypothesis text may contain any unicode, but JSON accepts unicode except control chars
        # We'll escape control chars as \uXXXX
        def escape_char(c):
            o = ord(c)
            if c == '"':
                return '\\"'
            elif c == '\\':
                return '\\\\'
            elif c == '\b':
                return '\\b'
            elif c == '\f':
                return '\\f'
            elif c == '\n':
                return '\\n'
            elif c == '\r':
                return '\\r'
            elif c == '\t':
                return '\\t'
            elif o < 0x20:
                return '\\u%04x' % o
            else:
                return c
        return '"' + ''.join(escape_char(c) for c in s) + '"'

    def json_value(v):
        if v is None:
            return "null"
        elif isinstance(v, str):
            return json_string(v)
        elif isinstance(v, int):
            return str(v)
        elif isinstance(v, list):
            return "[" + ",".join(json_value(x) for x in v) + "]"
        elif isinstance(v, dict):
            # dict representing a record
            # keys always known and six fields
            # output fields in fixed order
            fields = []
            # id field special: can be int or string representing large int literal
            idv = v["id"]
            if isinstance(idv, int):
                id_json = str(idv)
            else:
                # string representing large int literal, output raw (no quotes)
                id_json = idv
            fields.append('"id":' + id_json)
            fields.append('"amount":' + json_value(v["amount"]))
            if v["name"] is None:
                fields.append('"name":null')
            else:
                fields.append('"name":' + json_value(v["name"]))
            fields.append('"status":' + json_value(v["status"]))
            fields.append('"tags":' + json_value(v["tags"]))
            if v["child"] is None:
                fields.append('"child":null')
            else:
                fields.append('"child":' + json_value(v["child"]))
            return "{" + ",".join(fields) + "}"
        else:
            # Should not happen
            raise ValueError("Unexpected type in json_value")

    json_text = json_value(rec)
    return json_text.encode("utf-8")