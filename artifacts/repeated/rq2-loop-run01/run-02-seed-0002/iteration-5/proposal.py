from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base primitives as JSON text
    def json_string(s: str) -> str:
        # minimal escaping for quotes and backslash
        return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

    def json_int(i: int) -> str:
        return str(i)

    def json_null() -> str:
        return "null"

    def json_array(elems) -> str:
        return "[" + ",".join(elems) + "]"

    def json_object(pairs) -> str:
        # pairs is list of (key:str, value:str)
        return "{" + ",".join(json_string(k) + ":" + v for k, v in pairs) + "}"

    # Recursive record generator with bounded depth
    def record(depth: int) -> st.SearchStrategy[str]:
        # id: integer
        id_strat = st.integers(min_value=-(2**31), max_value=2**31-1).map(json_int)

        # amount: string, allow numeric strings, empty, or weird strings
        amount_strat = st.one_of(
            st.integers(min_value=0, max_value=10**6).map(lambda i: json_string(str(i))),
            st.text(min_size=0, max_size=10).map(json_string),
            st.just(json_string("0")),
        )

        # name: string or null, allow empty string, unicode, or null
        name_strat = st.one_of(
            st.none().map(lambda _: json_null()),
            st.text(min_size=0, max_size=20).map(json_string),
        )

        # status: one of "active", "inactive", "unknown"
        status_strat = st.sampled_from(["active", "inactive", "unknown"]).map(json_string)

        # tags: array of strings, allow empty, duplicates, unicode, empty strings
        tags_strat = st.lists(
            st.text(min_size=0, max_size=10), min_size=0, max_size=5
        ).map(lambda lst: json_array([json_string(s) for s in lst]))

        # child: null or nested record (one level recursion normally)
        if depth <= 0:
            child_strat = st.just(json_null())
        else:
            # To increase divergence, sometimes produce null, sometimes nested record
            child_strat = st.one_of(
                st.just(json_null()),
                record(depth - 1),
            )

        # Compose fields as pairs
        return st.tuples(id_strat, amount_strat, name_strat, status_strat, tags_strat, child_strat).map(
            lambda t: json_object([
                ("id", t[0]),
                ("amount", t[1]),
                ("name", t[2]),
                ("status", t[3]),
                ("tags", t[4]),
                ("child", t[5]),
            ])
        )

    # Generate record with max depth 1 (one level recursion)
    json_text = draw(record(1))
    return json_text.encode("utf-8")