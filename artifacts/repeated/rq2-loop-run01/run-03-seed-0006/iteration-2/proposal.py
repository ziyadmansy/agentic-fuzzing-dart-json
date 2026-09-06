from hypothesis import strategies as st

# Helper: JSON string escaping for double quotes and backslashes only (minimal)
def json_string_escape(s: str) -> str:
    return s.replace('\\', '\\\\').replace('"', '\\"')

# Compose a JSON string literal from a Python string
def json_string(s: str) -> str:
    return '"' + json_string_escape(s) + '"'

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status enum
    statuses = ["active", "inactive", "unknown"]

    # Base scalar fields with slight type fuzzing:
    # id: integer normally, but sometimes string or float to cause divergence
    # amount: string normally, but sometimes number or null (amount is string in schema)
    # name: string or null normally, but sometimes number or boolean or omitted (omission is not allowed, but test with null)
    # status: one of enum strings normally, but sometimes invalid string or null
    # tags: array of strings normally, but sometimes array with non-strings or empty array or null (null not allowed by schema)
    # child: either null or a nested record (one level only), but child can be null or a record with one field off

    # Strategy for id field: mostly int, sometimes stringified int, sometimes float
    id_val = draw(
        st.one_of(
            st.integers(min_value=0, max_value=2**31 - 1).map(str),
            st.integers(min_value=0, max_value=2**31 - 1),
            st.floats(min_value=0, max_value=2**31 - 1, allow_nan=False, allow_infinity=False).map(lambda f: str(f) if f.is_integer() else str(f)),
        )
    )
    # id must be integer in schema, so string or float is off

    # amount: normally string, but sometimes a number or null (null not allowed)
    amount_val = draw(
        st.one_of(
            st.text(min_size=1, max_size=10).map(json_string),
            st.integers(min_value=0, max_value=100000).map(str),
            st.just("null"),
        )
    )

    # name: string or null normally, sometimes number or boolean or "null" string
    name_val = draw(
        st.one_of(
            st.none().map(lambda _: "null"),
            st.text(min_size=0, max_size=10).map(json_string),
            st.integers(min_value=-1000, max_value=1000).map(str),
            st.booleans().map(lambda b: "true" if b else "false"),
        )
    )

    # status: one of enum strings normally, sometimes invalid string or null
    status_val = draw(
        st.one_of(
            st.sampled_from(statuses).map(json_string),
            st.text(min_size=1, max_size=10).filter(lambda s: s not in statuses).map(json_string),
            st.just("null"),
        )
    )

    # tags: array of strings normally, sometimes array with non-strings, empty array, or null (null not allowed)
    # We'll produce array text manually
    def gen_tag():
        return draw(
            st.one_of(
                st.text(min_size=1, max_size=10).map(json_string),
                st.integers(min_value=-1000, max_value=1000).map(str),
                st.booleans().map(lambda b: "true" if b else "false"),
            )
        )
    tags_len = draw(st.integers(min_value=0, max_value=5))
    tags_vals = [gen_tag() for _ in range(tags_len)]
    tags_val = "[" + ",".join(tags_vals) + "]"

    # child: null or a nested record with one level only
    # Nested record fields follow same fuzzing but no further recursion
    def gen_child_record():
        # id: int or string or float
        cid = draw(
            st.one_of(
                st.integers(min_value=0, max_value=2**31 - 1).map(str),
                st.integers(min_value=0, max_value=2**31 - 1),
                st.floats(min_value=0, max_value=2**31 - 1, allow_nan=False, allow_infinity=False).map(lambda f: str(f) if f.is_integer() else str(f)),
            )
        )
        # amount: string or number or null
        camount = draw(
            st.one_of(
                st.text(min_size=1, max_size=10).map(json_string),
                st.integers(min_value=0, max_value=100000).map(str),
                st.just("null"),
            )
        )
        # name: string or null or number or boolean
        cname = draw(
            st.one_of(
                st.none().map(lambda _: "null"),
                st.text(min_size=0, max_size=10).map(json_string),
                st.integers(min_value=-1000, max_value=1000).map(str),
                st.booleans().map(lambda b: "true" if b else "false"),
            )
        )
        # status: enum or invalid string or null
        cstatus = draw(
            st.one_of(
                st.sampled_from(statuses).map(json_string),
                st.text(min_size=1, max_size=10).filter(lambda s: s not in statuses).map(json_string),
                st.just("null"),
            )
        )
        # tags: array of strings or mixed or empty
        clen = draw(st.integers(min_value=0, max_value=3))
        ctags_vals = []
        for _ in range(clen):
            ctags_vals.append(draw(
                st.one_of(
                    st.text(min_size=1, max_size=10).map(json_string),
                    st.integers(min_value=-1000, max_value=1000).map(str),
                    st.booleans().map(lambda b: "true" if b else "false"),
                )
            ))
        ctags = "[" + ",".join(ctags_vals) + "]"

        # child: null only (no deeper recursion)
        cchild = "null"

        # Compose child record JSON text
        return (
            "{" +
            f'"id":{cid},'
            f'"amount":{camount},'
            f'"name":{cname},'
            f'"status":{cstatus},'
            f'"tags":{ctags},'
            f'"child":{cchild}'
            "}"
        )

    child_val = draw(st.one_of(st.just("null"), gen_child_record()))

    # Compose top-level JSON text
    json_text = (
        "{" +
        f'"id":{id_val},'
        f'"amount":{amount_val},'
        f'"name":{name_val},'
        f'"status":{status_val},'
        f'"tags":{tags_val},'
        f'"child":{child_val}'
        "}"
    )

    return json_text.encode("utf-8")