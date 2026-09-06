from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We limit length to keep size bounded.
    def json_string():
        # Characters allowed inside strings: safe codepoints excluding control chars and " \ 
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Escapes: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
        # We'll include some escapes randomly
        def escape():
            simple_escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
            # Unicode escape: \u followed by 4 hex digits
            hex_digit = st.characters("0123456789abcdefABCDEF")
            unicode_escape = st.tuples(
                st.just('\\u'),
                hex_digit, hex_digit, hex_digit, hex_digit
            ).map(lambda t: ''.join(t))
            return st.one_of(simple_escapes, unicode_escape)

        # Compose string content as a list of either safe chars or escapes
        # Limit length to max 20 for boundedness
        content = st.lists(st.one_of(safe_chars.map(lambda c: c), escape()), max_size=20).map(''.join)
        return content.map(lambda s: f'"{s}"')

    json_string_st = json_string()

    # NUMBER strategy: produce valid JSON numbers
    # Use Hypothesis built-in floats converted to JSON number strings, plus integers
    def json_number():
        # We'll generate numbers as strings matching the grammar
        # Limit exponent and fraction length for boundedness
        int_part = st.one_of(
            st.just("0"),
            st.integers(min_value=1, max_value=10**6).map(str)
        )
        frac_part = st.one_of(
            st.just(""),
            st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False)
            .map(lambda f: f"{f:.6f}".split('.')[1].rstrip('0'))
            .filter(lambda s: s != "")
            .map(lambda s: '.' + s)
        )
        exp_part = st.one_of(
            st.just(""),
            st.integers(min_value=-10, max_value=10).map(lambda e: f"E{e}" if e >= 0 else f"E{e}")
        )
        sign = st.one_of(st.just(""), st.just("-"))
        return st.tuples(sign, int_part, frac_part, exp_part).map(lambda t: ''.join(t))

    json_number_st = json_number()

    # Forward declaration for recursive structures
    # We'll use st.recursive to build obj and arr

    # obj: '{' pair (',' pair)* '}' | '{}'
    # pair: STRING ':' value

    # arr: '[' value (',' value)* ']' | '[]'

    # value: STRING | NUMBER | obj | arr | true | false | null

    # Define value strategy recursively
    # To keep size bounded, limit max depth and max size of collections

    # First define pair strategy
    def pair_strategy(value_st):
        return st.tuples(json_string_st, value_st).map(lambda t: f"{t[0]}:{t[1]}")

    # Recursive value strategy
    def value_strategy():
        # We define a recursive strategy for value
        base = st.one_of(
            json_string_st,
            json_number_st,
            json_true,
            json_false,
            json_null,
        )

        def obj_strategy(value_st):
            # pairs: 0 to 3 pairs
            pairs = st.lists(pair_strategy(value_st), max_size=3)
            # either empty object or with pairs joined by commas
            return st.one_of(
                st.just("{}"),
                pairs.map(lambda ps: "{" + ",".join(ps) + "}")
            )

        def arr_strategy(value_st):
            # elements: 0 to 3 values
            elements = st.lists(value_st, max_size=3)
            return st.one_of(
                st.just("[]"),
                elements.map(lambda es: "[" + ",".join(es) + "]")
            )

        return st.recursive(
            base,
            lambda children: st.one_of(
                obj_strategy(children),
                arr_strategy(children),
            ),
            max_leaves=10,
        )

    val_st = value_strategy()

    # Compose full JSON: value + EOF (just value here)
    json_st = val_st

    s = draw(json_st)
    return s.encode("utf-8")