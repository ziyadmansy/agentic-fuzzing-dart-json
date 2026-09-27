from hypothesis import strategies as st

# Constants for fixed sets
STATUS_VALUES = ['"active"', '"inactive"', '"unknown"']

# Helper to produce a JSON string literal from a Python string (no escapes needed for test)
def json_str(s: str) -> str:
    # Minimal escaping for quotes and backslash
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

@st.composite
def generated_json(draw) -> bytes:
    """
    Generate syntactically valid JSON objects as bytes, matching the record schema,
    with controlled variations to maximize behavioral divergence between four Dart JSON deserializers.
    """

    # --- id field ---
    # To exploit the difference in id decoding:
    # manual and built_value require true int (no double),
    # json_serializable and freezed accept double and convert to int via toInt().
    # jsonDecode turns integer literals outside 64-bit range into double.
    # So generate:
    # - int in 64-bit range (accepted by all)
    # - int outside 64-bit range (encoded as number literal, but jsonDecode makes it double)
    # - double with fractional part (rejected by all)
    id_case = draw(st.sampled_from(['int64', 'int64_out_of_range', 'double_fractional']))

    if id_case == 'int64':
        # int in 64-bit range, encoded as JSON integer literal
        # range: -2**63 .. 2**63-1
        id_val = draw(st.integers(min_value=-(2**63), max_value=2**63 - 1))
        id_json = str(id_val)
    elif id_case == 'int64_out_of_range':
        # int outside 64-bit range, encoded as JSON integer literal
        # e.g. 2**63 or -2**63 - 1
        # jsonDecode will parse as double, accepted only by json_serializable/freezed
        id_val = draw(st.sampled_from([2**63, -(2**63) - 1, 2**65, -(2**65)]))
        id_json = str(id_val)
    else:
        # double with fractional part, e.g. 1.5
        id_val = draw(st.floats(min_value=-1e10, max_value=1e10, allow_infinity=False, allow_nan=False))
        # force fractional part
        if id_val == int(id_val):
            id_val += 0.5
        id_json = repr(id_val)

    # --- amount field ---
    # amount is a string, always present
    # To cause divergence, try normal string or empty string or numeric string
    amount_val = draw(st.one_of(
        st.text(min_size=1, max_size=10),
        st.just(""),  # empty string
        st.integers(min_value=0, max_value=1000000).map(str),
    ))
    amount_json = json_str(amount_val)

    # --- name field ---
    # nullable string, missing allowed and accepted by all
    # But missing name is accepted by all, so no divergence here
    # Instead, produce either null or string (including empty string)
    name_val = draw(st.one_of(
        st.none(),
        st.text(min_size=0, max_size=10),
    ))
    if name_val is None:
        name_json = "null"
    else:
        name_json = json_str(name_val)

    # --- status field ---
    # one of "active", "inactive", "unknown"
    # unrecognized string rejected by all, no divergence
    # So pick only valid values
    status_json = draw(st.sampled_from(STATUS_VALUES))

    # --- tags field ---
    # array of strings, always present in well-formed document
    # Missing tags accepted only by built_value (others reject)
    # So to cause divergence, sometimes omit tags field
    tags_omit = draw(st.booleans())
    if not tags_omit:
        # present tags: array of strings (possibly empty)
        # To cause divergence, try empty array or array with empty string or normal strings
        tags_list = draw(st.lists(st.text(min_size=0, max_size=10), max_size=5))
        # encode tags array
        tags_json = "[" + ",".join(json_str(t) for t in tags_list) + "]"

    # --- child field ---
    # nullable record, one level recursion normally
    # missing child accepted by all
    # To keep recursion bounded, limit depth to 1
    # child can be null or a record with no child (child=null)
    child_omit = draw(st.booleans())
    if not child_omit:
        # child present: either null or a record with child=null
        child_null = draw(st.booleans())
        if child_null:
            child_json = "null"
        else:
            # child record with child=null, all fields present and valid
            # id: int64 in range
            child_id = draw(st.integers(min_value=-(2**63), max_value=2**63 - 1))
            child_id_json = str(child_id)
            # amount: non-empty string
            child_amount = draw(st.text(min_size=1, max_size=10))
            child_amount_json = json_str(child_amount)
            # name: null or string
            child_name = draw(st.one_of(st.none(), st.text(min_size=0, max_size=10)))
            child_name_json = "null" if child_name is None else json_str(child_name)
            # status: valid value
            child_status_json = draw(st.sampled_from(STATUS_VALUES))
            # tags: present, array of strings (empty or not)
            child_tags_list = draw(st.lists(st.text(min_size=0, max_size=10), max_size=3))
            child_tags_json = "[" + ",".join(json_str(t) for t in child_tags_list) + "]"
            # child: null
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
    # --- Compose top-level JSON object ---
    # Fields: id, amount, name, status, tags?, child?
    # Order fields in fixed order for readability
    fields = [
        f'"id":{id_json}',
        f'"amount":{amount_json}',
        f'"name":{name_json}',
        f'"status":{status_json}',
    ]
    if not tags_omit:
        fields.append(f'"tags":{tags_json}')
    if not child_omit:
        fields.append(f'"child":{child_json}')

    json_text = "{" + ",".join(fields) + "}"

    return json_text.encode("utf-8")