from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: simple safe strings with escapes
    def json_string():
        # safe codepoints excluding control chars and quotes/backslash
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)
        )
        # allow some escapes
        escapes = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # unicode escape: \uXXXX
        hex_digit = st.sampled_from('0123456789abcdefABCDEF')
        unicode_escape = st.tuples(
            st.just('\\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))

        # mix safe chars and escapes/unicode escapes
        char_piece = st.one_of(
            safe_chars.map(lambda c: c),
            escapes,
            unicode_escape
        )
        # build string pieces of length 0..20
        pieces = st.lists(char_piece, max_size=20)
        s = draw(pieces)
        # join and wrap in quotes
        return '"' + ''.join(s) + '"'

    json_string_st = st.deferred(json_string)

    # NUMBER strategy: generate numbers as strings matching grammar
    def json_number():
        # INT part
        int_part = st.one_of(
            st.just("0"),
            st.tuples(
                st.sampled_from("123456789"),
                st.text(min_size=0, max_size=5, alphabet=st.characters(min_codepoint=48, max_codepoint=57))
            ).map(lambda t: t[0] + t[1])
        )
        # fractional part
        frac_part = st.one_of(
            st.just(""),
            st.tuples(
                st.just("."),
                st.text(min_size=1, max_size=5, alphabet=st.characters(min_codepoint=48, max_codepoint=57))
            ).map(lambda t: t[0] + t[1])
        )
        # exponent part
        exp_part = st.one_of(
            st.just(""),
            st.tuples(
                st.sampled_from("eE"),
                st.one_of(st.just("+"), st.just("-"), st.just("")),
                st.text(min_size=1, max_size=3, alphabet=st.characters(min_codepoint=48, max_codepoint=57))
            ).map(lambda t: t[0] + t[1] + t[2])
        )
        # sign part
        sign_part = st.one_of(st.just(""), st.just("-"))

        return st.tuples(sign_part, int_part, frac_part, exp_part).map(lambda t: ''.join(t))

    json_number_st = st.deferred(json_number)

    # Recursive JSON value strategy
    def json_value():
        # base: primitives
        base = st.one_of(
            json_string_st,
            json_number_st,
            json_true,
            json_false,
            json_null,
        )

        # recursive containers: obj and arr
        # obj: {} or {"pair", ...}
        # pair: STRING : value
        # arr: [] or [value, ...]

        # To keep recursion bounded, limit max depth and size
        max_depth = 3
        max_pairs = 5
        max_arr_len = 5

        def obj_strategy():
            # pair: STRING : value
            pair = st.tuples(json_string_st, json_value()).map(lambda t: t[0] + ":" + t[1])
            pairs = st.lists(pair, max_size=max_pairs)
            return pairs.map(lambda ps: "{" + (",".join(ps) if ps else "") + "}")

        def arr_strategy():
            values = st.lists(json_value(), max_size=max_arr_len)
            return values.map(lambda vs: "[" + (",".join(vs) if vs else "") + "]")

        # Use recursive to combine base and containers
        return st.recursive(
            base,
            lambda children: st.one_of(obj_strategy(), arr_strategy()),
            max_leaves=100,
        )

    val = draw(json_value())
    # ensure full JSON by appending EOF (implicit)
    return val.encode("utf-8")