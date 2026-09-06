from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic atomic fields as strings (for JSON text)
    # id: integer (as number)
    id_str = draw(st.integers(min_value=-(2**31), max_value=2**31-1).map(str))

    # amount: string, but vary contents to include edge cases (empty, numeric string, special chars)
    amount_str = draw(
        st.one_of(
            st.text(min_size=0, max_size=10),
            st.integers(min_value=-100000, max_value=100000).map(str),
            st.just(""),
            st.just("0"),
            st.just("123.45"),
            st.just("-0"),
            st.just("null"),
            st.just("true"),
            st.just("false"),
            st.just("NaN"),
            st.just("Infinity"),
            st.just("-Infinity"),
        )
    )
    # JSON string literal for amount (always string)
    def json_string(s):
        # Minimal escaping for JSON string: backslash and quote
        s = s.replace('\\', '\\\\').replace('"', '\\"')
        # Also escape control chars (replace with \u00XX)
        def esc_char(c):
            if ord(c) < 0x20:
                return '\\u%04x' % ord(c)
            return c
        s = ''.join(esc_char(c) for c in s)
        return '"' + s + '"'
    amount_json = json_string(amount_str)

    # name: string or null, vary with null, empty string, unicode, control chars
    name_val = draw(
        st.one_of(
            st.none(),
            st.text(min_size=0, max_size=15),
            st.just(""),
            st.just("null"),
            st.just("true"),
            st.just("false"),
            st.just("\u0000\u0001\u0002"),
            st.just("名前"),  # unicode
        )
    )
    if name_val is None:
        name_json = "null"
    else:
        name_json = json_string(name_val)

    # status: one of "active", "inactive", "unknown"
    # Also try to inject slight deviations to test enum parsing:
    # e.g. uppercase, trailing spaces, null (should be rejected but maybe some accept)
    status_val = draw(
        st.one_of(
            st.sampled_from(["active", "inactive", "unknown"]),
            st.just("Active"),
            st.just("inactive "),
            st.just("UNKNOWN"),
            st.none(),
        )
    )
    if status_val is None:
        status_json = "null"
    else:
        status_json = json_string(status_val)

    # tags: array of strings, vary empty, null strings inside, unicode, control chars
    # Also try to produce some non-string elements to test type strictness
    def tag_element():
        return draw(
            st.one_of(
                st.text(min_size=0, max_size=10),
                st.just(""),
                st.just("null"),
                st.just("true"),
                st.just("false"),
                st.integers(min_value=-10, max_value=10).map(str),
                st.none(),
                st.just("\u0000"),
                st.just("tag\u1234"),
            )
        )
    tags_list = draw(st.lists(tag_element(), min_size=0, max_size=5))

    # Build JSON array for tags, forcing string elements or null or numbers as text
    def json_array_of_strings_or_nulls(lst):
        parts = []
        for v in lst:
            if v is None:
                parts.append("null")
            else:
                # Try to detect if v looks like a number string to emit as number or string
                # But to maximize divergence, always emit strings for tags elements
                parts.append(json_string(v))
        return "[" + ",".join(parts) + "]"
    tags_json = json_array_of_strings_or_nulls(tags_list)

    # child: null or a nested record (one level recursion)
    # To avoid infinite recursion, only one level deep
    # Compose child record similarly but simpler: no further child inside
    def child_record():
        # id integer
        cid = draw(st.integers(min_value=0, max_value=1000).map(str))
        # amount string (simple)
        camount = draw(st.text(min_size=0, max_size=5).map(json_string))
        # name string or null
        cname = draw(st.one_of(st.none(), st.text(min_size=0, max_size=5))).map(
            lambda x: "null" if x is None else json_string(x)
        )
        # status strict enum only here to reduce complexity
        cstatus = draw(st.sampled_from(["active", "inactive", "unknown"])).map(json_string)
        # tags empty array or small array of simple strings
        ctags = draw(
            st.lists(st.text(min_size=0, max_size=3), min_size=0, max_size=2)
        ).map(lambda lst: "[" + ",".join(json_string(s) for s in lst) + "]")
        # child is null here (no deeper recursion)
        return (
            '{'
            + '"id":' + cid + ','
            + '"amount":' + camount + ','
            + '"name":' + cname + ','
            + '"status":' + cstatus + ','
            + '"tags":' + ctags + ','
            + '"child":null'
            + '}'
        )

    child_val = draw(st.one_of(st.none(), child_record()))
    if child_val is None:
        child_json = "null"
    else:
        child_json = child_val

    # Compose full JSON object with all fields in order
    json_obj = (
        '{'
        + '"id":' + id_str + ','
        + '"amount":' + amount_json + ','
        + '"name":' + name_json + ','
        + '"status":' + status_json + ','
        + '"tags":' + tags_json + ','
        + '"child":' + child_json
        + '}'
    )

    return json_obj.encode("utf-8")