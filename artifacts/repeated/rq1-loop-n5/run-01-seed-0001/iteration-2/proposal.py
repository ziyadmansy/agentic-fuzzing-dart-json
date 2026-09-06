from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # JSON string: use Hypothesis built-in strings with safe codepoints, escape as needed
    # We generate Python strings and then json-encode them to ensure correctness
    # But since we cannot import json, we manually escape quotes and backslashes
    def json_string():
        s = draw(st.text(
            st.characters(
                blacklist_characters=['"', '\\', '\u0000', '\u0001', '\u0002', '\u0003', '\u0004',
                                      '\u0005', '\u0006', '\u0007', '\u0008', '\u000b', '\u000c',
                                      '\u000e', '\u000f', '\u0010', '\u0011', '\u0012', '\u0013',
                                      '\u0014', '\u0015', '\u0016', '\u0017', '\u0018', '\u0019',
                                      '\u001a', '\u001b', '\u001c', '\u001d', '\u001e', '\u001f'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            ),
            max_size=20,
        ))
        # Escape backslash and quote
        s = s.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{s}"'

    json_string_st = st.deferred(json_string)

    # JSON number: use Hypothesis floats converted to JSON number strings
    def json_number():
        # Generate floats that are finite and not NaN
        f = draw(st.floats(allow_infinity=False, allow_nan=False, width=32))
        # Format as JSON number string, avoiding scientific notation for simplicity
        # But allow scientific notation as JSON permits it
        # Use repr to get a valid JSON number representation
        s = repr(f)
        # repr can produce 'inf', 'nan' - filtered by strategy above
        # repr can produce '1e-07' which is valid JSON number
        return s

    json_number_st = st.deferred(json_number)

    # Recursive JSON value strategy
    def json_value():
        return st.recursive(
            base=st.one_of(
                json_string_st,
                json_number_st,
                json_null,
                json_true,
                json_false,
            ),
            extend=lambda children: st.one_of(
                # object: { pair (, pair)* } or {}
                st.builds(
                    lambda pairs: "{" + ",".join(pairs) + "}",
                    st.lists(
                        st.tuples(
                            # pair: STRING : value
                            st.deferred(json_string),
                            children,
                        ).map(lambda t: f"{t[0]}:{t[1]}"),
                        max_size=3,
                    ),
                ),
                # array: [ value (, value)* ] or []
                st.builds(
                    lambda values: "[" + ",".join(values) + "]",
                    st.lists(children, max_size=3),
                ),
            ),
            max_leaves=10,
        )

    val = draw(json_value())
    return val.encode("utf-8")