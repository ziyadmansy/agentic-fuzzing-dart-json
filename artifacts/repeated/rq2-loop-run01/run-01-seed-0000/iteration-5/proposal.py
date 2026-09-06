from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic primitives as strings for JSON output
    def json_string(s: str) -> str:
        # Escape backslash and quote for JSON string
        return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

    def json_int(i: int) -> str:
        return str(i)

    def json_null() -> str:
        return "null"

    def json_array(arr: list[str]) -> str:
        return "[" + ",".join(arr) + "]"

    def json_object(obj: dict[str, str]) -> str:
        # obj keys are always strings, values are JSON text
        items = []
        for k, v in obj.items():
            items.append(json_string(k) + ":" + v)
        return "{" + ",".join(items) + "}"

    # Enum values for "status"
    status_values = ["active", "inactive", "unknown"]

    # Recursive record generator with bounded depth
    def gen_record(depth: int) -> str:
        # id: integer
        id_val = draw(st.integers(min_value=-(2**31), max_value=2**31-1))
        id_json = json_int(id_val)

        # amount: string, allow numeric strings, empty, or weird strings
        amount_str = draw(
            st.one_of(
                st.text(min_size=0, max_size=10),
                st.integers(min_value=-10000, max_value=10000).map(str),
                st.floats(allow_nan=False, allow_infinity=False).map(lambda f: format(f, "g")),
            )
        )
        amount_json = json_string(amount_str)

        # name: string or null, allow empty string, unicode, or null
        name_val = draw(st.one_of(st.none(), st.text(min_size=0, max_size=20)))
        name_json = json_null() if name_val is None else json_string(name_val)

        # status: one of enum strings, but also try to produce strings outside enum to test rejection
        # To provoke divergence, sometimes produce invalid enum strings
        status_val = draw(
            st.one_of(
                st.sampled_from(status_values),
                st.text(min_size=1, max_size=10).filter(lambda s: s not in status_values),
            )
        )
        status_json = json_string(status_val)

        # tags: array of strings, allow empty array, or array with empty strings, or unicode strings
        tags_len = draw(st.integers(min_value=0, max_value=5))
        tags_vals = draw(st.lists(st.text(min_size=0, max_size=10), min_size=tags_len, max_size=tags_len))
        tags_json = json_array([json_string(t) for t in tags_vals])

        # child: null or nested record (one level recursion max)
        if depth > 0:
            child_val = draw(st.one_of(st.none(), st.deferred(lambda: gen_record(depth - 1))))
        else:
            child_val = None
        child_json = json_null() if child_val is None else child_val

        obj = {
            "id": id_json,
            "amount": amount_json,
            "name": name_json,
            "status": status_json,
            "tags": tags_json,
            "child": child_json,
        }
        return json_object(obj)

    # Generate record with max depth 1 (one level recursion)
    json_text = gen_record(1)
    return json_text.encode("utf-8")