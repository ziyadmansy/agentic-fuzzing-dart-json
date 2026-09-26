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
        choice = draw(st.floats(min_value=0, max_value=1))
        if choice < 0.5:
            # string or null (increase chance of null to provoke divergence)
            if draw(st.booleans()):
                # string
                s = draw(st.text(min_size=0, max_size=20))
                return json_string(s)
            else:
                return "null"
        elif choice < 0.75:
            # number as string (invalid type)
            n = draw(st.integers(min_value=-1000, max_value=1000))
            return str(n)
        elif choice < 0.9:
            # boolean literal (invalid type)
            return "true" if draw(st.booleans()) else "false"
        else:
            # empty array (invalid type)
            return "[]"

    # Helper: produce JSON text for the "status" field,
    # mostly valid enum, sometimes invalid string or number to provoke divergence.
    def gen_status_field():
        choice = draw(st.floats(min_value=0, max_value=1))
        if choice < 0.75:
            # valid enum string (slightly reduced to increase invalid cases)
            s = draw(st.sampled_from(statuses))
            return json_string(s)
        elif choice < 0.9:
            # invalid string (non-enum)
            # To provoke divergence, allow empty string and strings with spaces
            s = draw(st.text(min_size=0, max_size=10).filter(lambda x: x not in statuses))
            return json_string(s)
        elif choice < 0.95:
            # number (invalid type)
            n = draw(st.integers(min_value=-10, max_value=10))
            return str(n)
        else:
            # boolean (invalid type)
            return "true" if draw(st.booleans()) else "false"

    # Helper: produce JSON text for the "tags" field,
    # mostly array of strings, sometimes null or wrong type.
    def gen_tags_field():
        choice = draw(st.floats(min_value=0, max_value=1))
        if choice < 0.8:
            # array of strings (possibly empty)
            arr = draw(st.lists(st.text(min_size=0, max_size=10), max_size=5))
            # encode array of JSON strings
            arr_json = "[" + ",".join(json_string(s) for s in arr) + "]"
            return arr_json
        elif choice < 0.9:
            # null (invalid type)
            return "null"
        elif choice < 0.95:
            # number (invalid type)
            n = draw(st.integers(min_value=0, max_value=100))
            return str(n)
        else:
            # boolean (invalid type)
            return "false" if draw(st.booleans()) else "true"

    # Helper: produce JSON text for the "amount" field,
    # which is a string normally, but sometimes a number or null to provoke divergence.
    def gen_amount_field():
        choice = draw(st.floats(min_value=0, max_value=1))
        if choice < 0.8:
            # string (could be numeric string)
            # To provoke divergence, include some numeric-looking strings and empty string
            s = draw(st.one_of(
                st.text(min_size=0, max_size=20),
                st.integers(min_value=-100000, max_value=100000).map(str)
            ))
            return json_string(s)
        elif choice < 0.9:
            # number (invalid type)
            n = draw(st.integers(min_value=-100000, max_value=100000))
            return str(n)
        elif choice < 0.95:
            # null (invalid type)
            return "null"
        else:
            # boolean (invalid type)
            return "true" if draw(st.booleans()) else "false"

    # Helper: produce JSON text for the "id" field,
    # which is an integer normally, but sometimes a string or float to provoke divergence.
    def gen_id_field():
        choice = draw(st.floats(min_value=0, max_value=1))
        if choice < 0.8:
            # integer
            n = draw(st.integers(min_value=0, max_value=1000000))
            return str(n)
        elif choice < 0.9:
            # string (invalid type)
            s = str(draw(st.integers(min_value=0, max_value=1000000)))
            return json_string(s)
        elif choice < 0.97:
            # float (invalid type)
            # To provoke divergence, include floats with trailing zeros and no exponent
            f = draw(st.floats(min_value=0, max_value=1000000, allow_infinity=False, allow_nan=False))
            # format float with decimal point, no scientific notation
            # Also sometimes produce floats with .0 to provoke divergence
            formatted = format(f, 'f')
            # Strip trailing zeros but keep at least one decimal digit
            if '.' in formatted:
                formatted = formatted.rstrip('0').rstrip('.')
                if '.' not in formatted:
                    formatted += '.0'
            return formatted
        else:
            # boolean (invalid type)
            return "false" if draw(st.booleans()) else "true"

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
            # 50% chance null, 50% chance nested record (increase nested chance slightly)
            if draw(st.floats(min_value=0, max_value=1)) < 0.5:
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