from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base primitives as JSON text
    json_int = st.integers(min_value=0, max_value=1000).map(str)
    # amount is string, but allow numeric strings and some edge strings
    amount_str = st.one_of(
        st.text(min_size=1, max_size=5).filter(lambda s: all(c in "0123456789." for c in s)),
        st.just("0"),
        st.just("0.0"),
        st.just("123"),
        st.just("999.99"),
    )
    # name: string or null
    name_str = st.one_of(
        st.none().map(lambda _: "null"),
        st.text(min_size=0, max_size=10).map(lambda s: '"' + s.replace('"', '\\"') + '"'),
    )
    # status: one of three strings
    status_str = st.sampled_from(['"active"', '"inactive"', '"unknown"'])
    # tags: array of strings (possibly empty)
    tag_str = st.text(min_size=0, max_size=5).map(lambda s: '"' + s.replace('"', '\\"') + '"')
    tags_arr = st.lists(tag_str, max_size=3).map(lambda lst: "[" + ",".join(lst) + "]")

    # Recursive record builder, max depth 1 for child
    def record(depth):
        if depth > 1:
            # At max depth, child is always null
            child_val = st.just("null")
        else:
            # child is either null or another record (depth+1)
            child_val = st.one_of(st.just("null"), record(depth + 1))

        return st.tuples(
            json_int,
            amount_str,
            name_str,
            status_str,
            tags_arr,
            child_val,
        ).map(
            lambda t: (
                '{"id":' + t[0] +
                ',"amount":"' + t[1] + '"' +
                ',"name":' + t[2] +
                ',"status":' + t[3] +
                ',"tags":' + t[4] +
                ',"child":' + t[5] +
                '}'
            )
        )

    # Draw the top-level record string
    json_str = draw(record(0))
    return json_str.encode("utf-8")