from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON string escaper for Hypothesis-generated strings (minimal, safe subset)
    def json_string(s: str) -> str:
        # Escape backslash and double quote, and control chars minimally
        s = s.replace('\\', '\\\\').replace('"', '\\"')
        s = s.replace('\b', '\\b').replace('\f', '\\f').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
        # Remove other control chars (U+0000 to U+001F) by replacing with space
        s = ''.join(ch if ' ' <= ch <= '\uFFFF' else ' ' for ch in s)
        return '"' + s + '"'

    # Generate an integer id (0 to 10000)
    id_str = draw(st.integers(min_value=0, max_value=10000).map(str))

    # Generate amount as a string that looks like a decimal number, but sometimes with odd formats
    # (e.g. leading zeros, plus sign, or exponent) to provoke parsing differences
    def gen_amount_str():
        # Choose among normal decimal, leading zeros, plus sign, exponent, or empty string (edge)
        choice = draw(st.integers(min_value=0, max_value=4))
        if choice == 0:
            # normal decimal string, e.g. "123.45"
            whole = draw(st.integers(min_value=0, max_value=9999))
            frac = draw(st.integers(min_value=0, max_value=99))
            return f"{whole}.{frac:02d}"
        elif choice == 1:
            # leading zeros, e.g. "000123.45"
            whole = draw(st.integers(min_value=0, max_value=9999))
            frac = draw(st.integers(min_value=0, max_value=99))
            return f"{whole:05d}.{frac:02d}"
        elif choice == 2:
            # plus sign, e.g. "+123.45"
            whole = draw(st.integers(min_value=0, max_value=9999))
            frac = draw(st.integers(min_value=0, max_value=99))
            return f"+{whole}.{frac:02d}"
        elif choice == 3:
            # exponent notation, e.g. "1.23e3"
            base_whole = draw(st.integers(min_value=0, max_value=9))
            base_frac = draw(st.integers(min_value=0, max_value=99))
            exp = draw(st.integers(min_value=-5, max_value=5))
            return f"{base_whole}.{base_frac:02d}e{exp}"
        else:
            # empty string (edge case)
            return ""

    amount_str = gen_amount_str()

    # name: either null or a string, sometimes empty or with unicode
    name_val = draw(st.one_of(
        st.none(),
        st.text(min_size=0, max_size=20).map(json_string)
    ))
    # if null, output literal null, else string
    name_str = "null" if name_val is None else name_val

    # status: one of "active", "inactive", "unknown", or sometimes a string with different case or extra whitespace
    status_base = draw(st.sampled_from(["active", "inactive", "unknown"]))
    status_variant = draw(st.integers(min_value=0, max_value=3))
    if status_variant == 0:
        status_str = json_string(status_base)
    elif status_variant == 1:
        # uppercase variant
        status_str = json_string(status_base.upper())
    elif status_variant == 2:
        # trailing space
        status_str = json_string(status_base + " ")
    else:
        # leading space
        status_str = json_string(" " + status_base)

    # tags: array of strings, sometimes empty, sometimes with empty strings or strings with commas/quotes
    def gen_tag():
        # strings with possible commas, quotes, or empty
        return draw(st.one_of(
            st.just(""),
            st.text(min_size=0, max_size=10).map(json_string),
            st.sampled_from([json_string(","), json_string("\""), json_string("tag1"), json_string("tag,2")])
        ))

    tags_len = draw(st.integers(min_value=0, max_value=5))
    tags_list = [gen_tag() for _ in range(tags_len)]
    tags_str = "[" + ",".join(tags_list) + "]"

    # child: either null or a nested record (one level only)
    # To avoid infinite recursion, child record fields are simpler and do not nest further.
    def gen_child():
        # id integer
        cid = draw(st.integers(min_value=0, max_value=10000).map(str))
        # amount string (simple decimal)
        camount = draw(st.floats(min_value=0, max_value=10000, allow_nan=False, allow_infinity=False)).map(lambda f: f"{f:.2f}")
        # name null or string
        cname_val = draw(st.one_of(st.none(), st.text(min_size=0, max_size=10).map(json_string)))
        cname_str = "null" if cname_val is None else cname_val
        # status one of exact allowed strings only (no variants)
        cstatus = draw(st.sampled_from(["active", "inactive", "unknown"]))
        cstatus_str = json_string(cstatus)
        # tags empty array or single tag
        ctags_str = draw(st.sampled_from(["[]", "[" + json_string("childtag") + "]"]))
        # child null (no further nesting)
        cchild_str = "null"
        return (
            "{" +
            f"\"id\":{cid}," +
            f"\"amount\":\"{camount}\"," +
            f"\"name\":{cname_str}," +
            f"\"status\":{cstatus_str}," +
            f"\"tags\":{ctags_str}," +
            f"\"child\":{cchild_str}" +
            "}"
        )

    child_val = draw(st.one_of(st.just("null"), gen_child()))

    # Compose full JSON object string
    json_obj = (
        "{" +
        f"\"id\":{id_str}," +
        f"\"amount\":\"{amount_str}\"," +
        f"\"name\":{name_str}," +
        f"\"status\":{status_str}," +
        f"\"tags\":{tags_str}," +
        f"\"child\":{child_val}" +
        "}"
    )

    return json_obj.encode("utf-8")