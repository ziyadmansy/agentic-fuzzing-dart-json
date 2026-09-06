from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic scalar fields
    id_ = draw(st.integers(min_value=-(2**31), max_value=2**31-1))
    # amount as string, sometimes numeric-looking, sometimes with spaces or signs
    amount_str = draw(
        st.one_of(
            st.integers(min_value=-999999, max_value=999999).map(str),
            st.floats(min_value=-9999, max_value=9999, allow_infinity=False, allow_nan=False).map(lambda f: f"{f:.4g}"),
            st.text(min_size=1, max_size=6, alphabet=st.characters(whitelist_categories=('Nd', 'Zs', 'Sm'), blacklist_characters=['"', '\\', '\n', '\r'])),
        )
    )
    # name: either null or string, sometimes empty, sometimes unicode, sometimes whitespace only
    name = draw(
        st.one_of(
            st.none(),
            st.text(min_size=0, max_size=10, alphabet=st.characters(blacklist_characters=['"', '\\', '\n', '\r'])),
        )
    )
    # status: one of the three strings, but sometimes with extra whitespace or uppercase to test strict enum parsing
    status_raw = draw(
        st.one_of(
            st.sampled_from(["active", "inactive", "unknown"]),
            st.sampled_from(["ACTIVE", "Inactive ", " unknown"]),
        )
    )
    # tags: array of strings, sometimes empty, sometimes with empty string, sometimes with unicode, sometimes with null (invalid per schema but syntactically valid JSON)
    tags_list = draw(
        st.lists(
            st.one_of(
                st.text(min_size=0, max_size=8, alphabet=st.characters(blacklist_characters=['"', '\\', '\n', '\r'])),
                st.none(),
            ),
            min_size=0,
            max_size=5,
        )
    )
    # child: either null or a nested record (one level only)
    # To avoid infinite recursion, child record fields are simpler (no child inside child)
    def child_record():
        cid = draw(st.integers(min_value=-(2**31), max_value=2**31-1))
        camount = draw(
            st.one_of(
                st.integers(min_value=-9999, max_value=9999).map(str),
                st.text(min_size=1, max_size=5, alphabet=st.characters(blacklist_characters=['"', '\\', '\n', '\r'])),
            )
        )
        cname = draw(
            st.one_of(
                st.none(),
                st.text(min_size=0, max_size=5, alphabet=st.characters(blacklist_characters=['"', '\\', '\n', '\r'])),
            )
        )
        cstatus = draw(st.sampled_from(["active", "inactive", "unknown"]))
        ctags = draw(
            st.lists(
                st.text(min_size=0, max_size=5, alphabet=st.characters(blacklist_characters=['"', '\\', '\n', '\r'])),
                min_size=0,
                max_size=3,
            )
        )
        # child inside child is always null
        # Build JSON text for child record
        # Use minimal spacing, no escaping needed due to character restrictions
        child_json = (
            '{"id":' + str(cid) +
            ',"amount":"' + camount + '"' +
            ',"name":' + ("null" if cname is None else '"' + cname + '"') +
            ',"status":"' + cstatus + '"' +
            ',"tags":[' + ",".join('"' + t + '"' for t in ctags) + ']' +
            ',"child":null}'
        )
        return child_json

    child_val = draw(st.one_of(st.just("null"), child_record()))

    # Compose top-level JSON text
    # Escape none needed because we restrict characters in strings
    # But we must handle null for name and tags can have nulls inside (which is invalid per schema but valid JSON)
    # For tags, render null as literal null, strings as quoted
    tags_json = "[" + ",".join("null" if t is None else '"' + t + '"' for t in tags_list) + "]"

    json_text = (
        '{"id":' + str(id_) +
        ',"amount":"' + amount_str + '"' +
        ',"name":' + ("null" if name is None else '"' + name + '"') +
        ',"status":"' + status_raw + '"' +
        ',"tags":' + tags_json +
        ',"child":' + child_val +
        '}'
    )
    return json_text.encode("utf-8")