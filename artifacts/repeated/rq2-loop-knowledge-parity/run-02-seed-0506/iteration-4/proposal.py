from hypothesis import strategies as st

# Constants for fixed sets
STATUS_VALUES = ['"active"', '"inactive"', '"unknown"']

# Helper to produce JSON string literal from a Python string (no escapes needed for test)
def json_str(s: str) -> str:
    # We only generate simple ASCII strings without quotes or backslashes,
    # so just wrap in quotes.
    return '"' + s + '"'

@st.composite
def generated_json(draw) -> bytes:
    """
    Generate syntactically valid JSON objects matching the record schema,
    with controlled variations to maximize behavioral divergence among
    four Dart JSON deserializers.

    Strategy:
    - id: either int (within 64-bit range), or a float representing an int,
      or an out-of-range int encoded as float (to trigger built_value vs others).
    - amount: string, always present.
    - name: string or null or missing (nullable).
    - status: one of the three valid strings, or an invalid string to cause rejection.
    - tags: array of strings, present or missing (missing triggers built_value acceptance only).
    - child: null or nested record (one level max), or missing (nullable).
    - Introduce exactly one or two subtle deviations per document to cause divergence.
    """

    # --- id field ---
    # Three variants:
    # 1) int in 64-bit range (accepted by all)
    # 2) float with integral value (accepted by json_serializable/freezed, rejected by manual/built_value)
    # 3) float out-of-64-bit-range (toInt() saturates in json_serializable/freezed, manual/built_value reject)
    id_variant = draw(st.integers(min_value=1, max_value=3))
    if id_variant == 1:
        # int in 64-bit range
        id_val = draw(st.integers(min_value=-(2**63), max_value=2**63 - 1))
        id_json = str(id_val)
    elif id_variant == 2:
        # float integral value within 64-bit range
        int_val = draw(st.integers(min_value=-(2**63), max_value=2**63 - 1))
        id_json = str(float(int_val))  # e.g. 123.0
    else:
        # float out-of-64-bit range (e.g. 2**63 as float)
        # This will saturate in toInt() for json_serializable/freezed
        # but manual/built_value expect int and reject
        big_int = 2**63  # one above max int64
        id_json = str(float(big_int))  # e.g. 9223372036854775808.0

    # --- amount field ---
    # Always present, string, non-empty ascii without quotes or backslash
    amount_val = draw(st.text(min_size=1, max_size=10, alphabet=st.characters(blacklist_characters='"\\')))
    amount_json = json_str(amount_val)

    # --- name field ---
    # nullable string or null or missing
    name_choice = draw(st.sampled_from(['string', 'null', 'missing']))
    if name_choice == 'string':
        name_val = draw(st.text(min_size=0, max_size=10, alphabet=st.characters(blacklist_characters='"\\')))
        name_json = json_str(name_val)
        name_field = f'"name":{name_json}'
    elif name_choice == 'null':
        name_field = '"name":null'
    else:
        name_field = None  # missing

    # --- status field ---
    # Mostly valid values, sometimes invalid string to cause rejection
    status_choice = draw(st.sampled_from(['valid', 'invalid']))
    if status_choice == 'valid':
        status_val = draw(st.sampled_from(STATUS_VALUES))
    else:
        # invalid string (not one of the three)
        invalid_status = draw(st.text(min_size=1, max_size=10, alphabet=st.characters(blacklist_characters='"\\')))
        # ensure invalid_status not in STATUS_VALUES (without quotes)
        while f'"{invalid_status}"' in STATUS_VALUES:
            invalid_status = draw(st.text(min_size=1, max_size=10, alphabet=st.characters(blacklist_characters='"\\')))
        status_val = json_str(invalid_status)
    status_field = f'"status":{status_val}'

    # --- tags field ---
    # Present or missing (missing triggers built_value acceptance only)
    tags_choice = draw(st.sampled_from(['present', 'missing']))
    if tags_choice == 'present':
        # array of strings (possibly empty)
        tags_len = draw(st.integers(min_value=0, max_value=3))
        tags_elems = []
        for _ in range(tags_len):
            tag = draw(st.text(min_size=1, max_size=10, alphabet=st.characters(blacklist_characters='"\\')))
            tags_elems.append(json_str(tag))
        tags_json = '[' + ','.join(tags_elems) + ']'
        tags_field = f'"tags":{tags_json}'
    else:
        tags_field = None  # missing

    # --- child field ---
    # nullable record or null or missing
    # To keep recursion bounded, only one level of child allowed
    child_choice = draw(st.sampled_from(['record', 'null', 'missing']))
    if child_choice == 'record':
        # child record with all fields present and valid (no further child)
        # id: int in 64-bit range
        child_id = draw(st.integers(min_value=-(2**63), max_value=2**63 - 1))
        child_id_json = str(child_id)
        # amount: string
        child_amount = draw(st.text(min_size=1, max_size=10, alphabet=st.characters(blacklist_characters='"\\')))
        child_amount_json = json_str(child_amount)
        # name: string or null (no missing)
        child_name_choice = draw(st.sampled_from(['string', 'null']))
        if child_name_choice == 'string':
            child_name_val = draw(st.text(min_size=0, max_size=10, alphabet=st.characters(blacklist_characters='"\\')))
            child_name_json = json_str(child_name_val)
        else:
            child_name_json = 'null'
        # status: valid status string
        child_status_json = draw(st.sampled_from(STATUS_VALUES))
        # tags: present, array of strings (possibly empty)
        child_tags_len = draw(st.integers(min_value=0, max_value=3))
        child_tags_elems = []
        for _ in range(child_tags_len):
            tag = draw(st.text(min_size=1, max_size=10, alphabet=st.characters(blacklist_characters='"\\')))
            child_tags_elems.append(json_str(tag))
        child_tags_json = '[' + ','.join(child_tags_elems) + ']'
        # child: null (no further recursion)
        child_child_json = 'null'

        child_fields = [
            f'"id":{child_id_json}',
            f'"amount":{child_amount_json}',
            f'"name":{child_name_json}',
            f'"status":{child_status_json}',
            f'"tags":{child_tags_json}',
            f'"child":{child_child_json}',
        ]
        child_field = '"child":{' + ','.join(child_fields) + '}'
    elif child_choice == 'null':
        child_field = '"child":null'
    else:
        child_field = None  # missing

    # Compose top-level fields list
    fields = [
        f'"id":{id_json}',
        f'"amount":{amount_json}',
        status_field,
    ]
    if name_field is not None:
        fields.append(name_field)
    if tags_field is not None:
        fields.append(tags_field)
    if child_field is not None:
        fields.append(child_field)

    # Shuffle fields order to avoid positional bias
    # Hypothesis does not have a built-in shuffle, so we simulate by drawing a permutation
    # of indices and reorder fields accordingly.
    indices = list(range(len(fields)))
    shuffled_indices = draw(st.permutations(indices))
    shuffled_fields = [fields[i] for i in shuffled_indices]

    json_text = '{' + ','.join(shuffled_fields) + '}'
    return json_text.encode('utf-8')