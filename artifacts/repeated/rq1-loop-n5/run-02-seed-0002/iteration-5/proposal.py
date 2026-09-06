from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # JSON string: use safe unicode characters excluding control chars and quotes/backslash
    # We generate strings without control chars and without unescaped quotes/backslash
    # Then we escape them properly.
    def json_string():
        # Generate a string of safe codepoints (excluding control chars and " \)
        # SAFECODEPOINT in grammar excludes control chars and " \, so we mimic that.
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        s = st.text(safe_chars, min_size=0, max_size=20)

        # Escape special chars per JSON spec
        def escape_json_string(s):
            # Escape backslash and quote
            s = s.replace('\\', '\\\\').replace('"', '\\"')
            # Escape control chars (U+0000 to U+001F)
            def esc_char(c):
                o = ord(c)
                if o < 0x20:
                    return '\\u%04x' % o
                return c
            s = ''.join(esc_char(c) for c in s)
            return f'"{s}"'

        return s.map(escape_json_string)

    json_string_st = json_string()

    # JSON number: use Hypothesis floats converted to JSON number strings
    # We generate finite floats, then convert to JSON number strings
    def json_number():
        # Generate floats in a reasonable range to avoid too long exponentials
        f = st.floats(
            allow_nan=False,
            allow_infinity=False,
            width=32,
            min_value=-1e10,
            max_value=1e10,
        )
        def float_to_json_number(x):
            # Use repr to get shortest representation
            s = repr(x)
            # repr can produce 'inf', 'nan' - filtered by floats strategy
            # JSON numbers cannot have leading +, so repr is safe
            # Also, repr(1.0) -> '1.0' which is valid JSON number
            return s
        return f.map(float_to_json_number)

    json_number_st = json_number()

    # Recursive JSON value strategy
    # Use st.recursive to build arrays and objects with bounded depth and size
    base = st.one_of(
        json_null,
        json_true,
        json_false,
        json_string_st,
        json_number_st,
    )

    # Forward declaration for recursive use
    # We limit max size of arrays and objects to keep examples small
    def json_value():
        return st.recursive(
            base,
            lambda children: st.one_of(
                # Object: { pair (, pair)* } or empty {}
                st.dictionaries(
                    keys=json_string_st.map(lambda s: s[1:-1]),  # strip quotes for keys
                    values=children,
                    min_size=0,
                    max_size=4,
                ).map(
                    lambda d: (
                        '{' +
                        ','.join(f'"{k}":{v}' for k, v in d.items()) +
                        '}'
                    )
                ),
                # Array: [ value (, value)* ] or empty []
                st.lists(children, min_size=0, max_size=4).map(
                    lambda l: '[' + ','.join(l) + ']'
                ),
            ),
            max_leaves=10,
        )

    json_str = draw(json_value())
    return json_str.encode('utf-8')