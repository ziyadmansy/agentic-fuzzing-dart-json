from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON values
    json_null = st.just("null")
    json_bool = st.sampled_from(["true", "false"])
    json_number = st.from_regex(
        r"-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?",
        fullmatch=True,
        flags=0,
    )
    # STRING: roughly matching JSON string content (no control chars, escapes allowed)
    # We'll generate strings and then JSON-encode them to ensure correctness.
    json_string = st.text(
        st.characters(
            blacklist_characters=['\\', '"', '\u0000', '\u0001', '\u0002', '\u0003', '\u0004', '\u0005',
                                  '\u0006', '\u0007', '\u0008', '\u000b', '\u000c', '\u000e', '\u000f',
                                  '\u0010', '\u0011', '\u0012', '\u0013', '\u0014', '\u0015', '\u0016',
                                  '\u0017', '\u0018', '\u0019', '\u001a', '\u001b', '\u001c', '\u001d',
                                  '\u001e', '\u001f'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        ),
        max_size=20,
    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

    # Recursive JSON value strategy with bounded depth
    # We'll build objects and arrays recursively but limit max depth to avoid recursion errors.
    def json_value():
        # Base values
        base = st.one_of(json_string, json_number, json_bool, json_null)
        # Recursive container values
        return st.recursive(
            base,
            lambda children: st.one_of(
                # Object: { pair (, pair)* } or {}
                st.dictionaries(
                    keys=json_string,
                    values=children,
                    max_size=3,
                    # keys are strings already quoted, but JSON requires keys as strings, so keys are strings with quotes
                ).map(lambda d: "{" + ",".join(f"{k}:{v}" for k, v in d.items()) + "}"),
                # Array: [ value (, value)* ] or []
                st.lists(children, max_size=3).map(lambda l: "[" + ",".join(l) + "]"),
            ),
            max_leaves=10,
        )

    val = draw(json_value())
    return val.encode("utf-8")