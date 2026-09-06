from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # JSON strings: quoted, with safe codepoints and escapes
    # We'll generate unicode strings and then escape them properly
    def json_string():
        # Use a small max_size to keep examples bounded
        # Use characters excluding control chars and quotes/backslash
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',),
        )
        # Compose string with safe chars and some escapes
        # We'll generate a unicode string and then escape it manually
        return st.text(safe_chars, max_size=10).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

    # JSON numbers: use Hypothesis floats and ints, then format as JSON numbers
    def json_number():
        # Generate floats and ints in a reasonable range
        # Format according to JSON number grammar
        def format_number(n):
            # Format int or float without trailing .0 if int
            if isinstance(n, int):
                return str(n)
            else:
                # Use repr to get a JSON-compatible float representation
                # but avoid scientific notation for small numbers
                s = repr(n)
                # JSON allows scientific notation, so repr is fine
                return s
        # Use floats and ints, bounded to avoid huge numbers
        num_strategy = st.one_of(
            st.integers(min_value=-10_000, max_value=10_000),
            st.floats(min_value=-1e6, max_value=1e6, allow_infinity=False, allow_nan=False),
        )
        return num_strategy.map(format_number)

    # Forward declaration for recursive structures
    # We'll define value_strategy recursively below

    # Compose object pairs: "string": value
    @st.composite
    def json_pair(draw):
        key = draw(json_string())
        val = draw(value_strategy)
        return f"{key}:{val}"

    # Compose objects: { pair (, pair)* } or {}
    @st.composite
    def json_object(draw):
        # Limit number of pairs to keep size bounded
        pairs = draw(st.lists(json_pair(), max_size=3))
        if not pairs:
            return "{}"
        else:
            return "{" + ",".join(pairs) + "}"

    # Compose arrays: [ value (, value)* ] or []
    @st.composite
    def json_array(draw):
        values = draw(st.lists(value_strategy, max_size=3))
        if not values:
            return "[]"
        else:
            return "[" + ",".join(values) + "]"

    # Recursive value strategy
    # Use st.recursive to build nested structures with bounded depth
    base = st.one_of(
        json_null,
        json_true,
        json_false,
        json_string(),
        json_number(),
    )

    # We need to define value_strategy before use in json_pair, json_object, json_array
    # So we use st.deferred to break circular dependency
    value_strategy = st.deferred(lambda: st.one_of(
        base,
        json_object(),
        json_array(),
    ))

    # Draw a full JSON value and append EOF (nothing)
    val = draw(value_strategy)
    # Return as bytes
    return val.encode("utf-8")