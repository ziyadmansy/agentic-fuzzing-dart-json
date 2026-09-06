from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: roughly valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then JSON-encode them to ensure correctness.
    # But since we can't import json or use eval/exec, we must build strings manually.
    # We'll generate strings with safe unicode codepoints excluding control chars and quotes/backslash.
    # Also add some escapes manually.
    def json_string():
        # safe codepoints excluding control chars, quotes, backslash
        safe_chars = (
            [chr(c) for c in range(0x20, 0x7F) if c not in (0x22, 0x5C)] +
            [chr(c) for c in range(0xA0, 0x10000)]
        )
        # escapes: \", \\, \b, \f, \n, \r, \t, \uXXXX
        escapes = ['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t']
        # unicode escape generator
        def unicode_escape():
            codepoint = draw(st.integers(min_value=0x20, max_value=0xFFFF))
            return f"\\u{codepoint:04x}"
        # build string pieces: either safe char, escape, or unicode escape
        pieces = []
        length = draw(st.integers(min_value=0, max_value=20))
        for _ in range(length):
            choice = draw(st.integers(min_value=0, max_value=10))
            if choice <= 6:
                # safe char
                c = draw(st.sampled_from(safe_chars))
                pieces.append(c)
            elif choice == 7:
                # escape
                e = draw(st.sampled_from(escapes))
                pieces.append(e)
            else:
                # unicode escape
                pieces.append(unicode_escape())
        return '"' + "".join(pieces) + '"'

    json_string_st = st.deferred(json_string)

    # NUMBER: generate numbers as strings matching the grammar
    def json_number():
        # sign
        sign = draw(st.sampled_from(["", "-"]))
        # int part
        int_part = draw(st.one_of(
            st.just("0"),
            st.integers(min_value=1, max_value=10**6).map(str)
        ))
        # fraction
        fraction = draw(st.one_of(
            st.just(""),
            st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False)
              .map(lambda f: ("%.6f" % f)[1:])  # get fraction part like .123456
        ))
        # exponent
        exponent = draw(st.one_of(
            st.just(""),
            st.tuples(
                st.sampled_from(["e", "E"]),
                st.sampled_from(["", "+", "-"]),
                st.integers(min_value=0, max_value=99)
            ).map(lambda t: t[0] + t[1] + str(t[2]))
        ))
        return sign + int_part + fraction + exponent

    json_number_st = st.deferred(json_number)

    # Forward declarations for recursive structures
    # We'll use st.recursive to build value

    # value strategy placeholder
    def value_strategy():
        return st.deferred(lambda: value_st)

    # pair: STRING ':' value
    @st.composite
    def pair(draw):
        key = draw(json_string_st)
        val = draw(value_strategy())
        return f"{key}:{val}"

    # obj: '{' pair (',' pair)* '}' | '{}'
    @st.composite
    def obj(draw):
        # limit number of pairs to keep size bounded
        n = draw(st.integers(min_value=0, max_value=4))
        if n == 0:
            return "{}"
        pairs = [draw(pair) for _ in range(n)]
        return "{" + ",".join(pairs) + "}"

    # arr: '[' value (',' value)* ']' | '[]'
    @st.composite
    def arr(draw):
        n = draw(st.integers(min_value=0, max_value=4))
        if n == 0:
            return "[]"
        values = [draw(value_strategy()) for _ in range(n)]
        return "[" + ",".join(values) + "]"

    # Compose value strategy recursively
    value_st = st.recursive(
        st.one_of(
            json_string_st,
            json_number_st,
            json_true,
            json_false,
            json_null,
        ),
        lambda children: st.one_of(
            obj(),
            arr(),
        ),
        max_leaves=10,
    )

    # Draw a full JSON value and append EOF (nothing)
    json_text = draw(value_st)
    # Return as bytes
    return json_text.encode("utf-8")