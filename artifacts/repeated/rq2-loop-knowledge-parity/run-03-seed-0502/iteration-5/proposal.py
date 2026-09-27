from hypothesis import strategies as st

# Constants for status field
STATUS_VALUES = ['"active"', '"inactive"', '"unknown"']

# Helper to produce a JSON string literal with proper escaping of quotes and backslashes
def json_string_literal(s: str) -> str:
    # Minimal escaping for " and \ only, enough for Hypothesis-generated strings
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

@st.composite
def generated_json(draw) -> bytes:
    """
    Produce syntactically valid JSON objects as bytes, matching the schema:
    {
      "id": <integer or double (to exploit id decoding differences)>,
      "amount": <string>,
      "name": <string or null>,
      "status": <"active"|"inactive"|"unknown">,
      "tags": <array of strings> or missing (to trigger built_value vs others),
      "child": <record or null or missing (missing allowed)>,
    }
    Introduce subtle divergences:
    - id as int or double (including out-of-64-bit-range double)
    - tags present or missing (built_value accepts missing tags)
    - child present or missing or null
    - name present as string or null or missing (missing accepted)
    - amount always string (non-nullable)
    - status always one of the three strings (non-nullable)
    """

    # id: either int (within 64-bit range) or double (including out-of-range)
    # To maximize divergence, sometimes produce a double outside int64 range
    id_choice = draw(st.integers(min_value=0, max_value=3))
    if id_choice == 0:
        # int in 64-bit range
        id_val = draw(st.integers(min_value=-(2**63), max_value=2**63 - 1))
        id_json = str(id_val)
    elif id_choice == 1:
        # double representing an integer within 64-bit range (e.g. 1.0)
        int_val = draw(st.integers(min_value=-(2**63), max_value=2**63 - 1))
        id_json = f"{int_val}.0"
    elif id_choice == 2:
        # double outside 64-bit int range positive (e.g. 2**63 as double)
        dbl_val = float(2**63 + draw(st.integers(min_value=1, max_value=1000)))
        id_json = repr(dbl_val)
    else:
        # double outside 64-bit int range negative
        dbl_val = float(-(2**63) - draw(st.integers(min_value=1, max_value=1000)))
        id_json = repr(dbl_val)

    # amount: non-null string, non-empty to avoid trivial rejection
    amount_str = draw(st.text(min_size=1)).replace('"', '\\"').replace('\\', '\\\\')
    amount_json = json_string_literal(amount_str)

    # name: nullable string or missing (missing accepted by all)
    name_option = draw(st.sampled_from(['string', 'null', 'missing']))
    if name_option == 'string':
        name_val = draw(st.text()).replace('"', '\\"').replace('\\', '\\\\')
        name_json = json_string_literal(name_val)
        name_field = f'"name":{name_json}'
    elif name_option == 'null':
        name_field = '"name":null'
    else:
        name_field = None  # missing

    # status: always one of the three valid strings
    status_json = draw(st.sampled_from(STATUS_VALUES))

    # tags: either present as array of strings or missing (to trigger divergence)
    tags_option = draw(st.sampled_from(['present', 'missing']))
    if tags_option == 'present':
        # array of strings, possibly empty (empty accepted by all)
        tags_list = draw(st.lists(st.text(min_size=0).map(lambda s: s.replace('"', '\\"').replace('\\', '\\\\')), max_size=5))
        # build JSON array string
        tags_json = '[' + ','.join(json_string_literal(t) for t in tags_list) + ']'
        tags_field = f'"tags":{tags_json}'
    else:
        tags_field = None  # missing

    # child: nullable record or missing
    # To keep recursion bounded, child record has no child field (always null)
    child_option = draw(st.sampled_from(['record', 'null', 'missing']))
    if child_option == 'record':
        # child record with all fields present, child=null (no recursion)
        # For child.id, use int in range to avoid complexity in nested
        child_id = draw(st.integers(min_value=-(2**63), max_value=2**63 - 1))
        child_id_json = str(child_id)
        child_amount = draw(st.text(min_size=1)).replace('"', '\\"').replace('\\', '\\\\')
        child_amount_json = json_string_literal(child_amount)
        child_name_option = draw(st.sampled_from(['string', 'null', 'missing']))
        if child_name_option == 'string':
            child_name_val = draw(st.text()).replace('"', '\\"').replace('\\', '\\\\')
            child_name_json = json_string_literal(child_name_val)
            child_name_field = f'"name":{child_name_json}'
        elif child_name_option == 'null':
            child_name_field = '"name":null'
        else:
            child_name_field = None

        child_status_json = draw(st.sampled_from(STATUS_VALUES))
        child_tags_list = draw(st.lists(st.text(min_size=0).map(lambda s: s.replace('"', '\\"').replace('\\', '\\\\')), max_size=3))
        child_tags_json = '[' + ','.join(json_string_literal(t) for t in child_tags_list) + ']'
        child_tags_field = f'"tags":{child_tags_json}'

        # child.child is always null to avoid recursion
        child_child_field = '"child":null'

        child_fields = [
            f'"id":{child_id_json}',
            f'"amount":{child_amount_json}',
            child_name_field,
            f'"status":{child_status_json}',
            child_tags_field,
            child_child_field,
        ]
        child_fields = [f for f in child_fields if f is not None]
        child_json = '{' + ','.join(child_fields) + '}'
        child_field = f'"child":{child_json}'
    elif child_option == 'null':
        child_field = '"child":null'
    else:
        child_field = None  # missing

    # Compose top-level fields, omitting those that are None (missing)
    fields = [
        f'"id":{id_json}',
        f'"amount":{amount_json}',
        name_field,
        f'"status":{status_json}',
        tags_field,
        child_field,
    ]
    fields = [f for f in fields if f is not None]

    json_text = '{' + ','.join(fields) + '}'
    return json_text.encode('utf-8')