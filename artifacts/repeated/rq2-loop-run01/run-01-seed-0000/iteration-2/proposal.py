from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base primitives as JSON text
    def json_string(s: str) -> str:
        # Escape backslash and double quotes minimally for JSON string
        s = s.replace('\\', '\\\\').replace('"', '\\"')
        return '"' + s + '"'

    def json_int(i: int) -> str:
        return str(i)

    def json_null() -> str:
        return "null"

    def json_array(arr: list[str]) -> str:
        return "[" + ",".join(arr) + "]"

    def json_object(obj: dict[str, str]) -> str:
        # obj keys are always strings, values are JSON text
        items = [json_string(k) + ":" + v for k, v in obj.items()]
        return "{" + ",".join(items) + "}"

    # Recursive record generator with bounded depth
    def record(depth: int) -> st.SearchStrategy[str]:
        if depth <= 0:
            # At max depth, child is always null
            child_strat = st.just(json_null())
        else:
            child_strat = st.one_of(
                st.just(json_null()),
                record(depth - 1)
            )

        # id: integer (allow negative and zero to test edge cases)
        id_strat = st.integers(min_value=-1000, max_value=1000).map(json_int)

        # amount: string, allow numeric strings, empty, or weird strings
        amount_strat = st.one_of(
            st.text(min_size=0, max_size=10).map(json_string),
            st.integers(min_value=-100000, max_value=100000).map(lambda i: json_string(str(i))),
            st.just(json_string(""))  # empty string
        )

        # name: string or null, allow empty string, unicode, or null
        name_strat = st.one_of(
            st.none().map(lambda _: json_null()),
            st.text(min_size=0, max_size=15).map(json_string)
        )

        # status: one of "active", "inactive", "unknown" as string, but also try
        # to produce invalid enum strings to provoke divergence
        status_strat = st.one_of(
            st.sampled_from(["active", "inactive", "unknown"]).map(json_string),
            # invalid enum strings to test acceptance/rejection differences
            st.sampled_from(["Active", "INACTIVE", "unknown ", "unknown\n", ""]).map(json_string)
        )

        # tags: array of strings, allow empty array, array with empty strings,
        # or array with unicode and special chars
        tags_strat = st.lists(
            st.text(min_size=0, max_size=10).map(json_string),
            min_size=0,
            max_size=5
        ).map(json_array)

        # child: record or null
        child_json_strat = child_strat

        # Compose the object fields as JSON text
        return st.tuples(id_strat, amount_strat, name_strat, status_strat, tags_strat, child_json_strat).map(
            lambda fields: json_object({
                "id": fields[0],
                "amount": fields[1],
                "name": fields[2],
                "status": fields[3],
                "tags": fields[4],
                "child": fields[5],
            })
        )

    # Generate record with max recursion depth 1 (one level of child)
    json_text = draw(record(depth=1))
    return json_text.encode("utf-8")