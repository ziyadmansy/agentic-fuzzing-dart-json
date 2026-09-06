from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants
    STATUS_VALUES = ['"active"', '"inactive"', '"unknown"']

    # Helper: produce a JSON string literal with proper escaping of quotes and backslashes
    def json_string(s: str) -> str:
        # Minimal escaping for " and \ to keep JSON valid
        return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

    # Recursive record generator, bounded to depth 1 for "child"
    def record(depth: int) -> st.SearchStrategy[str]:
        # id: integer
        id_strat = st.integers(min_value=-(2**31), max_value=2**31-1).map(str)

        # amount: string, but we will generate some edge cases that look numeric but are strings
        # Also try some tricky strings that might confuse parsers (leading zeros, signs, decimals)
        amount_strat = st.one_of(
            st.text(min_size=1, max_size=10).filter(lambda s: all(c not in s for c in '\n\r\t"\\')),  # safe strings
            st.sampled_from([
                "0", "00", "01", "-0", "+0", "0.0", "00.00", "1e10", "-1e-10", " 123", "123 ", " 123 ", "0x10"
            ])
        ).map(json_string)

        # name: string or null, but also try empty string, whitespace, or tricky unicode
        name_strat = st.one_of(
            st.none().map(lambda _: "null"),
            st.text(min_size=0, max_size=20).filter(lambda s: all(c not in s for c in '\n\r\t"\\')).map(json_string),
            st.sampled_from(['""', '" "', '"\u0000"', '"\u2028"', '"\u2029"'])  # some special unicode chars allowed in JSON strings
        )

        # status: one of the three strings, but also try upper/lower case variants or misspellings
        status_strat = st.one_of(
            st.sampled_from(STATUS_VALUES),
            st.sampled_from(['"Active"', '"INACTIVE"', '"unknown "', '"unknown"', '"unkn0wn"', '"active\n"'])
        )

        # tags: array of strings, but try empty array, array with null, array with numbers as strings, or empty strings
        tag_strat = st.lists(
            st.one_of(
                st.text(min_size=0, max_size=10).filter(lambda s: all(c not in s for c in '\n\r\t"\\')).map(json_string),
                st.just("null"),  # invalid element type, might cause divergence
                st.sampled_from(['"tag1"', '"tag2"', '""', '" "'])
            ),
            min_size=0, max_size=5
        ).map(lambda lst: "[" + ",".join(lst) + "]")

        # child: either null or a nested record (depth limited to 1)
        if depth >= 1:
            child_strat = st.just("null")
        else:
            child_strat = st.one_of(
                st.just("null"),
                record(depth + 1)
            )

        # Compose the record JSON object string
        def make_record(id_s, amount_s, name_s, status_s, tags_s, child_s) -> str:
            # Compose fields in fixed order with no extra spaces to keep JSON minimal
            return (
                '{'
                + '"id":' + id_s + ','
                + '"amount":' + amount_s + ','
                + '"name":' + name_s + ','
                + '"status":' + status_s + ','
                + '"tags":' + tags_s + ','
                + '"child":' + child_s
                + '}'
            )

        return st.tuples(id_strat, amount_strat, name_strat, status_strat, tag_strat, child_strat).map(
            lambda t: make_record(*t)
        )

    # Generate top-level record (depth 0)
    json_text = draw(record(0))
    return json_text.encode('utf-8')