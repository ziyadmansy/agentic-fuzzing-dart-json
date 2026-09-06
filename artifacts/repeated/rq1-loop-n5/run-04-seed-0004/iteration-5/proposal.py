from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: roughly matching grammar, allowing escapes and safe codepoints
    # We'll produce valid JSON strings using Hypothesis's built-in json string strategy
    json_string = st.text(
        alphabet=(
            # safe codepoints excluding control chars and quotes/backslash
            st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

    # NUMBER: produce JSON numbers as strings
    # Use floats and ints, then convert to JSON number strings
    def number_to_json(n):
        # Format int or float to JSON number string
        if isinstance(n, int):
            return str(n)
        else:
            # Use repr to get JSON-compatible float string (e.g. no trailing .0 if int)
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
    # Use st.recursive to build nested objects and arrays, bounded depth and size
    base = st.one_of(json_string, json_number, json_null, json_true, json_false)

    # Pair: STRING ':' value
    @st.composite
    def json_pair(draw, value_strat):
        key = draw(json_string)
        val = draw(value_strat)
        return f"{key}:{val}"

    def json_obj(value_strat):
        # Objects with 0 to 4 pairs
        return st.lists(json_pair(value_strat), min_size=0, max_size=4).map(
            lambda pairs: "{" + (",".join(pairs)) + "}"
        )

    def json_arr(value_strat):
        # Arrays with 0 to 4 elements
        return st.lists(value_strat, min_size=0, max_size=4).map(
            lambda elems: "[" + (",".join(elems)) + "]"
        )

    json_value = st.recursive(
        base,
        lambda children: st.one_of(json_obj(children), json_arr(children)),
        max_leaves=20,
    )

    result = draw(json_value)
    return result.encode("utf-8")