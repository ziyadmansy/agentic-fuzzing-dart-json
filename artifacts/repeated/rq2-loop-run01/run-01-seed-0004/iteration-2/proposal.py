from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for enum values
    STATUS_VALUES = ['"active"', '"inactive"', '"unknown"']

    # Helper: produce a JSON string literal with proper escaping of quotes and backslashes
    def json_string(s: str) -> str:
        # Minimal escaping for quotes and backslash
        s = s.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{s}"'

    # Strategy for "id": integer, but also try strings that look like integers, floats, or null
    # to induce divergence.
    id_strategy = st.one_of(
        st.integers(min_value=-(2**31), max_value=2**31-1).map(str),
        st.text(min_size=1, max_size=5).filter(lambda t: not t.isdigit()),  # non-digit strings
        st.floats(allow_infinity=False, allow_nan=False).map(lambda f: repr(f)),
        st.just("null"),
        st.just("true"),
        st.just("false"),
    )

    # Strategy for "amount": string normally, but also try numbers or null to induce divergence
    amount_strategy = st.one_of(
        st.text(min_size=0, max_size=10).map(json_string),
        st.integers(min_value=-1000, max_value=1000).map(str),
        st.floats(allow_infinity=False, allow_nan=False).map(lambda f: repr(f)),
        st.just("null"),
        st.just("true"),
        st.just("false"),
    )

    # Strategy for "name": string or null normally, but also try numbers or booleans
    name_strategy = st.one_of(
        st.none().map(lambda _: "null"),
        st.text(min_size=0, max_size=10).map(json_string),
        st.integers(min_value=-1000, max_value=1000).map(str),
        st.floats(allow_infinity=False, allow_nan=False).map(lambda f: repr(f)),
        st.just("true"),
        st.just("false"),
    )

    # Strategy for "status": one of the three strings normally, but also try null, numbers, booleans
    status_strategy = st.one_of(
        st.sampled_from(STATUS_VALUES),
        st.none().map(lambda _: "null"),
        st.text(min_size=1, max_size=10).map(json_string),
        st.integers(min_value=-10, max_value=10).map(str),
        st.just("true"),
        st.just("false"),
    )

    # Strategy for "tags": array of strings normally, but also try null, empty array, array with non-string
    def tags_strategy():
        # array of strings
        arr_strings = st.lists(st.text(min_size=0, max_size=10).map(json_string), max_size=5).map(
            lambda lst: "[" + ",".join(lst) + "]"
        )
        # array with some non-string elements
        arr_mixed = st.lists(
            st.one_of(
                st.text(min_size=0, max_size=10).map(json_string),
                st.integers(min_value=-10, max_value=10).map(str),
                st.none().map(lambda _: "null"),
                st.just("true"),
                st.just("false"),
            ),
            max_size=5,
        ).map(lambda lst: "[" + ",".join(lst) + "]")

        return st.one_of(
            arr_strings,
            arr_mixed,
            st.just("null"),
            st.just("[]"),
        )

    # Recursive strategy for "child": either null or a nested record (one level only)
    # To avoid deep recursion, child.child is always null.
    @st.composite
    def record(draw, allow_child=True):
        # Compose fields except child first
        id_val = draw(id_strategy)
        amount_val = draw(amount_strategy)
        name_val = draw(name_strategy)
        status_val = draw(status_strategy)
        tags_val = draw(tags_strategy())

        if allow_child:
            # child is either null or a record with child=null
            child_null = st.just("null")
            child_record = record(allow_child=False)
            child_val = draw(st.one_of(child_null, child_record))
        else:
            child_val = "null"

        # Build JSON object string with fields in fixed order
        # Use no extra spaces to keep consistent formatting
        json_obj = (
            "{" +
            f'"id":{id_val},' +
            f'"amount":{amount_val},' +
            f'"name":{name_val},' +
            f'"status":{status_val},' +
            f'"tags":{tags_val},' +
            f'"child":{child_val}' +
            "}"
        )
        return json_obj

    # Draw top-level record
    top_record = draw(record())

    # Return as bytes
    return top_record.encode("utf-8")