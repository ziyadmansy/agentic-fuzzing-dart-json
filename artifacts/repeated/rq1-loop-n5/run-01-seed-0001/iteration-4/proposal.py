from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with safe codepoints and escapes
    # We'll generate Python strings and then JSON-encode them with escapes.
    # To keep it simple, generate strings with safe Unicode codepoints excluding control chars.
    # We'll manually escape backslash and quotes.
    def json_string(s: str) -> str:
        # Escape backslash and quotes and control chars
        def esc_char(c):
            if c == '"':
                return r'\"'
            elif c == '\\':
                return r'\\'
            elif c == '\b':
                return r'\b'
            elif c == '\f':
                return r'\f'
            elif c == '\n':
                return r'\n'
            elif c == '\r':
                return r'\r'
            elif c == '\t':
                return r'\t'
            elif ord(c) < 0x20:
                # Unicode escape for control chars
                return '\\u%04x' % ord(c)
            else:
                return c
        return '"' + ''.join(esc_char(c) for c in s) + '"'

    # Generate strings with codepoints excluding control chars and quotes/backslash
    safe_char = st.characters(
        blacklist_characters='"\\',
        blacklist_categories=('Cc',),  # control chars
        min_codepoint=0x20,
        max_codepoint=0x10FFFF,
    )
    string_strategy = st.text(safe_char, max_size=20).map(json_string)

    # NUMBER strategy: produce JSON numbers as strings
    # Use Hypothesis floats and ints, then convert to JSON number strings
    def json_number(n):
        # Format number according to JSON number grammar
        # Use repr for floats to get scientific notation if needed
        if isinstance(n, int):
            return str(n)
        else:
            # Use lower-case 'e' for exponent, no plus sign for positive exponent
            s = repr(n)
            # repr can produce 'inf', 'nan' - exclude those by filtering in strategy
            if 'inf' in s or 'nan' in s:
                return "0"
            # Normalize exponent to lowercase 'e' and remove + sign
            if 'E' in s:
                s = s.replace('E', 'e')
                s = s.replace('e+', 'e')
            return s

    int_strategy = st.integers(min_value=-10**6, max_value=10**6)
    float_strategy = st.floats(
        allow_infinity=False, allow_nan=False, width=32, min_value=-1e6, max_value=1e6
    )
    number_strategy = st.one_of(int_strategy, float_strategy).map(json_number)

    # Recursive JSON value strategy
    # We'll build a recursive strategy for value:
    # value = string | number | obj | arr | true | false | null

    # Forward declaration for recursive use
    json_value = st.deferred()

    # Object: { pair (, pair)* } or {}
    # pair: STRING : value
    # We'll limit pairs to max 5 to keep size bounded
    pair_strategy = st.tuples(string_strategy, json_value).map(
        lambda p: p[0] + ":" + p[1]
    )
    obj_strategy = st.one_of(
        st.just("{}"),
        st.lists(pair_strategy, min_size=1, max_size=5).map(
            lambda pairs: "{" + ",".join(pairs) + "}"
        ),
    )

    # Array: [ value (, value)* ] or []
    arr_strategy = st.one_of(
        st.just("[]"),
        st.lists(json_value, min_size=1, max_size=5).map(
            lambda vals: "[" + ",".join(vals) + "]"
        ),
    )

    # Compose value strategy
    json_value_strategy = st.recursive(
        st.one_of(
            string_strategy,
            number_strategy,
            json_true,
            json_false,
            json_null,
        ),
        lambda children: st.one_of(obj_strategy, arr_strategy),
        max_leaves=10,
    )

    # Assign to deferred
    json_value = json_value_strategy

    # Draw a JSON value and append EOF (nothing)
    json_text = draw(json_value)
    # Return bytes
    return json_text.encode("utf-8")