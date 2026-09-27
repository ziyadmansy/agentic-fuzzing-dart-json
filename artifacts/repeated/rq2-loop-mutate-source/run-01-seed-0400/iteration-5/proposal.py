from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for enum values
    STATUS_VALUES = ['active', 'inactive', 'unknown']

    # Helper to produce a JSON string literal with proper escaping of quotes and backslashes
    def json_string(s: str) -> str:
        # Minimal escaping for JSON string: backslash and quote
        s = s.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{s}"'

    # Recursive strategy for a Record JSON object as text
    # depth controls recursion depth to avoid infinite recursion
    def record_json(depth=0) -> st.SearchStrategy[str]:
        # id: integer (always present)
        id_strat = st.integers(min_value=-(2**31), max_value=2**31-1).map(str)

        # amount: string (always present)
        # To induce divergence, sometimes produce numeric strings, sometimes empty, sometimes weird unicode
        amount_strat = st.text(min_size=0, max_size=20).map(json_string)

        # name: string or null
        # To induce divergence, sometimes produce null, sometimes string, sometimes empty string
        name_strat = st.one_of(
            st.none().map(lambda _: "null"),
            st.text(min_size=0, max_size=20).map(json_string),
        )

        # status: one of "active", "inactive", "unknown"
        # To induce divergence, sometimes produce correct enum, sometimes a string close to enum but invalid
        # But mostly valid to keep near well-formed
        status_valid = st.sampled_from(STATUS_VALUES).map(json_string)
        status_invalid = st.text(min_size=1, max_size=10).filter(lambda x: x not in STATUS_VALUES).map(json_string)
        # Bias towards valid but sometimes invalid to induce divergence
        status_strat = st.one_of(
            status_valid,
            status_invalid,
        )

        # tags: array of strings (always present)
        # To induce divergence, sometimes empty array, sometimes array with empty strings, sometimes array with nulls (invalid)
        tag_string = st.text(min_size=0, max_size=10).map(json_string)
        tags_valid = st.lists(tag_string, min_size=0, max_size=5).map(lambda lst: "[" + ",".join(lst) + "]")
        tags_invalid = st.lists(st.one_of(tag_string, st.just("null")), min_size=0, max_size=5).map(lambda lst: "[" + ",".join(lst) + "]")
        tags_strat = st.one_of(tags_valid, tags_invalid)

        # child: Record or null
        # To avoid deep recursion, limit depth to 1 normally
        if depth >= 1:
            # Only null or empty object (invalid) to induce divergence
            child_strat = st.one_of(
                st.just("null"),
                st.just("{}"),  # empty object, missing fields
            )
        else:
            # Sometimes null, sometimes a nested record (depth+1)
            child_strat = st.one_of(
                st.just("null"),
                record_json(depth + 1),
            )

        # Compose fields with possible type deviations to induce divergence:
        # For each field, sometimes produce correct type, sometimes wrong type (e.g. number instead of string)
        # But only one or two fields per record are off to keep near well-formed

        # For each field, produce a tuple (fieldname, json_text)
        # We will shuffle fields to avoid positional assumptions

        # id field: sometimes integer as number, sometimes as string (wrong type)
        id_field = st.one_of(
            id_strat.map(lambda v: f'"id":{v}'),  # number
            id_strat.map(lambda v: f'"id":{json_string(str(v))}'),  # string instead of number
        )

        # amount field: always string, but sometimes empty or numeric string
        amount_field = amount_strat.map(lambda v: f'"amount":{v}')

        # name field: string or null, sometimes number (wrong type)
        name_field = st.one_of(
            name_strat.map(lambda v: f'"name":{v}'),
            id_strat.map(lambda v: f'"name":{v}'),  # number instead of string/null
        )

        # status field: mostly valid enum string, sometimes invalid string, sometimes null (wrong type)
        status_field = st.one_of(
            status_strat.map(lambda v: f'"status":{v}'),
            st.just('"status":null'),
        )

        # tags field: array of strings, sometimes array with nulls, sometimes string (wrong type)
        tags_field = st.one_of(
            tags_strat.map(lambda v: f'"tags":{v}'),
            amount_strat.map(lambda v: f'"tags":{v}'),  # string instead of array
        )

        # child field: null or nested record or empty object or number (wrong type)
        child_field = st.one_of(
            child_strat.map(lambda v: f'"child":{v}'),
            id_strat.map(lambda v: f'"child":{v}'),  # number instead of object/null
        )

        # Combine all fields into a list, then shuffle to avoid positional assumptions
        fields_list_strat = st.tuples(id_field, amount_field, name_field, status_field, tags_field, child_field).map(list)

        def shuffle_fields(fields):
            # Shuffle fields deterministically with Hypothesis
            # Hypothesis does not provide a shuffle strategy, so shuffle manually using draw
            # But we cannot call draw here, so shuffle by sorting by hash mod 6
            # This is a deterministic shuffle to avoid positional bias
            return sorted(fields, key=lambda f: hash(f) % 6)

        fields_shuffled_strat = fields_list_strat.map(shuffle_fields)

        # Join fields with commas and wrap in braces
        record_obj_strat = fields_shuffled_strat.map(lambda fields: "{" + ",".join(fields) + "}")

        return record_obj_strat

    # Draw the top-level record JSON string
    json_text = draw(record_json(depth=0))

    # Return as bytes (UTF-8)
    return json_text.encode("utf-8")