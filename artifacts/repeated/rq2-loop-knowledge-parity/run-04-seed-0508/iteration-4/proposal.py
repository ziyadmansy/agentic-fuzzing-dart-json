from hypothesis import strategies as st

# Constants for the "status" enum
STATUS_VALUES = ['"active"', '"inactive"', '"unknown"']

# Helper to produce a JSON string literal for a given Python string (no escapes needed for test)
def json_string(s: str) -> str:
    # We only generate simple ASCII strings without quotes or backslashes, so safe to quote directly
    return '"' + s + '"'

@st.composite
def generated_json(draw) -> bytes:
    """
    Generate syntactically valid JSON objects matching the schema, with subtle
    variations to provoke divergence between four Dart JSON deserializers.

    Schema:
    {
      "id": <integer or double (to test int/double boundary)>,
      "amount": <string>,
      "name": <string or null or missing>,
      "status": <one of "active", "inactive", "unknown"> or invalid string,
      "tags": <array of strings> or missing (to test built_value default),
      "child": <record or null or missing>
    }

    Variations:
    - id: int or double (to test json_serializable/freezed vs manual/built_value)
    - tags: present or missing (to test built_value default empty list)
    - name: string, null, or missing (missing accepted by all)
    - child: null, missing, or a nested record (one level only)
    - status: valid enum or invalid string (invalid rejected by all)
    - amount: always string (no invalid to avoid universal rejection)
    """

    # --- id field ---
    # Generate an integer within 64-bit range or a double that represents an int or out-of-range int
    # to test int/double decoding differences.
    # We produce either:
    #  - a true int (int64 range)
    #  - a double with fractional part zero (e.g. 1.0) to test toInt()
    #  - a double outside int64 range (e.g. 2**63 as double)
    id_type = draw(st.sampled_from(['int', 'double_int', 'double_out_of_range']))
    if id_type == 'int':
        # int64 range: -2**63 .. 2**63-1
        id_val = draw(st.integers(min_value=-(2**63), max_value=2**63 - 1))
        id_json = str(id_val)
    elif id_type == 'double_int':
        # double with zero fractional part inside int64 range
        base = draw(st.integers(min_value=-(2**63), max_value=2**63 - 1))
        id_json = f"{float(base):.1f}"  # e.g. "123.0"
    else:
        # double outside int64 range, e.g. 2**63 or -2**63-1 as float
        val = draw(st.sampled_from([float(2**63), float(-(2**63) - 1)]))
        # Represent as JSON number with decimal point to force double
        id_json = f"{val:.1f}"

    # --- amount field ---
    # Always a string, non-empty ASCII without quotes/backslash
    amount_str = draw(st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=('Ll','Lu','Nd','Zs'), blacklist_characters=['"', '\\'])))
    amount_json = json_string(amount_str)

    # --- name field ---
    # nullable string or missing (missing accepted by all)
    name_choice = draw(st.sampled_from(['string', 'null', 'missing']))
    if name_choice == 'string':
        name_val = draw(st.text(min_size=0, max_size=10, alphabet=st.characters(whitelist_categories=('Ll','Lu','Nd','Zs'), blacklist_characters=['"', '\\'])))
        name_json = json_string(name_val)
        name_field = f'"name":{name_json}'
    elif name_choice == 'null':
        name_field = '"name":null'
    else:
        name_field = None  # missing

    # --- status field ---
    # Mostly valid enum, sometimes invalid string to test rejection by all (no divergence)
    # To maximize divergence, keep valid mostly, but allow invalid occasionally
    status_choice = draw(st.sampled_from(['valid', 'invalid']))
    if status_choice == 'valid':
        status_json = draw(st.sampled_from(STATUS_VALUES))
    else:
        # invalid string: a quoted string not in enum
        invalid_status = draw(st.text(min_size=1, max_size=10, alphabet=st.characters(blacklist_characters=['"', '\\'])))
        # Ensure invalid_status not in STATUS_VALUES
        while f'"{invalid_status}"' in STATUS_VALUES:
            invalid_status = draw(st.text(min_size=1, max_size=10, alphabet=st.characters(blacklist_characters=['"', '\\'])))
        status_json = json_string(invalid_status)

    # --- tags field ---
    # Present or missing (missing triggers built_value default empty list)
    tags_present = draw(st.booleans())
    if tags_present:
        # array of strings (empty or non-empty)
        tags_len = draw(st.integers(min_value=0, max_value=5))
        tags_elems = []
        for _ in range(tags_len):
            tag = draw(st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=('Ll','Lu','Nd','Zs'), blacklist_characters=['"', '\\'])))
            tags_elems.append(json_string(tag))
        tags_json = "[" + ",".join(tags_elems) + "]"
        tags_field = f'"tags":{tags_json}'
    else:
        tags_field = None  # missing

    # --- child field ---
    # null, missing, or one-level nested record (no deeper recursion)
    child_choice = draw(st.sampled_from(['null', 'missing', 'record']))

    def gen_child_record():
        # Generate a minimal valid record with no nested child (child missing)
        # id: int64 int only (to keep child simple)
        child_id = draw(st.integers(min_value=-(2**63), max_value=2**63 - 1))
        child_id_json = str(child_id)
        # amount: string
        child_amount = draw(st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=('Ll','Lu','Nd','Zs'), blacklist_characters=['"', '\\'])))
        child_amount_json = json_string(child_amount)
        # name: string or null or missing
        child_name_choice = draw(st.sampled_from(['string', 'null', 'missing']))
        if child_name_choice == 'string':
            child_name_val = draw(st.text(min_size=0, max_size=10, alphabet=st.characters(whitelist_categories=('Ll','Lu','Nd','Zs'), blacklist_characters=['"', '\\'])))
            child_name_json = json_string(child_name_val)
            child_name_field = f'"name":{child_name_json}'
        elif child_name_choice == 'null':
            child_name_field = '"name":null'
        else:
            child_name_field = None
        # status: valid enum only (to avoid universal rejection)
        child_status_json = draw(st.sampled_from(STATUS_VALUES))
        # tags: present or missing
        child_tags_present = draw(st.booleans())
        if child_tags_present:
            child_tags_len = draw(st.integers(min_value=0, max_value=3))
            child_tags_elems = []
            for _ in range(child_tags_len):
                tag = draw(st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=('Ll','Lu','Nd','Zs'), blacklist_characters=['"', '\\'])))
                child_tags_elems.append(json_string(tag))
            child_tags_json = "[" + ",".join(child_tags_elems) + "]"
            child_tags_field = f'"tags":{child_tags_json}'
        else:
            child_tags_field = None
        # child: missing (no recursion)
        fields = [
            f'"id":{child_id_json}',
            f'"amount":{child_amount_json}',
            child_name_field,
            f'"status":{child_status_json}',
            child_tags_field,
        ]
        fields = [f for f in fields if f is not None]
        return "{" + ",".join(fields) + "}"

    if child_choice == 'null':
        child_field = '"child":null'
    elif child_choice == 'missing':
        child_field = None
    else:
        child_json = gen_child_record()
        child_field = f'"child":{child_json}'

    # Compose top-level fields
    fields = [
        f'"id":{id_json}',
        f'"amount":{amount_json}',
    ]
    if name_field is not None:
        fields.append(name_field)
    fields.append(f'"status":{status_json}')
    if tags_field is not None:
        fields.append(tags_field)
    if child_field is not None:
        fields.append(child_field)

    json_text = "{" + ",".join(fields) + "}"
    return json_text.encode('utf-8')