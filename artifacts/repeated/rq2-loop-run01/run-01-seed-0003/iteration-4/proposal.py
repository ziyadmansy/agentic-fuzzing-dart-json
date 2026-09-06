from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for enum values
    STATUS_VALUES = ['"active"', '"inactive"', '"unknown"']

    # Helper to produce a JSON string literal with proper escaping of quotes and backslashes
    def json_string(s: str) -> str:
        # Escape backslash and double quotes minimally for JSON string
        s = s.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{s}"'

    # id: integer, but we will sometimes produce a string or float to cause divergence
    # amount: string, but sometimes produce a number or null or boolean to cause divergence
    # name: string or null, sometimes produce number or boolean to cause divergence
    # status: one of "active", "inactive", "unknown" - sometimes produce invalid string or null
    # tags: array of strings - sometimes produce array with non-string elements or empty array or null
    # child: either null or a nested record (one level only) - sometimes produce wrong type or missing

    # Strategy for id field: mostly integer, sometimes string or float
    id_strategy = st.one_of(
        st.integers(min_value=0, max_value=2**31-1).map(str),
        st.floats(allow_infinity=False, allow_nan=False).map(lambda f: str(f)),
        st.text(min_size=1, max_size=5).map(json_string),
    )

    # Strategy for amount field: mostly string numeric, sometimes number, null, boolean
    amount_strategy = st.one_of(
        st.text(min_size=1, max_size=10).filter(lambda s: all(c.isdigit() or c in '.-' for c in s)).map(json_string),
        st.floats(allow_infinity=False, allow_nan=False).map(lambda f: str(f)),
        st.integers(min_value=-10000, max_value=10000).map(str),
        st.just("null"),
        st.booleans().map(lambda b: "true" if b else "false"),
    )

    # Strategy for name field: string or null normally, sometimes number or boolean
    name_strategy = st.one_of(
        st.none().map(lambda _: "null"),
        st.text(min_size=0, max_size=10).map(json_string),
        st.integers(min_value=-1000, max_value=1000).map(str),
        st.booleans().map(lambda b: "true" if b else "false"),
    )

    # Strategy for status field: mostly valid enum strings, sometimes invalid string or null
    status_strategy = st.one_of(
        st.sampled_from(STATUS_VALUES),
        st.text(min_size=1, max_size=10).filter(lambda s: s not in ['active', 'inactive', 'unknown']).map(json_string),
        st.just("null"),
    )

    # Strategy for tags: array of strings normally, sometimes array with non-string elements or empty array or null
    # We produce JSON array text directly
    def tags_strategy():
        # Elements: mostly strings, sometimes numbers or booleans or null
        elem = st.one_of(
            st.text(min_size=0, max_size=5).map(json_string),
            st.integers(min_value=-100, max_value=100).map(str),
            st.booleans().map(lambda b: "true" if b else "false"),
            st.just("null"),
        )
        # Array length 0 to 5
        arr = st.lists(elem, min_size=0, max_size=5)
        return arr.map(lambda elems: "[" + ",".join(elems) + "]")

    # Recursive child record: either null or a record with same schema but no further recursion
    # To avoid deep recursion, child.child is always null
    @st.composite
    def child_record(draw):
        # child.child is always null to limit recursion depth
        child_child = "null"
        id_val = draw(id_strategy)
        amount_val = draw(amount_strategy)
        name_val = draw(name_strategy)
        status_val = draw(status_strategy)
        tags_val = draw(tags_strategy())
        # child field is null here
        child_val = child_child
        # Compose JSON object text
        obj = (
            '{'
            f'"id":{id_val},'
            f'"amount":{amount_val},'
            f'"name":{name_val},'
            f'"status":{status_val},'
            f'"tags":{tags_val},'
            f'"child":{child_val}'
            '}'
        )
        return obj

    # Strategy for child field: null or child record or sometimes invalid type (string, number, array)
    child_field_strategy = st.one_of(
        st.just("null"),
        child_record(),
        # invalid types for child to cause divergence
        st.text(min_size=0, max_size=10).map(json_string),
        st.integers(min_value=-1000, max_value=1000).map(str),
        tags_strategy(),
    )

    # Compose top-level record with one or two fields off type or value to cause divergence
    # We pick one or two fields to be "off" and others normal

    # Pick fields to be off: 0,1 or 2 fields off
    off_fields = draw(st.lists(st.sampled_from(["id", "amount", "name", "status", "tags", "child"]), max_size=2, unique=True))

    # For each field, decide if off or normal
    def field_value(field):
        if field in off_fields:
            # produce off value
            if field == "id":
                # produce string or float instead of int
                return draw(st.one_of(
                    st.floats(allow_infinity=False, allow_nan=False).map(lambda f: str(f)),
                    st.text(min_size=1, max_size=5).map(json_string),
                ))
            elif field == "amount":
                # produce number, null, boolean or malformed string
                return draw(st.one_of(
                    st.floats(allow_infinity=False, allow_nan=False).map(lambda f: str(f)),
                    st.just("null"),
                    st.booleans().map(lambda b: "true" if b else "false"),
                    st.text(min_size=1, max_size=10).filter(lambda s: not all(c.isdigit() or c in '.-' for c in s)).map(json_string),
                ))
            elif field == "name":
                # produce number, boolean, or null
                return draw(st.one_of(
                    st.integers(min_value=-1000, max_value=1000).map(str),
                    st.booleans().map(lambda b: "true" if b else "false"),
                    st.just("null"),
                ))
            elif field == "status":
                # produce invalid string or null
                return draw(st.one_of(
                    st.text(min_size=1, max_size=10).filter(lambda s: s not in ['active', 'inactive', 'unknown']).map(json_string),
                    st.just("null"),
                ))
            elif field == "tags":
                # produce array with mixed types or null
                return draw(st.one_of(
                    tags_strategy(),
                    st.just("null"),
                    st.text(min_size=1, max_size=10).map(json_string),
                ))
            elif field == "child":
                # produce invalid types or null or child record
                return draw(st.one_of(
                    st.just("null"),
                    child_record(),
                    st.text(min_size=0, max_size=10).map(json_string),
                    st.integers(min_value=-1000, max_value=1000).map(str),
                    tags_strategy(),
                ))
        else:
            # produce normal value
            if field == "id":
                return draw(st.integers(min_value=0, max_value=2**31-1).map(str))
            elif field == "amount":
                # string numeric
                return draw(st.text(min_size=1, max_size=10).filter(lambda s: all(c.isdigit() or c in '.-' for c in s)).map(json_string))
            elif field == "name":
                return draw(st.one_of(
                    st.none().map(lambda _: "null"),
                    st.text(min_size=0, max_size=10).map(json_string),
                ))
            elif field == "status":
                return draw(st.sampled_from(STATUS_VALUES))
            elif field == "tags":
                return draw(tags_strategy())
            elif field == "child":
                return draw(st.one_of(
                    st.just("null"),
                    child_record(),
                ))

    id_val = field_value("id")
    amount_val = field_value("amount")
    name_val = field_value("name")
    status_val = field_value("status")
    tags_val = field_value("tags")
    child_val = field_value("child")

    # Compose final JSON object text
    json_text = (
        '{'
        f'"id":{id_val},'
        f'"amount":{amount_val},'
        f'"name":{name_val},'
        f'"status":{status_val},'
        f'"tags":{tags_val},'
        f'"child":{child_val}'
        '}'
    )

    return json_text.encode("utf-8")