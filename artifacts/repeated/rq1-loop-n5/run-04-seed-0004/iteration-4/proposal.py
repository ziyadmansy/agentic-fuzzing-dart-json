from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy producing valid JSON strings
    # Use st.text with safe codepoints excluding control chars and quotes/backslash
    # SAFECODEPOINT: ~["\\\u0000-\u001F]
    safe_chars = st.characters(
        blacklist_characters=['"', '\\'],
        min_codepoint=0x20,
        max_codepoint=0x10FFFF,
    )
    json_string = st.text(safe_chars, min_size=0, max_size=20).map(lambda s: '"' + s + '"')

    # NUMBER strategy matching JSON number grammar
    # Use st.floats and st.integers to generate numbers, then format as JSON number strings
    def number_to_json(n):
        # Format int or float to JSON number string without trailing .0 if int
        if isinstance(n, int):
            return str(n)
        else:
            # Use repr to preserve exponent notation if any
            return repr(n)

    json_number = st.one_of(
        st.integers(min_value=-1_000_000, max_value=1_000_000).map(number_to_json),
        st.floats(
            allow_nan=False,
            allow_infinity=False,
            width=32,
            min_value=-1e6,
            max_value=1e6,
        ).map(number_to_json),
    )

    # Recursive JSON value strategy
    # We'll define a function to build recursive JSON values as strings

    # Forward declaration for recursive use
    json_value = st.deferred(lambda: json_value_strategy)

    # JSON pair: STRING ':' value
    json_pair = st.tuples(json_string, json_value).map(lambda p: f"{p[0]}:{p[1]}")

    # JSON object: '{' pair (',' pair)* '}' or '{}'
    json_object = st.recursive(
        st.just("{}"),
        lambda children: st.lists(json_pair, min_size=1, max_size=4).map(
            lambda pairs: "{" + ",".join(pairs) + "}"
        ),
        max_leaves=10,
    )

    # JSON array: '[' value (',' value)* ']' or '[]'
    json_array = st.recursive(
        st.just("[]"),
        lambda children: st.lists(json_value, min_size=1, max_size=4).map(
            lambda values: "[" + ",".join(values) + "]"
        ),
        max_leaves=10,
    )

    # Compose the json_value_strategy with all possible JSON values
    json_value_strategy = st.one_of(
        json_string,
        json_number,
        json_object,
        json_array,
        json_true,
        json_false,
        json_null,
    )

    # Draw a JSON value string
    result_str = draw(json_value_strategy)

    # Return as bytes
    return result_str.encode("utf-8")