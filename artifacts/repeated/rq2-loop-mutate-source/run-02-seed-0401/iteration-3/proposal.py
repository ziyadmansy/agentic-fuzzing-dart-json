from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status enum
    statuses = ["active", "inactive", "unknown"]

    # Helper: produce a JSON string literal from a Python string,
    # escaping only minimal characters for JSON correctness.
    def json_string(s: str) -> str:
        # Escape backslash and double quote, and control chars minimally
        # (Hypothesis strings are unicode, so we must escape properly)
        # We'll do a minimal escape for \ and " and control chars <0x20
        def esc_char(c):
            o = ord(c)
            if c == '"':
                return r'\"'
            elif c == '\\':
                return r'\\'
            elif o < 0x20:
                # Use \u00XX escape for control chars
                return '\\u%04x' % o
            else:
                return c
        return '"' + ''.join(esc_char(c) for c in s) + '"'

    # Helper: produce JSON text for a string or null, but with a chance to
    # produce a non-string type to provoke divergence.
    # We bias heavily to correct type, but sometimes produce a number or bool.
    def gen_name_field():
        # 80% string or null, 20% other types (number, bool, empty array)
        choice = draw(st.floats(min_value=0, max_value=1))
        if choice < 0.4:
            # string or null
            if draw(st.booleans()):
                # string
                s = draw(st.text(min_size=0, max_size=20))
                return json_string(s)
            else:
                return "null"
        elif choice < 0.7:
            # number as string (invalid type)
            n = draw(st.integers(min_value=-1000, max_value=1000))
            return str(n)
        elif choice < 0.85:
            # boolean literal (invalid type)
            return "true" if draw(st.booleans()) else "false"
        else:
            # empty array (invalid type)
            return "[]"

    # Helper: produce JSON text for the "status" field, mostly valid enum,
    # sometimes invalid string or number to provoke divergence.
    def gen_status_field():
        choice = draw(st.floats(min_value=0, max_value=1))
        if choice < 0.8:
            # valid enum string
            s = draw(st.sampled_from(statuses))
            return json_string(s)
        elif choice < 0.9:
            # invalid string
            s = draw(st.text(min_size=1, max_size=10).filter(lambda x: x not in statuses))
            return json_string(s)
        else:
            # number (invalid type)
            n = draw(st.integers(min_value=-10, max_value=10))
            return str(n)

    # Helper: produce JSON text for the "tags" field,
    # mostly array of strings, sometimes null or wrong type.
    def gen_tags_field():
        choice = draw(st.floats(min_value=0, max_value=1))
        if choice < 0.85:
            # array of strings (possibly empty)
            arr = draw(st.lists(st.text(min_size=0, max_size=10), max_size=5))
            # encode array of JSON strings
            arr_json = "[" + ",".join(json_string(s) for s in arr) + "]"
            return arr_json
        elif choice < 0.95:
            # null (invalid type)
            return "null"
        else:
            # number (invalid type)
            n = draw(st.integers(min_value=0, max_value=100))
            return str(n)

    # Helper: produce JSON text for the "amount" field,
    # which is a string normally, but sometimes a number or null to provoke divergence.
    def gen_amount_field():
        choice = draw(st.floats(min_value=0, max_value=1))
        if choice < 0.85:
            # string (could be numeric string)
            s = draw(st.text(min_size=0, max_size=20))
            return json_string(s)
        elif choice < 0.95:
            # number (invalid type)
            n = draw(st.integers(min_value=-100000, max_value=100000))
            return str(n)
        else:
            # null (invalid type)
            return "null"

    # Helper: produce JSON text for the "id" field,
    # which is an integer normally, but sometimes a string or float to provoke divergence.
    def gen_id_field():
        choice = draw(st.floats(min_value=0, max_value=1))
        if choice < 0.85:
            # integer
            n = draw(st.integers(min_value=0, max_value=1000000))
            return str(n)
        elif choice < 0.95:
            # string (invalid type)
            s = str(draw(st.integers(min_value=0, max_value=1000000)))
            return json_string(s)
        else:
            # float (invalid type)
            f = draw(st.floats(min_value=0, max_value=1000000))
            # format float with decimal point
            return repr(f)

    # Recursive generation of the "child" field, with bounded depth
    def gen_record(depth: int) -> str:
        # Compose fields, mostly valid but with some chance of type divergence
        id_field = gen_id_field()
        amount_field = gen_amount_field()
        name_field = gen_name_field()
        status_field = gen_status_field()
        tags_field = gen_tags_field()

        # child field: either null or a nested record (one level recursion max)
        if depth <= 0:
            child_field = "null"
        else:
            # 70% chance null, 30% chance nested record
            if draw(st.floats(min_value=0, max_value=1)) < 0.7:
                child_field = "null"
            else:
                child_field = gen_record(depth - 1)

        # Build JSON object text with fields in fixed order
        # Use no extra spaces to keep output compact
        json_obj = (
            '{'
            + '"id":' + id_field + ','
            + '"amount":' + amount_field + ','
            + '"name":' + name_field + ','
            + '"status":' + status_field + ','
            + '"tags":' + tags_field + ','
            + '"child":' + child_field
            + '}'
        )
        return json_obj

    # Generate top-level record with max recursion depth 1 (one nested child max)
    json_text = gen_record(depth=1)

    # Return as bytes
    return json_text.encode("utf-8")