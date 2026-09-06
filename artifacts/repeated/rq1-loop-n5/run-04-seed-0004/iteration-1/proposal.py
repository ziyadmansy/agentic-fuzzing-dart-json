from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_bool = st.one_of(json_true, json_false)

    # STRING as per grammar: '"' (ESC | SAFECODEPOINT)* '"'
    # We'll approximate ESC and SAFECODEPOINT by allowing safe unicode chars and some escapes
    # SAFECODEPOINT: ~["\\\u0000-\u001F]
    # We'll exclude control chars and backslash and quote from safe chars
    safe_char = st.characters(
        blacklist_characters=['"', '\\'],
        min_codepoint=0x20,
        max_codepoint=0x10FFFF,
    )
    # ESC: backslash + one of ["\\/bfnrt] or unicode escape \uXXXX
    # We'll generate either a simple escape or a unicode escape
    simple_esc = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
    unicode_esc = st.builds(
        lambda h1,h2,h3,h4: '\\u' + h1 + h2 + h3 + h4,
        st.sampled_from('0123456789abcdefABCDEF'),
        st.sampled_from('0123456789abcdefABCDEF'),
        st.sampled_from('0123456789abcdefABCDEF'),
        st.sampled_from('0123456789abcdefABCDEF'),
    )
    esc_seq = st.one_of(simple_esc, unicode_esc)

    # STRING content: mix of safe_char and esc_seq
    # To keep it simple, generate a list of length 0..10 of either safe_char or esc_seq
    string_content = st.lists(st.one_of(safe_char, esc_seq), max_size=10).map("".join)
    json_string = string_content.map(lambda s: f'"{s}"')

    # NUMBER: '-'? INT ('.' [0-9]+)? EXP?
    # INT: '0' | [1-9][0-9]*
    # EXP: [Ee][+-]?[0-9]+
    # We'll generate numbers as strings matching the pattern
    def number_str():
        sign = st.one_of(st.just(''), st.just('-'))
        int_part = st.one_of(st.just('0'), st.integers(min_value=1, max_value=10**6).map(str))
        frac_part = st.one_of(st.just(''), st.builds(lambda d: '.' + d, st.text(min_size=1, max_size=5, alphabet='0123456789')))
        exp_part = st.one_of(
            st.just(''),
            st.builds(
                lambda e, s, d: e + s + d,
                st.sampled_from(['E', 'e']),
                st.one_of(st.just(''), st.sampled_from(['+', '-'])),
                st.text(min_size=1, max_size=3, alphabet='0123456789'),
            ),
        )
        return st.builds(lambda sg, i, f, e: sg + i + f + e, sign, int_part, frac_part, exp_part)

    json_number = number_str()

    # Forward declaration for recursive structures
    # We'll use st.recursive to build obj and arr

    # obj : '{' pair (',' pair)* '}' | '{}'
    # pair : STRING ':' value
    # arr : '[' value (',' value)* ']' | '[]'
    # value : STRING | NUMBER | obj | arr | true | false | null

    # We'll define value recursively
    # To keep recursion bounded, max_depth=3

    # Define value base (non-recursive)
    json_value_base = st.one_of(json_string, json_number, json_bool, json_null)

    # Define pair: STRING ':' value
    @st.composite
    def json_pair(draw, value_strategy):
        k = draw(json_string)
        v = draw(value_strategy)
        return f"{k}:{v}"

    # Recursive strategy for value
    def json_value_strategy():
        return st.recursive(
            json_value_base,
            lambda children: st.one_of(
                # obj
                st.builds(
                    lambda pairs: "{" + ",".join(pairs) + "}" if pairs else "{}",
                    st.lists(json_pair(children), max_size=3),
                ),
                # arr
                st.builds(
                    lambda vals: "[" + ",".join(vals) + "]" if vals else "[]",
                    st.lists(children, max_size=3),
                ),
            ),
            max_leaves=10,
        )

    json_value = json_value_strategy()

    # The top-level json is value + EOF
    json_text = draw(json_value)
    return json_text.encode("utf-8")