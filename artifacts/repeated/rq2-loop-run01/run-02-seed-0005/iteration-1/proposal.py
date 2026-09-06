from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status enum
    statuses = ["active", "inactive", "unknown"]

    # Helper to produce a JSON string literal with proper escaping of quotes and backslashes
    def json_string(s: str) -> str:
        # Minimal escaping: backslash and double quote
        esc = s.replace("\\", "\\\\").replace("\"", "\\\"")
        return f"\"{esc}\""

    # Recursive record generator with bounded depth (max 1 level of recursion)
    def record(depth: int) -> st.SearchStrategy[str]:
        # id: integer (always present)
        id_strat = st.integers(min_value=-(2**31), max_value=2**31-1).map(str)

        # amount: string (always present)
        # To induce divergence, sometimes produce numeric strings, sometimes strings with spaces, etc.
        amount_strat = st.one_of(
            st.decimals(min_value=0, max_value=1e9, allow_infinity=False, allow_nan=False).map(lambda d: format(d, "f")),
            st.text(min_size=1, max_size=10).filter(lambda s: all(c not in "\"\\\b\f\n\r\t" for c in s)),  # safe text without escapes
        )

        # name: string or null
        # To induce divergence, sometimes produce null, sometimes empty string, sometimes normal string
        name_strat = st.one_of(
            st.none().map(lambda _: "null"),
            st.text(min_size=0, max_size=15).map(json_string),
        )

        # status: one of "active", "inactive", "unknown"
        # To induce divergence, sometimes produce valid enum, sometimes produce a string close to enum but invalid
        status_strat = st.one_of(
            st.sampled_from(statuses).map(json_string),
            st.text(min_size=1, max_size=8).filter(lambda s: s not in statuses).map(json_string),
        )

        # tags: array of strings (always present)
        # To induce divergence, sometimes empty array, sometimes array with empty string, sometimes array with normal strings
        tags_strat = st.lists(
            st.text(min_size=0, max_size=10).filter(lambda s: all(c not in "\"\\\b\f\n\r\t" for c in s)).map(json_string),
            min_size=0,
            max_size=5,
        ).map(lambda lst: "[" + ",".join(lst) + "]")

        # child: either null or a record (one level recursion only)
        if depth == 0:
            child_strat = st.just("null")
        else:
            # To induce divergence, sometimes produce null, sometimes produce a record
            child_strat = st.one_of(
                st.just("null"),
                record(depth - 1),
            )

        # Compose the record fields as JSON text
        def compose(id_s, amount_s, name_s, status_s, tags_s, child_s) -> str:
            # name_s is either "null" or a quoted string
            # status_s is quoted string (valid or invalid)
            # amount_s is string (not quoted yet)
            # id_s is string (not quoted yet)
            # tags_s is JSON array string
            # child_s is JSON object string or "null"

            # Compose JSON object with fields in fixed order
            # Intentionally produce some fields with wrong types sometimes to induce divergence:
            # For example, sometimes produce amount as a JSON number (unquoted), sometimes as a string (quoted)
            # But amount_s is string representation of decimal or text, so we can decide here to quote or not

            # Introduce a small chance to produce amount as JSON number (unquoted) or string (quoted)
            # This is done by checking if amount_s looks like a decimal number
            try:
                float(amount_s)
                amount_field = amount_s  # unquoted number
            except Exception:
                amount_field = json_string(amount_s)  # quoted string

            # Similarly, for id, always unquoted integer string

            # name_s is either "null" or quoted string (already prepared)

            # status_s is quoted string (already prepared)

            # tags_s is JSON array string (already prepared)

            # child_s is JSON object string or "null"

            return (
                "{" +
                f"\"id\":{id_s}," +
                f"\"amount\":{amount_field}," +
                f"\"name\":{name_s}," +
                f"\"status\":{status_s}," +
                f"\"tags\":{tags_s}," +
                f"\"child\":{child_s}" +
                "}"
            )

        return st.tuples(id_strat, amount_strat, name_strat, status_strat, tags_strat, child_strat).map(
            lambda t: compose(*t)
        )

    # Generate a record with depth 1 (one level of child recursion allowed)
    json_text = draw(record(depth=1))

    # Return as bytes
    return json_text.encode("utf-8")