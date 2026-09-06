from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: use Hypothesis text with safe codepoints, escape as needed
    # We'll generate strings without control chars or quotes/backslash, then escape them
    def escape_json_string(s: str) -> str:
        # Escape backslash and quotes, and control chars if any
        def esc_char(c):
            if c == '"':
                return '\\"'
            elif c == '\\':
                return '\\\\'
            elif c == '\b':
                return '\\b'
            elif c == '\f':
                return '\\f'
            elif c == '\n':
                return '\\n'
            elif c == '\r':
                return '\\r'
            elif c == '\t':
                return '\\t'
            elif ord(c) < 0x20:
                # Use \uXXXX escape for control chars
                return '\\u%04x' % ord(c)
            else:
                return c
        return '"' + ''.join(esc_char(c) for c in s) + '"'

    json_string = st.text(
        alphabet=st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        ),
        min_size=0,
        max_size=20,
    ).map(escape_json_string)

    # NUMBER: use Hypothesis floats converted to JSON number strings
    # We'll generate finite floats, then convert to JSON number strings
    def float_to_json_number(f: float) -> str:
        # Format float as JSON number string, avoid scientific notation if possible
        # Use repr to preserve precision
        s = repr(f)
        # JSON allows scientific notation, so repr is fine
        return s

    json_number = st.floats(
        allow_nan=False,
        allow_infinity=False,
        width=32,
        min_value=-1e10,
        max_value=1e10,
    ).map(float_to_json_number)

    # Recursive JSON value strategy
    # Use st.recursive to build nested objects and arrays
    base = st.one_of(json_string, json_number, json_null, json_true, json_false)

    # Compose object and array strategies
    # Use bounded sizes to keep recursion and output size bounded
    def json_obj():
        # pair: STRING ':' value
        pair = st.tuples(json_string, json_value).map(lambda p: f"{p[0]}:{p[1]}")
        # object: '{' pair (',' pair)* '}' or '{}'
        return st.lists(pair, max_size=5).map(
            lambda pairs: "{" + ",".join(pairs) + "}" if pairs else "{}"
        )

    def json_arr():
        # array: '[' value (',' value)* ']' or '[]'
        return st.lists(json_value, max_size=5).map(
            lambda values: "[" + ",".join(values) + "]" if values else "[]"
        )

    # We need to define json_value for recursion, so use st.deferred
    json_value = st.deferred(lambda: st.one_of(base, json_obj(), json_arr()))

    # Draw a JSON value and encode as bytes
    s = draw(json_value)
    return s.encode("utf-8")