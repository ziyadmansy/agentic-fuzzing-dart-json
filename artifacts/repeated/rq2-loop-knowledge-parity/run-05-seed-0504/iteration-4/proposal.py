from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status enum
    statuses = ["active", "inactive", "unknown"]

    # Helper: produce a JSON string literal with proper escaping of " and \
    # We'll keep it simple: only escape " and \, no other escapes.
    def json_string(s: str) -> str:
        return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

    # Helper: produce JSON text for an int or a float (for id)
    # We produce either an integer literal or a float literal (with decimal point)
    # to trigger the known divergence on id decoding.
    def json_number(n):
        # n is int or float
        if isinstance(n, int):
            return str(n)
        else:
            # float: ensure decimal point to distinguish from int
            # Use repr to get a canonical float representation
            r = repr(n)
            if '.' not in r and 'e' not in r and 'E' not in r:
                r += '.0'
            return r

    # Helper: produce JSON text for a JSON value (string, number, null, array, object)
    # limited to our schema types
    # We'll inline this for the fields below.

    # Compose a valid "id" field value:
    # - manual and built_value require int (JSON integer)
    # - json_serializable and freezed accept int or float (converted to int)
    # We want to produce either an int or a float that looks like an int,
    # or a float outside int64 range to trigger saturation differences.
    # We'll produce either:
    # - an int in 64-bit range
    # - a float that is an integer value (e.g. 1.0)
    # - a float outside int64 range (e.g. 2**63 as float)
    # Hypothesis int64 range: -2**63 to 2**63-1
    INT64_MIN = -2**63
    INT64_MAX = 2**63 - 1

    id_type_choice = draw(st.sampled_from(["int", "float_in_range", "float_out_of_range"]))

    if id_type_choice == "int":
        # int in 64-bit range
        id_val = draw(st.integers(min_value=INT64_MIN, max_value=INT64_MAX))
        id_json = json_number(id_val)
    elif id_type_choice == "float_in_range":
        # float that is an integer value inside int64 range
        int_val = draw(st.integers(min_value=INT64_MIN, max_value=INT64_MAX))
        id_val = float(int_val)
        id_json = json_number(id_val)
    else:
        # float outside int64 range, saturates to min or max
        # pick a float > INT64_MAX or < INT64_MIN
        side = draw(st.sampled_from(["min", "max"]))
        if side == "min":
            # float less than INT64_MIN
            # e.g. INT64_MIN - 1e10 as float
            id_val = float(INT64_MIN) - 1e10
        else:
            # float greater than INT64_MAX
            id_val = float(INT64_MAX) + 1e10
        id_json = json_number(id_val)

    # Compose "amount" field: string, always present, non-null
    # We'll produce a simple decimal string, or a string that looks like a number but is string
    # To keep it simple, just a decimal string with optional minus and decimal point
    amount_str = draw(st.text(min_size=1, max_size=10, alphabet="0123456789.-"))
    # sanitize amount_str to be a valid JSON string (no control chars, no quotes)
    # We'll filter out quotes and backslashes to avoid escaping complexity
    amount_str = ''.join(c for c in amount_str if c not in '"\\')
    if amount_str == "":
        amount_str = "0"
    amount_json = json_string(amount_str)

    # Compose "name" field: nullable string
    # Either null or a string (possibly empty)
    name_is_null = draw(st.booleans())
    if name_is_null:
        name_json = "null"
    else:
        name_val = draw(st.text(min_size=0, max_size=20))
        # sanitize string for JSON
        name_json = json_string(name_val)

    # Compose "status" field: one of the three known strings
    # We will also try to produce an unrecognized string rarely to confirm rejection
    # But since all reject unrecognized status, it won't cause divergence.
    # So produce only valid status strings here.
    status_val = draw(st.sampled_from(statuses))
    status_json = json_string(status_val)

    # Compose "tags" field: array of strings
    # Known divergence: missing tags accepted only by built_value
    # So we produce either:
    # - present tags array (possibly empty)
    # - missing tags field (to trigger divergence)
    tags_present = draw(st.booleans())
    if tags_present:
        # produce array of strings (0 to 5 elements)
        tags_list = draw(st.lists(st.text(min_size=0, max_size=10), max_size=5))
        # sanitize tags strings
        tags_list = [''.join(c for c in t if c not in '"\\') for t in tags_list]
        tags_json = "[" + ",".join(json_string(t) for t in tags_list) + "]"
    else:
        tags_json = None  # missing field

    # Compose "child" field: nullable record or null
    # We allow one level of recursion only
    # child can be null or a record with same schema but no further recursion
    child_is_null = draw(st.booleans())
    if child_is_null:
        child_json = "null"
    else:
        # Compose a child record with no further child (child=null)
        # We reuse the same logic but fix child=null to avoid deep recursion
        # id: int in range
        child_id = draw(st.integers(min_value=INT64_MIN, max_value=INT64_MAX))
        child_id_json = json_number(child_id)
        # amount: string
        child_amount = draw(st.text(min_size=1, max_size=10, alphabet="0123456789.-"))
        child_amount = ''.join(c for c in child_amount if c not in '"\\')
        if child_amount == "":
            child_amount = "0"
        child_amount_json = json_string(child_amount)
        # name: nullable string
        child_name_is_null = draw(st.booleans())
        if child_name_is_null:
            child_name_json = "null"
        else:
            child_name_val = draw(st.text(min_size=0, max_size=20))
            child_name_json = json_string(child_name_val)
        # status: one of statuses
        child_status_val = draw(st.sampled_from(statuses))
        child_status_json = json_string(child_status_val)
        # tags: present, array of strings (empty or not)
        child_tags_list = draw(st.lists(st.text(min_size=0, max_size=10), max_size=5))
        child_tags_list = [''.join(c for c in t if c not in '"\\') for t in child_tags_list]
        child_tags_json = "[" + ",".join(json_string(t) for t in child_tags_list) + "]"
        # child: null (no further recursion)
        child_child_json = "null"

        child_json = (
            "{" +
            f'"id":{child_id_json},'
            f'"amount":{child_amount_json},'
            f'"name":{child_name_json},'
            f'"status":{child_status_json},'
            f'"tags":{child_tags_json},'
            f'"child":{child_child_json}'
            "}"
        )

    # Compose top-level JSON object fields as list of key:value strings
    fields = [
        f'"id":{id_json}',
        f'"amount":{amount_json}',
        f'"name":{name_json}',
        f'"status":{status_json}',
        f'"child":{child_json}',
    ]
    if tags_json is not None:
        fields.append(f'"tags":{tags_json}')
    # else omit tags field to trigger divergence

    # Shuffle fields order to avoid bias
    import random
    random.shuffle(fields)

    json_text = "{" + ",".join(fields) + "}"

    return json_text.encode("utf-8")