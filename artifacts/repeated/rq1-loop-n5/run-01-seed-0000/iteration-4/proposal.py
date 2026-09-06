from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then encode them as JSON strings with escapes.
    # To keep near-valid cases, allow some minimal invalid escapes (e.g. incomplete \u)
    # but mostly valid.
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and " \)
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Escapes: \", \\, \b, \f, \n, \r, \t, \uXXXX
        # We'll generate a mix of safe chars and escapes.
        # To keep it simple, generate a list of either safe chars or escapes.
        escape_simple = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape: \u + 4 hex digits
        hex_digit = st.sampled_from('0123456789abcdefABCDEF')
        unicode_escape = st.tuples(
            st.just('\\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))
        # Occasionally produce an invalid escape (e.g. \u with less than 4 hex digits)
        invalid_unicode_escape = st.one_of(
            st.just('\\u'),
            st.text('0123456789abcdefABCDEF', min_size=1, max_size=3).map(lambda s: '\\u' + s)
        )
        escape = st.one_of(escape_simple, unicode_escape, invalid_unicode_escape)

        # Compose string content: list of safe chars or escapes
        content = st.lists(st.one_of(safe_chars.map(lambda c: c), escape), min_size=0, max_size=20)
        # Join and wrap in quotes
        return content.map(lambda chars: '"' + ''.join(chars) + '"')

    json_string_st = json_string()

    # NUMBER strategy: generate valid JSON numbers as strings
    # We'll generate numbers as strings to preserve formatting (e.g. leading zeros disallowed)
    # and to allow near-valid cases, we can sometimes produce invalid numbers (e.g. leading zeros)
    def json_number():
        # Valid number parts
        sign = st.one_of(st.just(''), st.just('-'))
        int_part = st.one_of(
            st.just('0'),
            st.integers(min_value=1, max_value=999999).map(str)
        )
        frac_part = st.one_of(st.just(''), st.floats(min_value=0, max_value=1).map(lambda f: '.' + str(f)[2:]))
        exp_part = st.one_of(
            st.just(''),
            st.tuples(
                st.sampled_from(['e', 'E']),
                st.one_of(st.just(''), st.sampled_from(['+', '-'])),
                st.integers(min_value=0, max_value=99)
            ).map(lambda t: t[0] + t[1] + str(t[2]))
        )
        # Occasionally produce invalid numbers: leading zeros (e.g. 00), missing digits after dot, etc.
        invalid_number = st.one_of(
            st.just('00'),
            st.just('-00'),
            st.just('.123'),
            st.just('1.'),
            st.just('1e'),
            st.just('1e+'),
            st.just('-'),
            st.just('')
        )
        return st.one_of(
            st.tuples(sign, int_part, frac_part, exp_part).map(lambda t: ''.join(t)),
            invalid_number
        )

    json_number_st = json_number()

    # Recursive JSON value strategy
    # We'll use st.recursive to build nested objects and arrays with bounded depth and size
    def json_value():
        base = st.one_of(
            json_string_st,
            json_number_st,
            json_null,
            json_true,
            json_false,
        )

        # obj: '{' pair (',' pair)* '}' or '{}'
        # pair: STRING ':' value
        # arr: '[' value (',' value)* ']' or '[]'

        # We'll define pair and obj and arr recursively

        @st.composite
        def pair(draw):
            k = draw(json_string_st)
            v = draw(value)
            return f"{k}:{v}"

        @st.composite
        def obj(draw):
            # empty or 1-3 pairs
            n = draw(st.integers(min_value=0, max_value=3))
            if n == 0:
                return "{}"
            pairs = draw(st.lists(pair(), min_size=n, max_size=n))
            return "{" + ",".join(pairs) + "}"

        @st.composite
        def arr(draw):
            # empty or 1-4 values
            n = draw(st.integers(min_value=0, max_value=4))
            if n == 0:
                return "[]"
            vals = draw(st.lists(value, min_size=n, max_size=n))
            return "[" + ",".join(vals) + "]"

        # Compose value with recursion
        value = st.deferred(lambda: st.one_of(
            base,
            obj(),
            arr(),
        ))

        return value

    value = json_value()

    # Draw the full JSON text and encode as bytes
    json_text = draw(value)
    return json_text.encode('utf-8')