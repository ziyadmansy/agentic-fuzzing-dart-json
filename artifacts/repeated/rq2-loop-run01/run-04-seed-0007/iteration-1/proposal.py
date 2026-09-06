from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status enum
    statuses = ["active", "inactive", "unknown"]

    # Helper: produce a JSON string literal from a Python string (with minimal escaping)
    def json_string(s: str) -> str:
        # Escape backslash and double quote and control chars minimally
        # Hypothesis strings are unicode, but we keep it simple here
        s = s.replace("\\", "\\\\").replace('"', '\\"')
        # Escape control chars (U+0000 to U+001F)
        def esc_char(c):
            o = ord(c)
            if o < 0x20:
                return "\\u%04x" % o
            return c
        s = "".join(esc_char(c) for c in s)
        return '"' + s + '"'

    # Compose JSON for a Record, bounded recursion depth 0 or 1
    def record_json(depth: int) -> st.SearchStrategy[str]:
        # id: integer (always present)
        id_strat = st.integers(min_value=-(2**31), max_value=2**31-1).map(str)

        # amount: string (always present)
        # To induce divergence, sometimes produce numeric strings, sometimes empty, sometimes with spaces
        amount_strat = st.one_of(
            st.text(min_size=1, max_size=10).filter(lambda s: all(c not in '"\\' for c in s)),  # simple string no quotes or backslash
            st.just("0"),
            st.just("0.0"),
            st.just(" 123 "),  # spaces around digits
            st.just("1e10"),
            st.just(""),
        ).map(json_string)

        # name: string or null
        # To induce divergence, sometimes produce null, sometimes empty string, sometimes string with unicode
        name_strat = st.one_of(
            st.none().map(lambda _: "null"),
            st.text(min_size=0, max_size=20).map(json_string),
        )

        # status: one of the three strings, but sometimes produce a wrong string to induce divergence
        status_strat = st.one_of(
            st.sampled_from(statuses).map(json_string),
            # introduce a wrong enum string sometimes
            st.text(min_size=1, max_size=10).filter(lambda s: s not in statuses and all(c not in '"\\' for c in s)).map(json_string),
        )

        # tags: array of strings (always present)
        # To induce divergence, sometimes empty array, sometimes array with empty strings, sometimes array with unicode
        tags_strat = st.lists(
            st.text(min_size=0, max_size=10).filter(lambda s: all(c not in '"\\' for c in s)).map(json_string),
            min_size=0,
            max_size=5,
        ).map(lambda lst: "[" + ",".join(lst) + "]")

        # child: null or Record (one level recursion only)
        if depth > 0:
            child_strat = st.one_of(
                st.just("null"),
                record_json(depth - 1),
            )
        else:
            child_strat = st.just("null")

        # Now build the JSON object string with all fields present
        # To induce divergence, sometimes omit a field by replacing with empty string? No, spec says all fields always present.
        # Instead, sometimes produce wrong types for fields (e.g. number instead of string for amount)
        # But we must keep syntactically valid JSON objects with all six fields present.

        # To induce divergence, we can sometimes produce wrong types for fields:
        # id: always integer (stringified)
        # amount: sometimes string, sometimes number (unquoted)
        # name: string or null
        # status: string (enum or wrong string)
        # tags: array of strings (sometimes empty)
        # child: null or record

        # amount can be string or number (unquoted)
        amount_type = draw(st.sampled_from(["string", "number"]))
        if amount_type == "string":
            amount_val = draw(amount_strat)
        else:
            # number as JSON number literal (integer or float)
            amount_val = draw(
                st.one_of(
                    st.integers(min_value=-1000000, max_value=1000000).map(str),
                    st.floats(allow_infinity=False, allow_nan=False, width=32).map(lambda f: format(f, "g")),
                )
            )

        # name can be string or null
        name_val = draw(name_strat)

        # status string (enum or wrong)
        status_val = draw(status_strat)

        # tags array
        tags_val = draw(tags_strat)

        # child
        child_val = draw(child_strat)

        # id
        id_val = draw(id_strat)

        # Build JSON object string with fields in fixed order
        # Use no extra spaces to keep consistent
        json_obj = (
            '{'
            + '"id":' + id_val + ','
            + '"amount":' + amount_val + ','
            + '"name":' + name_val + ','
            + '"status":' + status_val + ','
            + '"tags":' + tags_val + ','
            + '"child":' + child_val
            + '}'
        )
        return json_obj

    # Generate record with depth 1 (one level recursion)
    json_text = draw(record_json(depth=1))
    return json_text.encode("utf-8")