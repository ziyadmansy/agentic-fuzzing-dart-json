from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic primitives as JSON text
    def json_string(s: str) -> str:
        # Escape backslash and double quote minimally for JSON strings
        return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

    def json_int(i: int) -> str:
        return str(i)

    def json_null() -> str:
        return "null"

    def json_enum_status(s: str) -> str:
        # s is one of "active", "inactive", "unknown"
        return json_string(s)

    # Recursive record generator, bounded to depth 1 for "child"
    def record(depth: int) -> st.SearchStrategy[str]:
        # id: integer
        id_strat = st.integers(min_value=-(2**31), max_value=2**31-1).map(json_int)

        # amount: string (arbitrary string, but valid JSON string)
        # To provoke divergence, allow empty string, numeric strings, strings with escapes
        amount_strat = st.text(min_size=0, max_size=20).map(json_string)

        # name: string or null
        name_strat = st.one_of(
            st.none().map(lambda _: json_null()),
            st.text(min_size=0, max_size=20).map(json_string),
        )

        # status: one of "active", "inactive", "unknown"
        status_strat = st.sampled_from(["active", "inactive", "unknown"]).map(json_enum_status)

        # tags: array of strings (0 to 5 elements)
        # Strings can be empty or contain escapes
        tags_strat = st.lists(st.text(min_size=0, max_size=10), max_size=5).map(
            lambda lst: "[" + ",".join(json_string(s) for s in lst) + "]"
        )

        # child: either null or a record (only one level recursion)
        if depth <= 0:
            child_strat = st.just(json_null())
        else:
            child_strat = st.one_of(
                st.just(json_null()),
                record(depth - 1),
            )

        # Compose the JSON object string with all fields in fixed order
        return st.tuples(id_strat, amount_strat, name_strat, status_strat, tags_strat, child_strat).map(
            lambda fields: (
                "{" +
                '"id":' + fields[0] + "," +
                '"amount":' + fields[1] + "," +
                '"name":' + fields[2] + "," +
                '"status":' + fields[3] + "," +
                '"tags":' + fields[4] + "," +
                '"child":' + fields[5] +
                "}"
            )
        )

    # Generate one record at depth 1 (child can be null or record with child=null)
    json_text = draw(record(depth=1))
    return json_text.encode("utf-8")