from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: roughly matching grammar, allowing safe codepoints and escapes
    # We'll generate Python strings and then JSON-encode them with escapes.
    # To keep near-valid cases, allow some control chars occasionally.
    def json_string():
        # Characters allowed in SAFECODEPOINT: ~["\\\u0000-\u001F]
        # We'll generate unicode strings excluding control chars except some escapes.
        # To keep it simple, generate strings with codepoints from 0x20 to 0x10FFFF except backslash and quote.
        # We'll allow backslash and quote but escape them.
        # Use st.text with a filter and then json.dumps to encode.
        import json
        # Generate text with codepoints excluding control chars and excluding unescaped quotes and backslash
        # We'll generate text with characters from 0x20 to 0x10FFFF except '"' and '\\'
        # Then json.dumps will add escapes as needed.
        # To keep near-valid, sometimes include control chars that get escaped.
        base_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Occasionally include control chars to get escapes
        control_chars = st.characters(min_codepoint=0x00, max_codepoint=0x1F)
        # Mix control chars and base chars
        text = st.text(
            st.one_of(base_chars, control_chars),
            min_size=0,
            max_size=20,
        )
        s = draw(text)
        # Use json.dumps to produce a valid JSON string literal
        return json.dumps(s)

    json_string_st = st.deferred(json_string)

    # NUMBER: generate numbers matching grammar
    # We'll generate floats and ints and convert to string matching grammar
    def json_number():
        # Generate int or float or exponent form
        # To keep near-valid, generate floats with optional exponent
        # We'll generate Python floats and format them to JSON number strings
        # Also generate ints with optional leading minus
        # Use st.floats with constraints to avoid NaN/inf
        # Also generate ints separately
        int_part = st.integers(min_value=-(10**6), max_value=10**6)
        float_part = st.floats(
            allow_nan=False,
            allow_infinity=False,
            width=32,
            min_value=-1e6,
            max_value=1e6,
        )
        # Choose int or float
        choice = draw(st.booleans())
        if choice:
            n = draw(int_part)
            return str(n)
        else:
            f = draw(float_part)
            # Format float to JSON number string
            # Use repr to get a compact representation
            s = repr(f)
            # repr may produce 'inf' or 'nan' but we filtered those out
            # repr may produce '1e-07' which is valid JSON number
            # Remove trailing .0 if present to keep near-valid
            if s.endswith(".0"):
                s = s[:-2]
            return s

    json_number_st = st.deferred(json_number)

    # Recursive JSON value strategy
    # We'll use st.recursive to build obj and arr

    # Forward declare value strategy
    # value = STRING | NUMBER | obj | arr | true | false | null

    # Base values
    base_values = st.one_of(
        json_string_st,
        json_number_st,
        json_null,
        json_true,
        json_false,
    )

    # Pair: STRING ':' value
    @st.composite
    def pair(draw):
        k = draw(json_string_st)
        v = draw(value)
        return f"{k}:{v}"

    # obj: '{' pair (',' pair)* '}' or '{}'
    @st.composite
    def obj(draw):
        # To keep sizes bounded, limit number of pairs
        n = draw(st.integers(min_value=0, max_value=4))
        if n == 0:
            return "{}"
        pairs = [draw(pair) for _ in range(n)]
        return "{" + ",".join(pairs) + "}"

    # arr: '[' value (',' value)* ']' or '[]'
    @st.composite
    def arr(draw):
        n = draw(st.integers(min_value=0, max_value=4))
        if n == 0:
            return "[]"
        values = [draw(value) for _ in range(n)]
        return "[" + ",".join(values) + "]"

    # Now define value as recursive strategy
    value = st.recursive(
        base_values,
        lambda children: st.one_of(
            obj(),
            arr(),
        ),
        max_leaves=10,
    )

    # Draw the top-level json value and add EOF (nothing after)
    top = draw(value)
    # Return as bytes
    return top.encode("utf-8")