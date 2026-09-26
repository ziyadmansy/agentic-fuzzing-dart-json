from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status values
    statuses = ["active", "inactive", "unknown"]

    # Helper: produce a JSON string literal from a Python string
    def json_string(s: str) -> str:
        # Minimal escaping for JSON string (only backslash and quote)
        s = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{s}"'

    # Helper: produce JSON text for a string or null, with a chance of wrong type
    def gen_name():
        # Mostly string or null, sometimes number or boolean to provoke divergence
        base = st.one_of(
            st.none().map(lambda _: "null"),
            st.text(min_size=0, max_size=20).map(json_string),
        )
        # Introduce occasional wrong types as raw JSON literals (numbers, bools)
        wrong_types = st.one_of(
            st.integers(min_value=-100, max_value=100).map(str),
            st.floats(allow_nan=False, allow_infinity=False).map(lambda f: f"{f:.6g}"),
            st.booleans().map(lambda b: "true" if b else "false"),
        )
        # 80% base, 20% wrong type
        return st.one_of(base, wrong_types).map(str)

    # Helper: produce JSON text for "status" field with occasional invalid string
    def gen_status():
        # Mostly valid status strings, sometimes invalid strings or numbers
        base = st.sampled_from(statuses).map(json_string)
        invalid_str = st.text(min_size=1, max_size=10).filter(lambda s: s not in statuses).map(json_string)
        wrong_type = st.one_of(
            st.integers(min_value=-10, max_value=10).map(str),
            st.booleans().map(lambda b: "true" if b else "false"),
        )
        # 70% base, 15% invalid string, 15% wrong type
        return st.one_of(base, invalid_str, wrong_type).map(str)

    # Helper: produce JSON text for "amount" field, mostly string decimal, sometimes number or malformed string
    def gen_amount():
        # Valid decimal string
        valid_decimal = st.floats(min_value=0, max_value=1000000, allow_nan=False, allow_infinity=False).map(
            lambda f: f'"{f:.2f}"'
        )
        # Malformed string (non-numeric)
        malformed_str = st.text(min_size=1, max_size=10).filter(lambda s: not s.replace(".", "", 1).isdigit()).map(json_string)
        # Number (not string)
        number = st.floats(min_value=0, max_value=1000000, allow_nan=False, allow_infinity=False).map(lambda f: f"{f:.2f}")
        # 60% valid decimal string, 20% malformed string, 20% number
        return st.one_of(valid_decimal, malformed_str, number).map(str)

    # Helper: produce JSON text for "tags" array, mostly array of strings, sometimes empty, sometimes wrong type inside
    def gen_tags():
        # Valid tags: array of strings
        valid_tags = st.lists(st.text(min_size=0, max_size=10).map(json_string), max_size=5).map(
            lambda lst: "[" + ",".join(lst) + "]"
        )
        # Array with some non-string elements (numbers, bools)
        mixed_tags = st.lists(
            st.one_of(
                st.text(min_size=0, max_size=10).map(json_string),
                st.integers(min_value=-10, max_value=10).map(str),
                st.booleans().map(lambda b: "true" if b else "false"),
            ),
            max_size=5,
        ).map(lambda lst: "[" + ",".join(lst) + "]")
        # Sometimes empty array
        empty = st.just("[]")
        # 50% valid, 30% mixed, 20% empty
        return st.one_of(valid_tags, mixed_tags, empty).map(str)

    # Recursive generation of "child" field JSON text or null
    # Limit recursion depth to 1 (child.child is always null)
    def gen_record(depth=0):
        # id: mostly integer, sometimes string or float to provoke divergence
        id_val = st.one_of(
            st.integers(min_value=0, max_value=1000).map(str),
            st.text(min_size=1, max_size=5).map(json_string),
            st.floats(min_value=0, max_value=1000, allow_nan=False, allow_infinity=False).map(lambda f: f"{f:.2f}"),
        )

        # amount
        amount_val = gen_amount()

        # name
        name_val = gen_name()

        # status
        status_val = gen_status()

        # tags
        tags_val = gen_tags()

        # child
        if depth == 1:
            # At max depth, child is always null
            child_val = st.just("null")
        else:
            # 70% null, 30% nested record (depth+1)
            child_val = st.one_of(
                st.just("null"),
                st.deferred(lambda: gen_record(depth=depth + 1)),
            )

        # Compose fields in fixed order with commas
        def compose_fields(id_, amount_, name_, status_, tags_, child_):
            return (
                '{'
                + f'"id":{id_},'
                + f'"amount":{amount_},'
                + f'"name":{name_},'
                + f'"status":{status_},'
                + f'"tags":{tags_},'
                + f'"child":{child_}'
                + "}"
            )

        return st.tuples(id_val, amount_val, name_val, status_val, tags_val, child_val).map(
            lambda t: compose_fields(*t)
        )

    # Generate top-level record JSON text
    json_text = draw(gen_record(depth=0))
    return json_text.encode("utf-8")