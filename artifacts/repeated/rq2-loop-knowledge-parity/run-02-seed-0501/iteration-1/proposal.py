from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status field
    statuses = ["active", "inactive", "unknown"]

    # Recursive record generator with bounded depth (max 1 level of child)
    def record(depth=0):
        # id: integer or double that jsonDecode would parse as double (to test int vs double acceptance)
        # We produce either an integer in 64-bit range or a large integer outside 64-bit range that jsonDecode turns into double
        # We produce id as a JSON number literal string (not quoted), but since we must produce JSON text, we must produce it as string
        # So we produce the id field as a JSON number literal (not string) in the JSON text.
        # But we must produce JSON text, so we must produce id as a number literal in the JSON text.
        # We'll produce id as a string representing a number literal (no quotes around it).
        # To do that, we produce id as a string of digits or number literal, then insert it verbatim in the JSON text.
        # So we produce id as a string representing a number literal, then insert it verbatim.

        # amount: string (always present, non-null)
        amount_str = draw(st.text(min_size=1, max_size=10))

        # name: string or null (nullable)
        name_val = draw(st.one_of(st.none(), st.text(max_size=10)))

        # status: one of "active", "inactive", "unknown"
        status_val = draw(st.sampled_from(statuses))

        # tags: array of strings, or missing (to test built_value accepts missing tags)
        # We produce either present tags (array of strings) or missing tags (omit field)
        tags_present = draw(st.booleans())
        if tags_present:
            tags_val = draw(st.lists(st.text(min_size=1, max_size=10), max_size=3))
        else:
            tags_val = None  # missing field

        # child: null or a record (one level recursion max)
        if depth == 0:
            child_val = draw(st.one_of(st.none(), record(depth=1)))
        else:
            child_val = draw(st.none())

        # id field: produce a number literal string for JSON text
        # We produce either:
        # - a normal int in 64-bit range (e.g. between -2**53 and 2**53)
        # - or a large int outside 64-bit range (e.g. 2**63 + something) that jsonDecode parses as double
        id_choice = draw(st.booleans())
        if id_choice:
            # normal int in safe range for JSON number (to test manual and built_value accept int)
            id_num = draw(st.integers(min_value=-(2**53), max_value=2**53))
            id_json = str(id_num)
        else:
            # large int outside 64-bit range, which jsonDecode parses as double
            # produce a large integer literal > 2**63 or < -2**63
            large_int = draw(st.one_of(
                st.integers(min_value=2**63 + 1, max_value=2**64),
                st.integers(min_value=-(2**64), max_value=-(2**63 + 1)),
            ))
            id_json = str(large_int)

        # Build JSON text for this record, carefully inserting fields
        # We produce fields in fixed order: id, amount, name, status, tags (optional), child (optional)
        # name and child nullable, tags optional (omit if tags_val is None)
        # name and child present with null or string/object

        # amount is a string, so must be quoted and escaped
        def json_string(s):
            # minimal JSON string escaping for quotes and backslash and control chars
            # Hypothesis strings are unicode, so escape quotes and backslash and control chars
            # We'll replace backslash and quote and control chars with escapes
            # Control chars: <0x20 must be escaped as \u00XX
            # For simplicity, escape backslash and quote and control chars
            res = []
            for c in s:
                o = ord(c)
                if c == '"':
                    res.append('\\"')
                elif c == '\\':
                    res.append('\\\\')
                elif o < 0x20:
                    res.append('\\u%04x' % o)
                else:
                    res.append(c)
            return '"' + ''.join(res) + '"'

        # tags array JSON text
        if tags_val is not None:
            tags_json = '[' + ','.join(json_string(t) for t in tags_val) + ']'

        # child JSON text or null
        if child_val is None:
            child_json = 'null'
        else:
            child_json = child_val

        # name JSON text or null
        if name_val is None:
            name_json = 'null'
        else:
            name_json = json_string(name_val)

        # Compose fields as JSON key:value pairs
        fields = [
            '"id":' + id_json,
            '"amount":' + json_string(amount_str),
            '"name":' + name_json,
            '"status":' + json_string(status_val),
        ]
        if tags_val is not None:
            fields.append('"tags":' + tags_json)
        # else omit tags field to test built_value accepts missing tags

        fields.append('"child":' + child_json)

        json_obj = '{' + ','.join(fields) + '}'
        return json_obj

    # Draw top-level record JSON text
    json_text = draw(record(depth=0))
    return json_text.encode('utf-8')