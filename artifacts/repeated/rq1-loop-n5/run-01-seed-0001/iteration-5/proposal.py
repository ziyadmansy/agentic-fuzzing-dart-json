from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: use Hypothesis built-in json string strategy,
    # but restrict to safe codepoints to match grammar SAFECODEPOINT and ESC
    # Hypothesis' json module has a string strategy, but to keep self-contained:
    # We'll generate strings with safe unicode codepoints excluding control chars and quotes/backslash.
    # We'll allow escape sequences by including backslash and quotes with escaping.
    # To keep it simple and valid, use st.text with safe characters and then json-encode it.
    # But since we must produce bytes of JSON text, we will produce the raw JSON string including quotes.

    # Characters allowed inside strings (SAFECODEPOINT): all except control chars, quote, backslash
    safe_chars = (
        st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
    )
    # To allow escapes, we can include backslash and quote but only as escaped sequences.
    # For simplicity, generate safe strings without escapes.
    # This is near-valid and valid JSON strings.

    json_string = draw(
        st.text(safe_chars, min_size=0, max_size=20)
        .map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')
    )

    # NUMBER strategy: generate numbers as strings matching grammar
    # Use Hypothesis floats converted to strings with JSON-compatible formatting
    def number_to_json(n: float) -> str:
        # Format float to JSON number string without trailing .0 if possible
        if n == float('inf') or n == float('-inf') or n != n:
            # JSON does not support NaN or infinities, fallback to 0
            return "0"
        s = repr(n)
        # repr may produce '1.0', convert to '1' if integer
        if '.' in s or 'e' in s or 'E' in s:
            try:
                f = float(s)
                i = int(f)
                if f == i:
                    return str(i)
            except Exception:
                pass
        return s

    json_number = st.floats(
        allow_infinity=False,
        allow_nan=False,
        width=32,
        min_value=-1e10,
        max_value=1e10,
    ).map(number_to_json)

    # Forward declaration for recursive strategy
    # We'll build a recursive strategy for value

    # Define value strategy recursively
    def json_value():
        return st.deferred(lambda: value_strategy)

    # Object strategy: { pair (, pair)* } or {}
    # pair: STRING : value
    # We'll limit number of pairs to keep size bounded
    def json_pair():
        return st.tuples(
            st.text(safe_chars, min_size=1, max_size=10).map(
                lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'
            ),
            json_value(),
        ).map(lambda t: t[0] + ":" + t[1])

    json_object = st.one_of(
        st.just("{}"),
        st.lists(json_pair(), min_size=1, max_size=5).map(lambda pairs: "{" + ",".join(pairs) + "}"),
    )

    # Array strategy: [ value (, value)* ] or []
    json_array = st.one_of(
        st.just("[]"),
        st.lists(json_value(), min_size=1, max_size=5).map(lambda values: "[" + ",".join(values) + "]"),
    )

    # Compose value strategy
    value_strategy = st.recursive(
        st.one_of(
            json_string,
            json_number,
            json_null,
            json_true,
            json_false,
        ),
        lambda children: st.one_of(
            json_object,
            json_array,
        ),
        max_leaves=10,
    )

    # Draw a value and encode to bytes
    result = draw(value_strategy)
    return result.encode("utf-8")