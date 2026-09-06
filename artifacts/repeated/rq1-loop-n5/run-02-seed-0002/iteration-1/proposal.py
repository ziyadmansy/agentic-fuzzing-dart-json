from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and " \)
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Escapes
        escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape: \uXXXX
        hex_digit = st.characters("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just('\\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))

        # Mix safe chars and escapes/unicode escapes
        # To keep it simple, generate a list of pieces, each either a safe char or an escape
        piece = st.one_of(
            safe_chars.map(lambda c: c),
            escapes,
            unicode_escape,
        )
        # Generate a list of pieces, length bounded
        pieces = st.lists(piece, min_size=0, max_size=20)
        return pieces.map(lambda pieces: '"' + ''.join(pieces) + '"')

    # NUMBER strategy: generate valid JSON numbers as strings
    def json_number():
        # Use Hypothesis built-in floats but convert to JSON number string format
        # We limit floats to finite numbers and avoid infinities and NaNs
        # Also produce integers as strings
        # We'll generate numbers as strings directly to avoid float formatting issues
        # Compose number parts manually
        sign = st.one_of(st.just(''), st.just('-'))
        int_part = st.one_of(st.just('0'), st.integers(min_value=1, max_value=10**6).map(str))
        frac_part = st.one_of(st.just(''), st.floats(min_value=0, max_value=1).map(lambda f: f"{f:.6f}".split('.')[1].rstrip('0')))
        # frac_part can be empty string if no fraction
        # exponent part
        exp_sign = st.one_of(st.just(''), st.sampled_from(['e', 'E']))
        exp_sign2 = st.one_of(st.just(''), st.sampled_from(['+', '-']))
        exp_digits = st.one_of(st.just(''), st.integers(min_value=0, max_value=99).map(str))
        def build_number(s, i, f, es, es2, ed):
            if f == '':
                frac = ''
            else:
                frac = '.' + f
            if es == '' or ed == '':
                exp = ''
            else:
                exp = es + es2 + ed
            return s + i + frac + exp
        return st.tuples(sign, int_part, frac_part, exp_sign, exp_sign2, exp_digits).map(
            lambda t: build_number(*t)
        ).filter(lambda s: s not in ('', '-', '.', '-.', '-e', '-E'))  # filter out invalid partials

    # Forward declaration for recursive structures
    # We'll define value later using st.deferred

    # Pair: STRING : value
    @st.composite
    def json_pair(draw, value):
        key = draw(json_string())
        val = draw(value)
        return f"{key}:{val}"

    # Object: { pair (, pair)* } or {}
    def json_object(value):
        # list of pairs, max 3 pairs to keep size bounded
        pairs = st.lists(json_pair(value), min_size=0, max_size=3)
        return pairs.map(lambda ps: '{' + (','.join(ps) if ps else '') + '}')

    # Array: [ value (, value)* ] or []
    def json_array(value):
        elems = st.lists(value, min_size=0, max_size=3)
        return elems.map(lambda es: '[' + (','.join(es) if es else '') + ']')

    # Recursive value definition
    def json_value():
        return st.deferred(lambda:
            st.one_of(
                json_string(),
                json_number(),
                json_object(json_value()),
                json_array(json_value()),
                json_true,
                json_false,
                json_null,
            )
        )

    # Compose full JSON: value + EOF (implicit)
    val = draw(json_value())
    return val.encode('utf-8')