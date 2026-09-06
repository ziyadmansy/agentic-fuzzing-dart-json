from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status enum
    statuses = ["active", "inactive", "unknown"]

    # Helper: produce a JSON string literal with proper escaping of quotes and backslashes
    def json_string(s: str) -> str:
        # minimal escaping for " and \ to keep JSON valid
        return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

    # Helper: produce JSON array of strings
    def json_string_array(strs):
        return "[" + ",".join(json_string(s) for s in strs) + "]"

    # Strategy for "amount" field: normally a string, but sometimes inject a number or null or boolean to cause divergence
    amount_str = st.text(min_size=0, max_size=10)
    amount_variant = st.one_of(
        amount_str.map(json_string),  # normal string
        st.integers(min_value=-1000, max_value=1000).map(str),  # number as string (still string)
        st.integers(min_value=-1000, max_value=1000).map(str).map(lambda n: n),  # number as number (no quotes)
        st.none().map(lambda _: "null"),
        st.booleans().map(lambda b: "true" if b else "false"),
    )

    # Strategy for "name": string or null, but also sometimes a number or boolean to cause divergence
    name_variant = st.one_of(
        st.none().map(lambda _: "null"),
        st.text(min_size=0, max_size=10).map(json_string),
        st.integers(min_value=-1000, max_value=1000).map(str),  # number as number (no quotes)
        st.booleans().map(lambda b: "true" if b else "false"),
    )

    # Strategy for "status": normally one of the three strings, but sometimes null or wrong string or number
    status_variant = st.one_of(
        st.sampled_from(statuses).map(json_string),
        st.none().map(lambda _: "null"),
        st.text(min_size=1, max_size=10).filter(lambda s: s not in statuses).map(json_string),
        st.integers(min_value=-10, max_value=10).map(str),
    )

    # Strategy for "tags": normally array of strings, but sometimes array of numbers, or null, or empty array
    tags_str_array = st.lists(st.text(min_size=0, max_size=5), min_size=0, max_size=5).map(json_string_array)
    tags_num_array = st.lists(st.integers(min_value=-10, max_value=10).map(str), min_size=0, max_size=5).map(lambda nums: "[" + ",".join(nums) + "]")
    tags_variant = st.one_of(
        tags_str_array,
        tags_num_array,
        st.none().map(lambda _: "null"),
        st.just("[]"),
    )

    # Recursive record builder, bounded to depth 1 (child is either null or a record with child=null)
    @st.composite
    def record(draw, depth=0):
        # id: normally integer, but sometimes string or null or boolean
        id_variant = st.one_of(
            st.integers(min_value=0, max_value=10000).map(str),
            st.text(min_size=1, max_size=5).map(json_string),
            st.none().map(lambda _: "null"),
            st.booleans().map(lambda b: "true" if b else "false"),
        )
        id_val = draw(id_variant)

        amount_val = draw(amount_variant)
        name_val = draw(name_variant)
        status_val = draw(status_variant)
        tags_val = draw(tags_variant)

        # child: null or record (only one level deep)
        if depth == 0:
            child_val = draw(
                st.one_of(
                    st.just("null"),
                    record(depth=1).map(lambda s: s.decode("utf-8")),
                )
            )
        else:
            child_val = "null"

        # Compose JSON object string
        # Intentionally vary field order sometimes to see if any implementation is sensitive (shouldn't be)
        fields = [
            ('"id"', id_val),
            ('"amount"', amount_val),
            ('"name"', name_val),
            ('"status"', status_val),
            ('"tags"', tags_val),
            ('"child"', child_val),
        ]

        # Shuffle fields sometimes to cause subtle differences
        if draw(st.booleans()):
            fields = fields[::-1]

        obj_str = "{" + ",".join(f"{k}:{v}" for k, v in fields) + "}"
        return obj_str.encode("utf-8")

    return draw(record())