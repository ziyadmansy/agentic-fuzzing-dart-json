from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for field names and status values
    FIELD_NAMES = ['id', 'amount', 'name', 'status', 'tags', 'child']
    STATUS_VALUES = ['active', 'inactive', 'unknown']

    # Strategy for "id" field:
    # - manual and built_value require a true int
    # - json_serializable and freezed accept num.toInt() (accept double)
    # We want to exploit this difference by generating a number that jsonDecode
    # produces as double (e.g. > 2**53) but that manual and built_value reject.
    # But jsonDecode is not available here, so we simulate by generating a number
    # that would be parsed as double by jsonDecode (a large integer literal > 2**53).
    # Since we must produce JSON text, we produce the number as a JSON number literal.
    # We produce the number as a string of digits without quotes.
    # We limit to 64-bit range max 9_223_372_036_854_775_807 (2**63-1).
    # But hypothesis float64 cannot exactly represent that, so we use a string.
    # We produce the id as a string of digits representing an integer in [2**53+1 .. 2**63-1].
    # This will be parsed by jsonDecode as a double, accepted by json_serializable/freezed,
    # but manual and built_value require int and reject.
    #
    # To produce the number as JSON text, we produce the digits as a string and insert
    # them directly into the JSON text (no quotes).
    #
    # We also allow a normal int in [0..2**53] to produce some normal cases.
    #
    # So id is a string of digits representing an integer in [0..2**63-1].
    # We will produce the JSON text for id as digits (no quotes).
    #
    # We produce id as a string of digits, then insert it as JSON number literal.

    # Generate id as int in [0..2**63-1]
    # We'll bias towards large numbers > 2**53 to trigger divergence.
    id_int = draw(
        st.one_of(
            st.integers(min_value=0, max_value=2**53),  # normal int range
            st.integers(min_value=2**53 + 1, max_value=2**63 - 1),  # large int triggers double
        )
    )
    id_json = str(id_int)

    # "amount" is a string, always present, non-nullable
    # Generate a non-empty string of digits with optional decimal point
    amount_str = draw(
        st.text(
            alphabet='0123456789.',
            min_size=1,
            max_size=10,
        ).filter(lambda s: s.count('.') <= 1 and s.replace('.', '').isdigit())
    )
    # amount JSON string with quotes and escaped if needed (only digits and '.' so no escapes)
    amount_json = '"' + amount_str + '"'

    # "name" is nullable string or null, optional presence accepted by all
    # We always include it (to avoid missing field issues)
    # Generate either null or a string (possibly empty)
    name_val = draw(st.one_of(st.none(), st.text(max_size=10)))
    if name_val is None:
        name_json = 'null'
    else:
        # Escape quotes and backslashes in name_val
        esc_name = name_val.replace('\\', '\\\\').replace('"', '\\"')
        name_json = '"' + esc_name + '"'

    # "status" is one of "active", "inactive", "unknown"
    # Always present and valid to avoid rejection by all
    status_val = draw(st.sampled_from(STATUS_VALUES))
    status_json = '"' + status_val + '"'

    # "tags" is array of strings, always present (missing tags accepted only by built_value)
    # To trigger divergence, we sometimes omit tags (to trigger built_value accept, others reject)
    # But we want to produce syntactically valid JSON objects, so we produce either:
    # - tags present with array of strings (possibly empty)
    # - or tags missing (to trigger divergence)
    # But the problem states all six fields always present in well-formed documents,
    # so we produce tags always present, but sometimes empty array to test empty list acceptance.
    # To test type divergence, we can produce tags as null (should be rejected by all)
    # or tags as a non-array (e.g. string) to test type rejection.
    # But type errors rejected by all, no divergence.
    # So we produce tags as array of strings (possibly empty).
    tags_len = draw(st.integers(min_value=0, max_value=3))
    tags_list = draw(st.lists(st.text(min_size=1, max_size=5), min_size=tags_len, max_size=tags_len))
    # Escape tags strings
    def esc_str(s):
        return s.replace('\\', '\\\\').replace('"', '\\"')
    tags_json = '[' + ','.join('"' + esc_str(t) + '"' for t in tags_list) + ']'

    # "child" is nullable Record or null, one level recursion normally
    # We produce either null or a nested record with same schema but no further nesting (child.child always null)
    # To keep bounded recursion, child.child is always null.
    # We produce child as null or a nested record with all fields present.
    child_is_null = draw(st.booleans())
    if child_is_null:
        child_json = 'null'
    else:
        # Nested record fields:
        # id: int in [0..2**53] (to avoid nested divergence)
        child_id = draw(st.integers(min_value=0, max_value=2**53))
        child_id_json = str(child_id)
        # amount: string as above
        child_amount = draw(
            st.text(
                alphabet='0123456789.',
                min_size=1,
                max_size=10,
            ).filter(lambda s: s.count('.') <= 1 and s.replace('.', '').isdigit())
        )
        child_amount_json = '"' + child_amount + '"'
        # name: nullable string or null
        child_name_val = draw(st.one_of(st.none(), st.text(max_size=10)))
        if child_name_val is None:
            child_name_json = 'null'
        else:
            esc_child_name = child_name_val.replace('\\', '\\\\').replace('"', '\\"')
            child_name_json = '"' + esc_child_name + '"'
        # status: one of STATUS_VALUES
        child_status_val = draw(st.sampled_from(STATUS_VALUES))
        child_status_json = '"' + child_status_val + '"'
        # tags: array of strings (possibly empty)
        child_tags_len = draw(st.integers(min_value=0, max_value=3))
        child_tags_list = draw(st.lists(st.text(min_size=1, max_size=5), min_size=child_tags_len, max_size=child_tags_len))
        child_tags_json = '[' + ','.join('"' + esc_str(t) + '"' for t in child_tags_list) + ']'
        # child.child is always null (no further recursion)
        child_child_json = 'null'

        child_json = (
            '{'
            + '"id":' + child_id_json + ','
            + '"amount":' + child_amount_json + ','
            + '"name":' + child_name_json + ','
            + '"status":' + child_status_json + ','
            + '"tags":' + child_tags_json + ','
            + '"child":' + child_child_json
            + '}'
        )

    # Compose top-level JSON object with all six fields present
    # Order fields as per schema
    json_text = (
        '{'
        + '"id":' + id_json + ','
        + '"amount":' + amount_json + ','
        + '"name":' + name_json + ','
        + '"status":' + status_json + ','
        + '"tags":' + tags_json + ','
        + '"child":' + child_json
        + '}'
    )

    # Return bytes
    return json_text.encode('utf-8')