from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base primitives as strings for JSON output
    def json_str(s: str) -> str:
        # Escape backslash and double quotes minimally for JSON string
        return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

    def json_null() -> str:
        return "null"

    def json_int(i: int) -> str:
        return str(i)

    def json_array_str(arr) -> str:
        # arr is list of strings already JSON encoded
        return "[" + ",".join(arr) + "]"

    # Recursive record generator, bounded depth 1 (child is null or record with child=null)
    def record(depth: int) -> st.SearchStrategy[str]:
        # id: integer
        id_s = st.integers(min_value=-(2**31), max_value=2**31-1).map(json_int)

        # amount: string, allow numeric strings, empty, or strings with spaces/escapes
        # Also allow some unusual but valid JSON strings to test deserializers
        amount_s = st.one_of(
            st.text(min_size=0, max_size=10).map(json_str),
            st.integers(min_value=0, max_value=9999999).map(lambda i: json_str(str(i))),
            st.just(json_str("")),  # empty string
            st.just(json_str(" 123 ")),
            st.just(json_str("0")),
            st.just(json_str("-123.45")),
        )

        # name: string or null, allow empty string, unicode, or null
        name_s = st.one_of(
            st.none().map(lambda _: json_null()),
            st.text(min_size=0, max_size=15).map(json_str),
        )

        # status: one of "active", "inactive", "unknown"
        status_s = st.sampled_from(["active", "inactive", "unknown"]).map(json_str)

        # tags: array of strings, allow empty, single, multiple, strings with escapes
        tags_s = st.lists(
            st.text(min_size=0, max_size=10).map(json_str),
            min_size=0,
            max_size=5,
        ).map(json_array_str)

        # child: null or record with depth limit 1
        if depth >= 1:
            child_s = st.just(json_null())
        else:
            child_s = st.one_of(
                st.just(json_null()),
                record(depth + 1)
            )

        # Compose JSON object string with fields in fixed order
        def compose(idj, amountj, namej, statusj, tagsj, childj):
            return (
                "{" +
                '"id":' + idj + "," +
                '"amount":' + amountj + "," +
                '"name":' + namej + "," +
                '"status":' + statusj + "," +
                '"tags":' + tagsj + "," +
                '"child":' + childj +
                "}"
            )

        return st.tuples(id_s, amount_s, name_s, status_s, tags_s, child_s).map(
            lambda t: compose(*t)
        )

    # Generate top-level record string, then encode as UTF-8 bytes
    json_str_obj = draw(record(0))
    return json_str_obj.encode("utf-8")