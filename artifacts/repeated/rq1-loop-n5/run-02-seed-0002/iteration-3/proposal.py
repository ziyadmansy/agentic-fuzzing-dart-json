from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: roughly valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then JSON-encode them to ensure correctness
    # but since we cannot import json or use eval/exec, we build strings manually.
    # We'll generate strings with safe codepoints and some escapes.
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and quotes/backslash)
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)  # control chars
        )
        # Include some escapes
        escapes = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Compose string pieces: either safe char or escape sequence
        pieces = st.lists(st.one_of(safe_chars.map(lambda c: c), escapes), min_size=0, max_size=20)
        return pieces.map(lambda chars: '"' + ''.join(chars) + '"')

    json_string_st = json_string()

    # NUMBER: generate numbers as strings matching the grammar
    # We'll generate floats and ints and format them accordingly
    def json_number():
        # Generate an int part
        int_part = st.one_of(
            st.just("0"),
            st.integers(min_value=1, max_value=10**6).map(str)
        )
        # Optional fractional part
        frac_part = st.one_of(
            st.just(""),
            st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False)
            .map(lambda f: ("%.10f" % f).lstrip("0") if f != 0 else "")
        )
        # Optional exponent part
        exp_part = st.one_of(
            st.just(""),
            st.integers(min_value=-10, max_value=10).map(lambda e: "e%+d" % e)
        )
        # Compose number string
        def compose_number(t):
            i, f, e = t
            # f might be empty or like ".xxxx"
            if f == "":
                return i + e
            # f might be like ".xxxx" or "0.xxxx" - ensure it starts with '.'
            if f.startswith("."):
                frac = f
            else:
                # f might be like "0.1234567890" from floats, convert to fractional part
                frac = f[f.find('.'):] if '.' in f else ""
            return i + frac + e

        # To simplify, generate a float and format it as JSON number string
        # We'll generate floats directly and format them
        float_num = st.floats(
            min_value=-1e6, max_value=1e6,
            allow_infinity=False, allow_nan=False
        ).map(lambda f: format(f, '.10g'))
        return float_num

    json_number_st = json_number()

    # Forward declaration for recursive structures
    # We'll define value recursively
    def json_value():
        # We'll use recursive strategy to build nested objects and arrays
        base = st.one_of(
            json_string_st,
            json_number_st,
            json_null,
            json_true,
            json_false,
        )

        # Recursive containers
        def json_obj():
            # pair: STRING ':' value
            pair = st.tuples(json_string_st, json_value()).map(lambda p: p[0] + ":" + p[1])
            # object: '{' pair (',' pair)* '}' or '{}'
            return st.lists(pair, max_size=5).map(
                lambda pairs: "{" + (",".join(pairs) if pairs else "") + "}"
            )

        def json_arr():
            # array: '[' value (',' value)* ']' or '[]'
            return st.lists(json_value(), max_size=5).map(
                lambda vals: "[" + (",".join(vals) if vals else "") + "]"
            )

        return st.recursive(
            base,
            lambda children: st.one_of(json_obj(), json_arr()),
            max_leaves=10,
        )

    # Generate the full JSON text and encode as bytes
    json_text = json_value()
    s = draw(json_text)
    return s.encode("utf-8")