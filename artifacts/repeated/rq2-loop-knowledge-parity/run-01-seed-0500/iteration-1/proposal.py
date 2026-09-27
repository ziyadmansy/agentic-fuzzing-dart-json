from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status field
    statuses = ["active", "inactive", "unknown"]

    # Helper: JSON string escaping for Hypothesis-generated strings
    # We use a restricted charset to avoid complex escaping
    json_string_chars = st.characters(
        whitelist_categories=("Ll", "Lu", "Nd", "Zs"),
        blacklist_characters='"\\',
        min_codepoint=32,
        max_codepoint=126,
    )
    json_string = json_string_chars.filter(lambda s: s != "").map(lambda s: s)

    # id field:
    # To trigger divergence on id decoding:
    # - manual and built_value require a true int (no double)
    # - json_serializable and freezed accept double and convert to int saturating
    # jsonDecode converts large integers out of 64-bit range to double
    # So we generate id as either:
    # 1) int in 64-bit range (safe for all)
    # 2) int outside 64-bit range (becomes double in jsonDecode)
    # 3) a double that is an integer value (e.g. 1.0)
    # 4) a double that is not integer (should be rejected by all)
    # We want to produce mostly 1 or 2 or 3 to maximize divergence possibility.
    # But 4 will cause all to reject, so avoid it.

    # 64-bit signed int range
    INT64_MIN = -(2**63)
    INT64_MAX = 2**63 - 1

    # Generate id as one of:
    # - int in 64-bit range (as JSON number without decimal)
    # - int outside 64-bit range (as JSON number without decimal, but jsonDecode will convert to double)
    # - double with .0 fractional (as JSON number with decimal)
    id_case = draw(st.sampled_from(["int64", "int64_out_of_range", "double_int"]))

    if id_case == "int64":
        # int in 64-bit range
        id_val = draw(st.integers(min_value=INT64_MIN, max_value=INT64_MAX))
        id_json = str(id_val)
    elif id_case == "int64_out_of_range":
        # int outside 64-bit range, but still integer literal JSON number
        # Use a number just outside 64-bit range to trigger jsonDecode double
        # Use either just below INT64_MIN or just above INT64_MAX
        side = draw(st.sampled_from(["below", "above"]))
        if side == "below":
            val = draw(st.integers(min_value=INT64_MIN - 10**6, max_value=INT64_MIN - 1))
        else:
            val = draw(st.integers(min_value=INT64_MAX + 1, max_value=INT64_MAX + 10**6))
        id_val = val
        id_json = str(val)
    else:
        # double with .0 fractional part (e.g. 42.0)
        # This is accepted by json_serializable and freezed but not manual or built_value
        val = draw(st.integers(min_value=0, max_value=10**6))
        id_val = float(val)
        id_json = f"{val}.0"

    # amount field: string, always present, non-null
    # Use simple decimal strings, or edge cases like "0", "0.0", "1e10"
    amount_val = draw(
        st.one_of(
            st.just("0"),
            st.just("0.0"),
            st.just("1e10"),
            st.from_regex(r"^-?\d+(\.\d+)?([eE][+-]?\d+)?$", fullmatch=True),
        )
    )

    # name field: nullable string
    # name can be null or a string
    name_is_null = draw(st.booleans())
    if name_is_null:
        name_json = "null"
    else:
        name_str = draw(json_string)
        # escape quotes and backslashes in name_str
        esc_name = name_str.replace("\\", "\\\\").replace('"', '\\"')
        name_json = f'"{esc_name}"'

    # status field: one of "active", "inactive", "unknown"
    status_val = draw(st.sampled_from(statuses))
    status_json = f'"{status_val}"'

    # tags field: array of strings
    # To trigger divergence on missing tags (built_value accepts missing, others reject),
    # we sometimes omit tags entirely.
    tags_present = draw(st.booleans())
    if tags_present:
        # tags is present, array of strings (possibly empty)
        tags_len = draw(st.integers(min_value=0, max_value=3))
        tags_list = []
        for _ in range(tags_len):
            tag_str = draw(json_string)
            esc_tag = tag_str.replace("\\", "\\\\").replace('"', '\\"')
            tags_list.append(f'"{esc_tag}"')
        tags_json = "[" + ",".join(tags_list) + "]"
    else:
        tags_json = None  # omit field

    # child field: nullable record or null
    # One level recursion only
    # child can be null or a record with same schema but no further recursion (child=null)
    child_is_null = draw(st.booleans())
    if child_is_null:
        child_json = "null"
    else:
        # child record with child=null (no deeper recursion)
        # Use simple fixed values for child to reduce complexity
        # id: int64 in range
        child_id = draw(st.integers(min_value=INT64_MIN, max_value=INT64_MAX))
        child_id_json = str(child_id)
        # amount: fixed string
        child_amount = "0"
        # name: null
        child_name = "null"
        # status: "unknown"
        child_status = '"unknown"'
        # tags: empty array
        child_tags = "[]"
        # child: null
        child_child = "null"
        child_json = (
            "{"
            f'"id":{child_id_json},'
            f'"amount":"{child_amount}",'
            f'"name":{child_name},'
            f'"status":{child_status},'
            f'"tags":{child_tags},'
            f'"child":{child_child}'
            "}"
        )

    # Compose top-level JSON object fields
    fields = [
        f'"id":{id_json}',
        f'"amount":"{amount_val}"',
        f'"name":{name_json}',
        f'"status":{status_json}',
    ]
    if tags_json is not None:
        fields.append(f'"tags":{tags_json}')
    # else omit tags field to trigger divergence on missing tags

    fields.append(f'"child":{child_json}')

    json_text = "{" + ",".join(fields) + "}"

    return json_text.encode("utf-8")