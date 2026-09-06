from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base primitives as JSON text
    def json_string(s: str) -> str:
        # Escape backslash and double quotes minimally for JSON string correctness
        esc = s.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{esc}"'

    def json_integer(i: int) -> str:
        return str(i)

    def json_null() -> str:
        return "null"

    def json_array(elems: list[str]) -> str:
        return "[" + ",".join(elems) + "]"

    def json_object(pairs: list[tuple[str, str]]) -> str:
        # pairs: list of (key, json_value_text)
        # keys must be strings, so quote them
        items = [json_string(k) + ":" + v for k, v in pairs]
        return "{" + ",".join(items) + "}"

    # Allowed status values as strings
    status_values = ["active", "inactive", "unknown"]

    # Recursive record generator: returns JSON text of a record or "null"
    # Limit recursion depth to 1 (child can be null or record with child=null)
    def gen_record(depth: int) -> st.SearchStrategy[str]:
        # id: integer (allow some edge cases: negative, zero, large)
        id_strat = st.integers(min_value=-1000, max_value=1000).map(json_integer)

        # amount: string, allow numeric strings, empty, weird chars
        amount_strat = st.text(min_size=0, max_size=10).map(json_string)

        # name: string or null, allow empty string, unicode, or null
        name_strat = st.one_of(
            st.none().map(lambda _: json_null()),
            st.text(min_size=0, max_size=10).map(json_string),
        )

        # status: one of the three strings, but also try to produce invalid strings sometimes
        # to provoke divergence (e.g. uppercase, misspell, or null)
        status_strat = st.one_of(
            st.sampled_from(status_values).map(json_string),
            st.text(min_size=1, max_size=7).filter(lambda s: s not in status_values).map(json_string),
            st.none().map(lambda _: json_null()),
        )

        # tags: array of strings, allow empty array, array with empty string, or array with nulls (invalid)
        tags_strat = st.lists(
            st.one_of(
                st.text(min_size=0, max_size=5).map(json_string),
                st.none().map(lambda _: json_null()),
            ),
            min_size=0,
            max_size=5,
        ).map(json_array)

        # child: null or record (one level recursion)
        if depth <= 0:
            child_strat = st.none().map(lambda _: json_null())
        else:
            child_strat = st.one_of(
                st.none().map(lambda _: json_null()),
                gen_record(depth - 1),
            )

        # Compose record fields as JSON text
        return st.tuples(id_strat, amount_strat, name_strat, status_strat, tags_strat, child_strat).map(
            lambda fields: json_object([
                ("id", fields[0]),
                ("amount", fields[1]),
                ("name", fields[2]),
                ("status", fields[3]),
                ("tags", fields[4]),
                ("child", fields[5]),
            ])
        )

    # Generate top-level record with depth=1
    json_text = draw(gen_record(depth=1))
    return json_text.encode("utf-8")