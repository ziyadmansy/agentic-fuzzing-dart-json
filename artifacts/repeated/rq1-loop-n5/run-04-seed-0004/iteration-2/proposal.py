from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_bool = st.one_of(json_true, json_false)
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(lambda f: format(f, '.15g'))
    # JSON strings: roughly matching the grammar (no control chars, escaped quotes and backslashes)
    # We'll generate unicode strings and then escape as needed
    def escape_json_string(s: str) -> str:
        # Escape backslash, quote, and control chars
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
                # Unicode escape for control chars
                return '\\u%04x' % ord(c)
            else:
                return c
        return '"' + ''.join(esc_char(c) for c in s) + '"'
    json_string = st.text(
        st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        ),
        max_size=20,
    ).map(escape_json_string)

    # Recursive JSON values: string, number, object, array, true, false, null
    # Use st.recursive to keep size bounded
    def json_value_strategy():
        base = st.one_of(json_string, json_number, json_bool, json_null)
        return st.recursive(
            base,
            lambda children: st.one_of(
                # object: { pair (, pair)* } or {}
                st.dictionaries(
                    keys=json_string,
                    values=children,
                    max_size=3,
                    # keys must be unique strings, but json_string includes quotes,
                    # so keys are quoted strings, which is valid JSON keys
                ).map(lambda d: "{" + ",".join(f"{k}:{v}" for k, v in d.items()) + "}"),
                # array: [ value (, value)* ] or []
                st.lists(children, max_size=3).map(lambda l: "[" + ",".join(l) + "]"),
            ),
            max_leaves=10,
        )
    json_value = json_value_strategy()

    # Compose full JSON with EOF (just the value, since EOF is implicit)
    s = draw(json_value)
    return s.encode('utf-8')