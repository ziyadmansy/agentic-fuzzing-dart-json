from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for fields with known constraints
    statuses = st.sampled_from(["active", "inactive", "unknown"])
    # name is nullable string
    name_strategy = st.one_of(st.none(), st.text(min_size=0, max_size=20))
    # tags is array of strings, always present but can be empty
    tags_strategy = st.lists(st.text(min_size=0, max_size=10), max_size=5)

    # id: to exploit difference in int decoding:
    # manual and built_value require int (no double),
    # json_serializable and freezed accept double and convert to int via toInt().
    # jsonDecode turns integer literals outside 64-bit range into double.
    # So produce either:
    # - a normal int in 64-bit range (accepted by all)
    # - an integer > 2**63-1 (64-bit max) as a JSON number literal (which jsonDecode parses as double)
    # - a double that is integral but out of int64 range
    # We'll produce either a normal int or a large int literal that jsonDecode parses as double.
    # Hypothesis integers are unbounded, but we must produce JSON text, so produce number literals as strings.
    # We'll produce the id field as a JSON number literal string, not as a Python int, to control the JSON text.
    # But we cannot import json, so we must build JSON text manually.
    # So id_strategy produces a string representing a JSON number literal (integer or double).
    # We'll produce either:
    # - a normal int in [-2**63, 2**63-1]
    # - a large int > 2**63-1 (which jsonDecode parses as double)
    # - a large negative int < -2**63 (also parsed as double)
    # We'll produce the id field as a string representing the number literal, then embed it verbatim in JSON text.

    # Define boundaries
    INT64_MIN = -2**63
    INT64_MAX = 2**63 - 1

    # id number literal as string strategy
    def id_number_literal():
        choice = draw(st.integers(min_value=0, max_value=2))
        if choice == 0:
            # normal int64 range integer
            v = draw(st.integers(min_value=INT64_MIN, max_value=INT64_MAX))
            return str(v)
        elif choice == 1:
            # large positive integer outside int64 range (parsed as double)
            v = draw(st.integers(min_value=INT64_MAX + 1, max_value=INT64_MAX + 10**6))
            return str(v)
        else:
            # large negative integer outside int64 range (parsed as double)
            v = draw(st.integers(min_value=INT64_MIN - 10**6, max_value=INT64_MIN - 1))
            return str(v)

    # amount is string, always present
    amount_strategy = st.text(min_size=0, max_size=20)

    # status: one of three strings, or possibly an invalid string to test rejection
    # But all reject unrecognized status, so no point in invalid here.
    # We'll keep it valid to focus on other fields.

    # child: nullable record, one level recursion only
    # We'll limit recursion depth to 1: child can be null or a record with child=null.
    # To avoid infinite recursion, define a helper function.

    def record_strategy(depth=0):
        # id as number literal string (to embed verbatim)
        id_str = id_number_literal()

        # amount string
        amount = draw(amount_strategy)

        # name nullable string
        name = draw(name_strategy)

        # status string
        status = draw(statuses)

        # tags array of strings
        tags = draw(tags_strategy)

        # child: null or record if depth==0, else null only
        if depth == 0:
            child = draw(st.one_of(st.none(), record_strategy(depth=1)))
        else:
            child = None

        # Build JSON text for this record:
        # We must produce syntactically valid JSON text with all fields present.
        # Fields: id (number literal), amount (string), name (string|null),
        # status (string), tags (array of strings), child (record|null)

        # Helper to JSON-escape strings (minimal, only backslash and quotes)
        def json_escape(s):
            s = s.replace('\\', '\\\\').replace('"', '\\"')
            # Also escape control chars for safety
            s = ''.join(c if c >= ' ' else '\\u%04x' % ord(c) for c in s)
            return s

        # Serialize amount string
        amount_json = '"' + json_escape(amount) + '"'

        # Serialize name nullable string
        if name is None:
            name_json = 'null'
        else:
            name_json = '"' + json_escape(name) + '"'

        # Serialize status string
        status_json = '"' + status + '"'

        # Serialize tags array of strings
        tags_json = '[' + ','.join('"' + json_escape(t) + '"' for t in tags) + ']'

        # Serialize child
        if child is None:
            child_json = 'null'
        else:
            child_json = child

        # Compose JSON object text
        json_obj = (
            '{'
            f'"id":{id_str},'
            f'"amount":{amount_json},'
            f'"name":{name_json},'
            f'"status":{status_json},'
            f'"tags":{tags_json},'
            f'"child":{child_json}'
            '}'
        )
        return json_obj

    # Draw top-level record JSON text
    json_text = record_strategy(depth=0)

    # Return bytes
    return json_text.encode('utf-8')