from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(str)
    # JSON strings: use Hypothesis text with safe codepoints, escape quotes and backslashes
    def json_string_escape(s: str) -> str:
        # Escape backslash and double quote, and control chars
        s = s.replace('\\', '\\\\').replace('"', '\\"')
        # Replace control chars with \uXXXX
        def esc_char(c):
            if ord(c) < 0x20:
                return f"\\u{ord(c):04x}"
            return c
        return ''.join(esc_char(c) for c in s)
    json_string = st.text(
        alphabet=st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        ),
        min_size=0,
        max_size=20,
    ).map(json_string_escape).map(lambda s: f'"{s}"')

    # Recursive JSON values: objects and arrays
    # Use st.recursive with a max depth to avoid max recursion depth exceeded
    base = st.one_of(json_null, json_true, json_false, json_number, json_string)

    # Compose object and array strategies
    # pair: STRING ':' value
    def json_pair():
        return st.tuples(json_string, generated_json_value).map(lambda p: f"{p[0]}:{p[1]}")

    # We define generated_json_value here as a placeholder for recursive use
    # We'll define it after base to avoid forward reference issues

    # Compose object and array with bounded size
    def json_object():
        # Up to 3 pairs to keep size bounded
        return st.lists(json_pair(), max_size=3).map(
            lambda pairs: "{" + ",".join(pairs) + "}" if pairs else "{}"
        )

    def json_array():
        # Up to 3 values to keep size bounded
        return st.lists(generated_json_value, max_size=3).map(
            lambda values: "[" + ",".join(values) + "]" if values else "[]"
        )

    # Now define generated_json_value recursively
    generated_json_value = st.recursive(
        base,
        lambda children: st.one_of(json_object(), json_array()),
        max_leaves=10,
    )

    # Draw the final JSON string and encode to bytes
    json_str = draw(generated_json_value)
    return json_str.encode("utf-8")