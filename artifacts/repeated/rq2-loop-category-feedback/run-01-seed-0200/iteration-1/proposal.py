from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status enum
    statuses = ["active", "inactive", "unknown"]

    # Recursive record generator with bounded depth
    def record(depth=0):
        # id: integer
        id_strat = st.integers(min_value=-(2**31), max_value=2**31-1)
        # amount: string, but test edge cases like numeric strings, empty, whitespace, and weird unicode
        amount_strat = st.one_of(
            st.text(min_size=0, max_size=10),
            st.just("0"),
            st.just("0.0"),
            st.just("-0"),
            st.just("1e10"),
            st.just(""),
            st.just(" "),
            st.just("\u200b"),  # zero width space
        )
        # name: string or null, test empty string, whitespace, unicode, or null
        name_strat = st.one_of(
            st.none(),
            st.text(min_size=0, max_size=10),
            st.just(""),
            st.just(" "),
            st.just("\u200b"),
        )
        # status: one of the three strings, but also test off-by-one or similar strings to cause divergence
        # We produce mostly valid, but sometimes slightly off strings to test enum parsing
        status_strat = st.one_of(
            st.sampled_from(statuses),
            st.text(min_size=1, max_size=8).filter(lambda s: s not in statuses),
        )
        # tags: array of strings, test empty array, array with empty string, array with null (should be invalid), array with unicode strings
        tags_strat = st.lists(
            st.text(min_size=0, max_size=5),
            min_size=0,
            max_size=5,
        )
        # child: either null or a nested record (only one level deep)
        if depth >= 1:
            child_strat = st.none()
        else:
            child_strat = st.one_of(st.none(), record(depth + 1))

        # Compose the JSON object as string
        # We will build the JSON text manually, escaping strings minimally (only backslash and quote)
        def json_escape(s: str) -> str:
            # minimal JSON string escaping for " and \ and control chars
            # We do not import json, so do a minimal escape:
            # Replace \ with \\, " with \"
            # Replace control chars with \u00XX
            res = []
            for c in s:
                o = ord(c)
                if c == '"':
                    res.append('\\"')
                elif c == '\\':
                    res.append('\\\\')
                elif o < 0x20:
                    res.append('\\u%04x' % o)
                else:
                    res.append(c)
            return ''.join(res)

        id_val = draw(id_strat)
        amount_val = draw(amount_strat)
        name_val = draw(name_strat)
        status_val = draw(status_strat)
        tags_val = draw(tags_strat)
        child_val = draw(child_strat)

        # Build JSON fields with minimal spacing
        # id: integer (no quotes)
        id_json = str(id_val)

        # amount: string (quoted)
        amount_json = '"' + json_escape(amount_val) + '"'

        # name: string or null
        if name_val is None:
            name_json = "null"
        else:
            name_json = '"' + json_escape(name_val) + '"'

        # status: string (quoted)
        status_json = '"' + json_escape(status_val) + '"'

        # tags: array of strings
        tags_items = []
        for t in tags_val:
            tags_items.append('"' + json_escape(t) + '"')
        tags_json = "[" + ",".join(tags_items) + "]"

        # child: either null or nested record JSON
        if child_val is None:
            child_json = "null"
        else:
            child_json = child_val

        # Compose full JSON object string
        obj = (
            '{'
            + '"id":' + id_json + ','
            + '"amount":' + amount_json + ','
            + '"name":' + name_json + ','
            + '"status":' + status_json + ','
            + '"tags":' + tags_json + ','
            + '"child":' + child_json
            + '}'
        )
        return obj.encode("utf-8")

    return record()