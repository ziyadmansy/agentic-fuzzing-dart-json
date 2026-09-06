from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: simplified safe string with escapes
    def json_string():
        # We generate strings with safe codepoints and some escapes
        # SAFECODEPOINT ~["\\\u0000-\u001F], so exclude control and backslash and quote
        safe_chars = st.characters(
            blacklist_characters=['\\', '"'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Escapes: \", \\, \b, \f, \n, \r, \t, \uXXXX
        # We'll include a few escapes randomly
        def escape_str():
            esc_simple = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])
            esc_unicode = st.builds(
                lambda h: '\\u' + h,
                st.text(st.characters(min_codepoint=0x30, max_codepoint=0x39), min_size=4, max_size=4)
            )
            return st.one_of(esc_simple, esc_unicode)
        # Compose string parts: mix safe chars and escapes
        part = st.one_of(
            safe_chars.map(lambda c: c),
            escape_str()
        )
        # Generate a list of parts, join, and quote
        s = draw(st.lists(part, min_size=0, max_size=20))
        return '"' + ''.join(s) + '"'

    json_string_st = st.deferred(lambda: st.builds(lambda s: s, json_string()))

    # NUMBER strategy
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(lambda f: format(f, '.15g'))

    # Forward declare value to allow recursion
    # We'll use st.recursive to build obj and arr

    # Placeholder for value, to be defined recursively
    def json_value():
        # Compose base values
        base = st.one_of(
            json_string_st,
            json_number,
            json_null,
            json_true,
            json_false,
        )
        # Recursive containers
        def json_obj():
            # pair: STRING : value
            pair = st.tuples(json_string_st, json_value()).map(lambda p: p[0] + ':' + p[1])
            # obj: {} or { pair (, pair)* }
            return st.one_of(
                st.just('{}'),
                st.lists(pair, min_size=1, max_size=4).map(lambda pairs: '{' + ','.join(pairs) + '}')
            )

        def json_arr():
            # arr: [] or [ value (, value)* ]
            return st.one_of(
                st.just('[]'),
                st.lists(json_value(), min_size=1, max_size=4).map(lambda vs: '[' + ','.join(vs) + ']')
            )

        return st.recursive(
            base,
            lambda children: st.one_of(json_obj(), json_arr()),
            max_leaves=10,
        )

    val = draw(json_value())
    return val.encode('utf-8')