from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: roughly matching JSON string with escapes and safe codepoints
    # We'll generate Python strings and encode them as JSON strings using repr-like escaping.
    # To keep it simple and valid, use st.text with safe chars and then json.dumps equivalent.
    # But since we can't import json, we do a minimal escape here.

    def json_string(s: str) -> str:
        # Escape backslash and quotes and control chars minimally
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
                return '\\u%04x' % ord(c)
            else:
                return c
        return '"' + ''.join(esc_char(c) for c in s) + '"'

    json_string_strat = st.text(
        alphabet=st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        ),
        min_size=0,
        max_size=20,
    ).map(json_string)

    # NUMBER: generate numbers as strings matching JSON number grammar
    # Use floats and ints, then convert to string with minimal formatting
    def json_number(n):
        # Format number to JSON number string
        # Use repr for floats, str for ints
        if isinstance(n, int):
            return str(n)
        else:
            # Use repr but remove trailing .0 if possible
            s = repr(n)
            if '.' in s or 'e' in s or 'E' in s:
                return s.lower()
            else:
                return s

    json_number_strat = st.one_of(
        st.integers(min_value=-(10**6), max_value=10**6),
        st.floats(allow_nan=False, allow_infinity=False, width=32, min_value=-1e6, max_value=1e6),
    ).map(json_number)

    # Recursive JSON value strategy
    # Use st.recursive to build obj and arr

    # Forward declaration for value
    # We'll define value_strat after obj and arr

    # Pair: STRING ':' value
    @st.composite
    def pair(draw, value_strat):
        k = draw(json_string_strat)
        v = draw(value_strat)
        return f"{k}:{v}"

    # obj: '{' pair (',' pair)* '}' or '{}'
    def obj_strat(value_strat):
        # pairs list, max 5 pairs to keep size bounded
        pairs = st.lists(pair(value_strat), min_size=0, max_size=5)
        return pairs.map(lambda ps: "{" + ",".join(ps) + "}")

    # arr: '[' value (',' value)* ']' or '[]'
    def arr_strat(value_strat):
        vals = st.lists(value_strat, min_size=0, max_size=5)
        return vals.map(lambda vs: "[" + ",".join(vs) + "]")

    # Now define value_strat recursively
    def value_strat():
        base = st.one_of(
            json_string_strat,
            json_number_strat,
            json_true,
            json_false,
            json_null,
        )
        return st.recursive(
            base,
            lambda children: st.one_of(
                obj_strat(children),
                arr_strat(children),
            ),
            max_leaves=10,
        )

    val_strat = value_strat()

    # The top-level json is a value followed by EOF (no trailing chars)
    json_str = val_strat

    s = draw(json_str)
    return s.encode("utf-8")