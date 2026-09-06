from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.from_regex(
        r"-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?",
        fullmatch=True,
        flags=0,
    )
    # STRING: roughly valid JSON strings with escapes
    # We generate unicode codepoints excluding control chars and quotes/backslash
    # and allow some escapes.
    # To keep it simple, generate strings with safe codepoints and some escapes.
    def json_string():
        # safe characters excluding control chars, quote, backslash
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # escape sequences allowed: \", \\, \b, \f, \n, \r, \t, \uXXXX
        escapes = st.sampled_from([
            r'\"', r'\\', r'\b', r'\f', r'\n', r'\r', r'\t',
        ])
        # unicode escape \uXXXX
        hex_digit = st.sampled_from("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just(r'\u'),
            hex_digit, hex_digit, hex_digit, hex_digit,
        ).map(lambda t: "".join(t))
        # mix safe chars and escapes/unicode escapes
        chunk = st.one_of(
            safe_chars.map(lambda c: c),
            escapes,
            unicode_escape,
        )
        # generate a string of length 0..20
        s = st.lists(chunk, max_size=20).map("".join)
        return s.map(lambda s: f'"{s}"')

    json_string_strat = json_string()

    # Recursive JSON value strategy
    # Use st.recursive with a max depth to avoid max recursion depth exceeded
    base = st.one_of(
        json_string_strat,
        json_number,
        json_true,
        json_false,
        json_null,
    )

    def extend_json_children(children):
        # object: { pair (, pair)* } or {}
        # pair: STRING : value
        pair = st.tuples(json_string_strat, children).map(lambda t: f"{t[0]}:{t[1]}")
        obj = st.one_of(
            st.just("{}"),
            st.lists(pair, max_size=5).map(lambda pairs: "{" + ",".join(pairs) + "}"),
        )
        # array: [ value (, value)* ] or []
        arr = st.one_of(
            st.just("[]"),
            st.lists(children, max_size=5).map(lambda values: "[" + ",".join(values) + "]"),
        )
        return st.one_of(obj, arr)

    json_value = st.recursive(base, extend_json_children, max_leaves=20)

    s = draw(json_value)
    return s.encode("utf-8")