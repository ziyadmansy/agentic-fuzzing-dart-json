from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Helper to produce a JSON string literal with proper escaping of quotes and backslashes
    def json_string(s: str) -> str:
        # Escape backslash and double quote for JSON string
        s = s.replace('\\', '\\\\').replace('"', '\\"')
        # Also escape control characters (minimal)
        s = s.replace('\b', '\\b').replace('\f', '\\f').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
        return '"' + s + '"'

    # id field: to provoke divergence, produce either a JSON integer or a JSON number with fractional part 0
    # manual and built_value require int (no double), json_serializable and freezed accept double.toInt()
    # So produce either an integer literal or a double literal with .0 fractional part
    id_int = draw(st.integers(min_value=-(2**63), max_value=2**63-1))
    id_as_int_literal = str(id_int)
    # double literal with .0 fractional part, but same numeric value
    id_as_double_literal = str(float(id_int)) + ".0" if id_int != 0 else "0.0"
    id_literal = draw(st.sampled_from([id_as_int_literal, id_as_double_literal]))

    # amount: string, non-null, always present
    # Use a simple decimal string, e.g. "123.45"
    amount_str = draw(st.text(min_size=1, max_size=10, alphabet=st.characters(blacklist_characters='"\\')))
    amount_json = json_string(amount_str)

    # name: nullable string, can be null or string
    # To provoke divergence, sometimes null, sometimes string
    name_is_null = draw(st.booleans())
    if name_is_null:
        name_json = "null"
    else:
        name_val = draw(st.text(min_size=0, max_size=20, alphabet=st.characters(blacklist_characters='"\\')))
        name_json = json_string(name_val)

    # status: one of "active", "inactive", "unknown"
    # Always valid string from these three to avoid rejection by all
    status_val = draw(st.sampled_from(["active", "inactive", "unknown"]))
    status_json = json_string(status_val)

    # tags: array of strings, always present (to avoid built_value silent default)
    # To provoke divergence, sometimes empty array, sometimes array of strings
    # Strings are simple ASCII without quotes or backslash
    tags_len = draw(st.integers(min_value=0, max_value=3))
    tags_elems = []
    for _ in range(tags_len):
        tag_str = draw(st.text(min_size=1, max_size=10, alphabet=st.characters(blacklist_characters='"\\')))
        tags_elems.append(json_string(tag_str))
    tags_json = "[" + ",".join(tags_elems) + "]"

    # child: nullable Record or null
    # To keep recursion bounded, only one level of recursion allowed
    # Compose child record similarly but with no child inside (child=null)
    child_is_null = draw(st.booleans())
    if child_is_null:
        child_json = "null"
    else:
        # child record fields:
        # id: integer only here (to keep complexity down)
        child_id = draw(st.integers(min_value=-(2**63), max_value=2**63-1))
        child_id_json = str(child_id)
        # amount: string
        child_amount_str = draw(st.text(min_size=1, max_size=10, alphabet=st.characters(blacklist_characters='"\\')))
        child_amount_json = json_string(child_amount_str)
        # name: nullable string
        child_name_is_null = draw(st.booleans())
        if child_name_is_null:
            child_name_json = "null"
        else:
            child_name_val = draw(st.text(min_size=0, max_size=20, alphabet=st.characters(blacklist_characters='"\\')))
            child_name_json = json_string(child_name_val)
        # status: one of three strings
        child_status_val = draw(st.sampled_from(["active", "inactive", "unknown"]))
        child_status_json = json_string(child_status_val)
        # tags: array of strings, possibly empty
        child_tags_len = draw(st.integers(min_value=0, max_value=2))
        child_tags_elems = []
        for _ in range(child_tags_len):
            tag_str = draw(st.text(min_size=1, max_size=10, alphabet=st.characters(blacklist_characters='"\\')))
            child_tags_elems.append(json_string(tag_str))
        child_tags_json = "[" + ",".join(child_tags_elems) + "]"
        # child.child must be null (one level recursion)
        child_child_json = "null"

        child_json = (
            "{" +
            f'"id":{child_id_json},' +
            f'"amount":{child_amount_json},' +
            f'"name":{child_name_json},' +
            f'"status":{child_status_json},' +
            f'"tags":{child_tags_json},' +
            f'"child":{child_child_json}' +
            "}"
        )

    # Compose top-level JSON object
    # To provoke divergence, sometimes omit "tags" field (built_value accepts, others reject)
    # But the prompt says all six fields always present in well-formed documents,
    # so to provoke divergence, produce two variants:
    # - all fields present (normal)
    # - tags missing (built_value accepts, others reject)
    omit_tags = draw(st.booleans())
    # But prompt says all six fields always present in well-formed document,
    # so omitting tags is a known divergence, so we include it as a candidate.

    # Compose fields in order id, amount, name, status, tags?, child
    fields = [
        f'"id":{id_literal}',
        f'"amount":{amount_json}',
        f'"name":{name_json}',
        f'"status":{status_json}',
    ]
    if not omit_tags:
        fields.append(f'"tags":{tags_json}')
    fields.append(f'"child":{child_json}')

    json_obj = "{" + ",".join(fields) + "}"

    return json_obj.encode("utf-8")