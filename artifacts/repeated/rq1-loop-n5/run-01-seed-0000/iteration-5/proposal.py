from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: roughly valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then json-encode them to ensure correctness.
    # But since we can't import json, we simulate escapes roughly.
    # To keep it simple, generate strings without control chars and backslash/quote,
    # plus some escaped sequences.
    def json_string():
        # safe codepoints excluding control chars and backslash/quote
        safe_chars = st.characters(
            blacklist_characters=['\\', '"'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # small strings to keep size bounded
        base_str = st.text(safe_chars, min_size=0, max_size=10)

        # add some escaped sequences randomly
        def escape_some(s):
            # randomly replace some chars with escapes
            import random
            escapes = {
                '"': '\\"',
                '\\': '\\\\',
                '\b': '\\b',
                '\f': '\\f',
                '\n': '\\n',
                '\r': '\\r',
                '\t': '\\t',
            }
            res = []
            for c in s:
                if c in escapes and random.random() < 0.3:
                    res.append(escapes[c])
                else:
                    res.append(c)
            return "".join(res)

        # We can't use random inside draw, so just draw from a strategy that includes escapes:
        # We'll generate strings that may contain backslash and quote escaped properly.
        # To do this, generate a list of either safe chars or escape sequences.
        esc_seq = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])
        safe_char = st.characters(
            blacklist_characters=['\\', '"', '\b', '\f', '\n', '\r', '\t'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        pieces = st.lists(st.one_of(safe_char.map(lambda c: c), esc_seq), max_size=10)
        s = draw(pieces)
        return '"' + "".join(s) + '"'

    json_string_st = st.deferred(json_string)

    # NUMBER: generate numbers as strings matching the grammar
    # We'll generate Python floats and ints and convert to strings matching JSON number grammar.
    def json_number():
        # generate int or float or exponent form
        # int part
        int_part = st.one_of(
            st.just("0"),
            st.integers(min_value=1, max_value=10**6).map(str),
        )
        # fraction part
        fraction_part = st.one_of(
            st.just(""),
            st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False)
            .map(lambda f: ("%.6f" % f)[1:] if f > 0 else ""),
        )
        # exponent part
        exponent_part = st.one_of(
            st.just(""),
            st.integers(min_value=-10, max_value=10).map(lambda e: "e%+d" % e),
            st.integers(min_value=-10, max_value=10).map(lambda e: "E%+d" % e),
        )
        # sign
        sign = st.one_of(st.just(""), st.just("-"))

        @st.composite
        def number_str(draw):
            s = draw(sign)
            i = draw(int_part)
            s += i
            # fraction part: either empty or .digits
            if draw(st.booleans()):
                # generate fraction digits
                digits = draw(st.text(st.characters(min_codepoint=48, max_codepoint=57), min_size=1, max_size=6))
                s += "." + digits
            # exponent part
            s += draw(exponent_part)
            return s

        return number_str()

    json_number_st = json_number()

    # Recursive JSON value
    # We'll use st.recursive to build nested objects and arrays with bounded depth and size.

    # Forward declaration for value
    json_value = st.deferred(lambda: json_value_inner)

    # Pair: STRING ':' value
    @st.composite
    def json_pair(draw):
        key = draw(json_string_st)
        val = draw(json_value)
        return f"{key}:{val}"

    # Object: '{' pair (',' pair)* '}' or '{}'
    @st.composite
    def json_object(draw):
        # limit number of pairs to keep size bounded
        pairs = draw(st.lists(json_pair(), max_size=5))
        if not pairs:
            return "{}"
        return "{" + ",".join(pairs) + "}"

    # Array: '[' value (',' value)* ']' or '[]'
    @st.composite
    def json_array(draw):
        values = draw(st.lists(json_value, max_size=5))
        if not values:
            return "[]"
        return "[" + ",".join(values) + "]"

    # Compose value strategy recursively
    json_value_inner = st.recursive(
        st.one_of(
            json_string_st,
            json_number_st,
            json_true,
            json_false,
            json_null,
        ),
        lambda children: st.one_of(
            json_object(),
            json_array(),
        ),
        max_leaves=10,
    )

    # Compose full json with EOF (just ensure full consumption)
    json_text = json_value_inner.map(lambda s: s)

    s = draw(json_text)
    return s.encode("utf-8")