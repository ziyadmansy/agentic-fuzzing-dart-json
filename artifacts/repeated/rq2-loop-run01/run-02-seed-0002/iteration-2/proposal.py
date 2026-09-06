from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for enum values
    statuses = ["active", "inactive", "unknown"]

    # Helper to produce a JSON string literal with proper escaping of quotes and backslashes
    def json_string(s: str) -> str:
        # Escape backslash and double quotes minimally
        s = s.replace("\\", "\\\\").replace('"', '\\"')
        # Also escape control characters minimally (newline, tab)
        s = s.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
        return f'"{s}"'

    # Recursive record generator with depth limit
    def record(depth: int) -> st.SearchStrategy[str]:
        # id: integer
        id_strat = st.integers(min_value=-(2**31), max_value=2**31-1).map(str)

        # amount: string, allow numeric strings, empty string, or strings with spaces, signs, decimals
        # Also allow some invalid numeric strings to test parsing differences
        amount_strat = st.one_of(
            st.integers(min_value=-999999, max_value=999999).map(str),
            st.floats(allow_infinity=False, allow_nan=False, width=32).map(lambda f: format(f, 'g')),
            st.text(min_size=0, max_size=5).filter(lambda s: all(c not in '"\\' for c in s)),  # simple strings without quotes or backslash
            st.sampled_from(["", "  ", "+123", "-0.0", "NaN", "inf", "-inf", "0x10", "1e10"])
        )

        # name: string or null, allow empty string, unicode, or null
        name_strat = st.one_of(
            st.none().map(lambda _: "null"),
            st.text(min_size=0, max_size=10).map(json_string)
        )

        # status: one of enum strings, or sometimes an invalid string to test rejection
        status_strat = st.one_of(
            st.sampled_from(statuses).map(json_string),
            st.text(min_size=1, max_size=8).filter(lambda s: s not in statuses and all(c not in '"\\' for c in s)).map(json_string)
        )

        # tags: array of strings, allow empty array, array with empty strings, or strings with spaces
        tags_strat = st.lists(
            st.text(min_size=0, max_size=5).filter(lambda s: all(c not in '"\\' for c in s)).map(json_string),
            min_size=0, max_size=4
        ).map(lambda lst: "[" + ",".join(lst) + "]")

        # child: null or nested record (depth limited)
        if depth <= 0:
            child_strat = st.just("null")
        else:
            child_strat = st.one_of(
                st.just("null"),
                record(depth - 1)
            )

        # Compose fields in random order to test order independence
        # But always produce all six fields present (per spec)
        # We'll produce a dict of fieldname -> json text, then join with commas

        # Draw all fields
        id_val = draw(id_strat)
        amount_val = draw(amount_strat)
        name_val = draw(name_strat)
        status_val = draw(status_strat)
        tags_val = draw(tags_strat)
        child_val = draw(child_strat)

        fields = {
            "id": id_val,
            "amount": json_string(amount_val) if not amount_val.startswith('"') else amount_val,
            "name": name_val,
            "status": status_val,
            "tags": tags_val,
            "child": child_val,
        }

        # Shuffle field order
        keys = list(fields.keys())
        draw(st.permutations(keys))
        keys = draw(st.permutations(keys))

        # Build JSON object string
        obj_str = "{" + ",".join(json_string(k) + ":" + fields[k] for k in keys) + "}"

        return obj_str

    # Generate top-level record with max depth 1 (one level of recursion)
    json_text = draw(record(depth=1))

    return json_text.encode("utf-8")