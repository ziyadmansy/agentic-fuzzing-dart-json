from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Helper to generate a valid status value or a subtle variant
    status_values = ["active", "inactive", "unknown"]
    # Sometimes use a valid value, sometimes a near-miss (e.g. wrong case, int, null, empty string)
    status_strategy = st.one_of(
        st.sampled_from(status_values),
        st.sampled_from([s.upper() for s in status_values]),
        st.integers(min_value=0, max_value=2),
        st.none(),
        st.just(""),
        st.just("null"),
    )

    # Helper for 'amount': usually a string, but sometimes a number, null, or weird string
    amount_strategy = st.one_of(
        st.text(min_size=0, max_size=16),
        st.integers(min_value=-10**9, max_value=10**9).map(str),
        st.floats(allow_nan=False, allow_infinity=False).map(lambda f: str(f)),
        st.integers(min_value=-10**9, max_value=10**9),  # wrong type
        st.none(),  # wrong type
    )

    # Helper for 'name': usually string or null, but sometimes int, bool, or missing
    name_strategy = st.one_of(
        st.text(min_size=0, max_size=16),
        st.none(),
        st.integers(min_value=-10**9, max_value=10**9),
        st.booleans(),
    )

    # Helper for 'tags': usually array of strings, but sometimes array of mixed types, or not an array
    tags_strategy = st.one_of(
        st.lists(st.text(min_size=0, max_size=16), max_size=4),
        st.lists(st.one_of(
            st.text(min_size=0, max_size=16),
            st.integers(min_value=-10**9, max_value=10**9),
            st.none(),
            st.booleans(),
        ), max_size=4),
        st.text(min_size=0, max_size=16),  # not an array
        st.none(),  # not an array
    )

    # Helper for 'id': usually int, but sometimes string, float, null, or missing
    id_strategy = st.one_of(
        st.integers(min_value=-10**9, max_value=10**9),
        st.text(min_size=0, max_size=16),
        st.floats(allow_nan=False, allow_infinity=False),
        st.none(),
    )

    # Recursion for 'child'
    def child_strategy(depth):
        if depth <= 0:
            return st.none()
        # Sometimes null, sometimes a record, sometimes wrong type
        return st.one_of(
            st.none(),
            record_strategy(depth - 1),
            st.text(min_size=0, max_size=16),  # wrong type
            st.integers(min_value=-10**9, max_value=10**9),  # wrong type
        )

    # Compose the record
    def record_strategy(depth):
        return st.tuples(
            id_strategy,
            amount_strategy,
            name_strategy,
            status_strategy,
            tags_strategy,
            child_strategy(depth),
        ).map(lambda fields: fields)

    # Draw the record (depth 1 or 2 for bounded recursion)
    depth = draw(st.integers(min_value=1, max_value=2))
    id_val, amount_val, name_val, status_val, tags_val, child_val = draw(record_strategy(depth))

    # Helper to encode a value as JSON
    def encode_json(val):
        if isinstance(val, str):
            # Escape backslashes and quotes
            return '"' + val.replace('\\', '\\\\').replace('"', '\\"') + '"'
        elif val is None:
            return 'null'
        elif isinstance(val, bool):
            return 'true' if val else 'false'
        elif isinstance(val, float):
            # JSON numbers: use repr, but avoid inf/nan
            return str(val)
        elif isinstance(val, int):
            return str(val)
        elif isinstance(val, list):
            return '[' + ','.join(encode_json(v) for v in val) + ']'
        elif isinstance(val, tuple):
            return '[' + ','.join(encode_json(v) for v in val) + ']'
        elif isinstance(val, dict):
            # Not used, but for completeness
            return '{' + ','.join(f'{encode_json(k)}:{encode_json(v)}' for k, v in val.items()) + '}'
        else:
            # Should not happen
            return 'null'

    # Compose the JSON object as a string
    fields = []
    # id
    fields.append('"id":' + encode_json(id_val))
    # amount
    fields.append('"amount":' + encode_json(amount_val))
    # name
    fields.append('"name":' + encode_json(name_val))
    # status
    fields.append('"status":' + encode_json(status_val))
    # tags
    fields.append('"tags":' + encode_json(tags_val))
    # child
    if isinstance(child_val, tuple):
        # It's a nested record
        child_fields = []
        child_id, child_amount, child_name, child_status, child_tags, child_child = child_val
        child_fields.append('"id":' + encode_json(child_id))
        child_fields.append('"amount":' + encode_json(child_amount))
        child_fields.append('"name":' + encode_json(child_name))
        child_fields.append('"status":' + encode_json(child_status))
        child_fields.append('"tags":' + encode_json(child_tags))
        child_fields.append('"child":' + encode_json(child_child))
        child_json = '{' + ','.join(child_fields) + '}'
        fields.append('"child":' + child_json)
    else:
        fields.append('"child":' + encode_json(child_val))

    json_str = '{' + ','.join(fields) + '}'
    return json_str.encode('utf-8')