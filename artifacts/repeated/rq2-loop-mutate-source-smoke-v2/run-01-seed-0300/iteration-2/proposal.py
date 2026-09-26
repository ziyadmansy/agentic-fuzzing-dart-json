from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status field
    statuses = ["active", "inactive", "unknown"]

    # Helper to produce a JSON string literal with proper escaping of " and \
    def json_string_literal(s: str) -> str:
        # Minimal escaping: replace \ and " with escaped versions
        s = s.replace("\\", "\\\\").replace('"', '\\"')
        # Also escape control characters (at least newline and tab)
        s = s.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
        return f'"{s}"'

    # Recursive generator for the "child" field, with depth limit 1
    def record(depth: int) -> st.SearchStrategy[str]:
        # id: integer
        id_strat = st.integers(min_value=-(2**31), max_value=2**31-1).map(str)

        # amount: string, but try some edge cases (empty, numeric strings, weird chars)
        amount_strat = st.one_of(
            st.text(min_size=0, max_size=10),
            st.integers(min_value=-10000, max_value=10000).map(str),
            st.just("0"),
            st.just(""),
            st.just("NaN"),
            st.just("Infinity"),
            st.just("-Infinity"),
            st.just("123.456"),
        )

        # name: string or null, but also try empty string, whitespace, or unusual unicode
        name_strat = st.one_of(
            st.none(),
            st.text(min_size=0, max_size=10),
            st.just(""),
            st.just(" "),
            st.just("\u0000"),  # null char
            st.just("\u2028"),  # line separator
            st.just("\u2029"),  # paragraph separator
        )

        # status: one of the three strings, but also try wrong casing or similar strings
        status_strat = st.one_of(
            st.sampled_from(statuses),
            st.sampled_from([s.upper() for s in statuses]),
            st.sampled_from([s.capitalize() for s in statuses]),
            st.just("active "),  # trailing space
            st.just("inactive\n"),  # newline
            st.just("unknown?"),
        )

        # tags: array of strings, try empty array, array with empty string, or weird strings
        tags_strat = st.lists(
            st.one_of(
                st.text(min_size=0, max_size=5),
                st.just(""),
                st.just(" "),
                st.just("\u0000"),
                st.just("\n"),
            ),
            min_size=0,
            max_size=5,
        )

        # child: either null or a nested record (only one level deep)
        if depth >= 1:
            child_strat = st.just("null")
        else:
            child_strat = st.one_of(
                st.just("null"),
                record(depth + 1),
            )

        # Compose the JSON object string with fields in fixed order for consistency
        def build_json_obj(
            id_s, amount_s, name_s, status_s, tags_s, child_s
        ) -> str:
            # id: integer literal
            id_json = id_s

            # amount: string literal
            amount_json = json_string_literal(amount_s)

            # name: null or string literal
            if name_s is None:
                name_json = "null"
            else:
                name_json = json_string_literal(name_s)

            # status: string literal (even if invalid)
            status_json = json_string_literal(status_s)

            # tags: array of string literals
            tags_json = "[" + ",".join(json_string_literal(t) for t in tags_s) + "]"

            # child: either "null" or nested JSON object string
            child_json = child_s

            return (
                "{"
                + f'"id":{id_json},'
                + f'"amount":{amount_json},'
                + f'"name":{name_json},'
                + f'"status":{status_json},'
                + f'"tags":{tags_json},'
                + f'"child":{child_json}'
                + "}"
            )

        return st.tuples(
            id_strat,
            amount_strat,
            name_strat,
            status_strat,
            tags_strat,
            child_strat,
        ).map(lambda tpl: build_json_obj(*tpl))

    # Generate top-level record (depth 0)
    json_str = draw(record(0))
    return json_str.encode("utf-8")