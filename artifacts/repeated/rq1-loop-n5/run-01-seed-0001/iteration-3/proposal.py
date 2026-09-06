from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(str)
    # JSON strings: use Hypothesis text with safe codepoints, escape quotes and backslashes
    def json_string():
        # Use a limited set of safe characters to avoid control chars
        # Escape backslash and quotes
        def escape_json_str(s: str) -> str:
            s = s.replace('\\', '\\\\').replace('"', '\\"')
            # Also escape control characters (U+0000 to U+001F)
            s_escaped = []
            for c in s:
                if ord(c) < 0x20:
                    s_escaped.append(f"\\u{ord(c):04x}")
                else:
                    s_escaped.append(c)
            return "".join(s_escaped)
        return st.text(
            alphabet=st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            ),
            min_size=0,
            max_size=20,
        ).map(lambda s: '"' + escape_json_str(s) + '"')

    json_string_strat = json_string()

    # Recursive definition for objects and arrays
    # We'll define a recursive strategy for JSON values
    # to keep size bounded, limit max_leaves and max_depth
    def json_value():
        # We define a recursive strategy for JSON values
        base = st.one_of(
            json_string_strat,
            json_number,
            json_null,
            json_true,
            json_false,
        )
        # Recursive container types
        return st.recursive(
            base,
            lambda children: st.one_of(
                # object: { pair (, pair)* } or {}
                st.dictionaries(
                    keys=json_string_strat,
                    values=children,
                    min_size=0,
                    max_size=3,
                ).map(
                    lambda d: (
                        "{" +
                        ",".join(f"{k}:{v}" for k, v in d.items()) +
                        "}"
                    )
                ),
                # array: [ value (, value)* ] or []
                st.lists(children, min_size=0, max_size=3).map(
                    lambda l: "[" + ",".join(l) + "]"
                ),
            ),
            max_leaves=10,
        )

    result = draw(json_value())
    return result.encode("utf-8")