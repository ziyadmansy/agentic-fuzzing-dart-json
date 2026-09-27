from hypothesis import strategies as st

# Helper to produce a JSON string literal with proper escaping of backslash and quote
def json_string_literal(s: str) -> str:
    # Escape backslash and double quote, and control chars \b\f\n\r\t as JSON requires
    # We do minimal escaping here for simplicity
    s = s.replace('\\', '\\\\').replace('"', '\\"')
    s = s.replace('\b', '\\b').replace('\f', '\\f').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
    return '"' + s + '"'

# Compose JSON array of strings from Python list of strings
def json_array_of_strings(lst):
    return '[' + ','.join(json_string_literal(s) for s in lst) + ']'

# Compose JSON object from dict of key->json_value (already serialized strings)
def json_object(d):
    # keys are always strings, so quote keys
    items = []
    for k, v in d.items():
        items.append(json_string_literal(k) + ':' + v)
    return '{' + ','.join(items) + '}'

@st.composite
def generated_json(draw) -> bytes:
    """
    Generate syntactically valid JSON objects as bytes, matching the record schema:
    {
      "id": <integer or double that may saturate>,
      "amount": <string>,
      "name": <string or null or missing>,
      "status": <"active"|"inactive"|"unknown" or unrecognized string>,
      "tags": <array of strings or missing>,
      "child": <record or null or missing>
    }

    Introduce subtle divergences:
    - id: sometimes int, sometimes double (to trigger json_serializable/freezed accepting double, manual/built_value rejecting)
    - tags: sometimes missing (built_value accepts, others reject)
    - name: sometimes null, sometimes missing (all accept)
    - child: sometimes null, sometimes missing, sometimes a nested record (one level recursion)
    - status: mostly valid, sometimes unrecognized string (all reject)
    - amount: always string (non-null)
    """

    # id field: generate int or double near int64 boundaries or normal int
    # int64 range: -2**63 .. 2**63-1
    INT64_MIN = -2**63
    INT64_MAX = 2**63 - 1

    # Strategy for id:
    # - 60% int in range
    # - 20% double with integral value (toInt() accepts)
    # - 20% double with fractional part (should cause rejection)
    id_kind = draw(st.sampled_from(['int', 'double_int', 'double_frac']))

    if id_kind == 'int':
        # Pick int in int64 range, but also some outside range to cause double from jsonDecode
        # But jsonDecode turns out-of-range int literals into double, so to test that, we must produce a number literal that looks like int but is out of range.
        # We cannot produce invalid JSON number syntax, so produce a number literal that is a double but looks like int.
        # We'll produce a JSON number literal as string later.
        # For now, pick int in int64 range.
        id_val = draw(st.integers(min_value=INT64_MIN, max_value=INT64_MAX))
        # Represent as JSON integer literal (no decimal point)
        id_json = str(id_val)
    elif id_kind == 'double_int':
        # double with integral value, in int64 range or outside
        # Pick a float that is integral but represented as double literal with decimal point
        base_int = draw(st.integers(min_value=INT64_MIN, max_value=INT64_MAX))
        id_val = float(base_int)
        # Represent as JSON number literal with ".0" to force double
        id_json = str(base_int) + '.0'
    else:
        # double with fractional part (should cause rejection)
        base_int = draw(st.integers(min_value=INT64_MIN, max_value=INT64_MAX))
        frac = draw(st.floats(min_value=0.1, max_value=0.9, allow_nan=False, allow_infinity=False))
        id_val = float(base_int) + frac
        # Represent as JSON number literal with fractional part
        # Use repr to get decimal form
        id_json = repr(id_val)
        # repr may produce scientific notation, which is valid JSON number

    # amount: always string, non-null, non-empty, printable ASCII
    amount_str = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(min_codepoint=32, max_codepoint=126)))
    amount_json = json_string_literal(amount_str)

    # name: string or null or missing (all accept missing or null)
    name_choice = draw(st.sampled_from(['string', 'null', 'missing']))
    if name_choice == 'string':
        name_val = draw(st.text(min_size=0, max_size=20, alphabet=st.characters(min_codepoint=32, max_codepoint=126)))
        name_json = json_string_literal(name_val)
    elif name_choice == 'null':
        name_json = 'null'
    else:
        name_json = None  # missing

    # status: mostly valid, sometimes unrecognized string (all reject unrecognized)
    # To maximize disagreements, mostly valid
    status_choice = draw(st.sampled_from(['valid', 'invalid']))
    if status_choice == 'valid':
        status_val = draw(st.sampled_from(['active', 'inactive', 'unknown']))
        status_json = json_string_literal(status_val)
    else:
        # unrecognized string, e.g. "pending", "deleted", "foo"
        status_val = draw(st.text(min_size=1, max_size=10, alphabet=st.characters(min_codepoint=97, max_codepoint=122)))
        # avoid accidentally picking valid status
        while status_val in ('active', 'inactive', 'unknown'):
            status_val = draw(st.text(min_size=1, max_size=10, alphabet=st.characters(min_codepoint=97, max_codepoint=122)))
        status_json = json_string_literal(status_val)

    # tags: array of strings or missing
    # Missing triggers built_value accept, others reject
    tags_choice = draw(st.sampled_from(['present', 'missing']))
    if tags_choice == 'present':
        # array of 0 to 5 strings, each string 0-10 chars ascii printable
        tags_list = draw(st.lists(st.text(min_size=0, max_size=10, alphabet=st.characters(min_codepoint=32, max_codepoint=126)), max_size=5))
        tags_json = json_array_of_strings(tags_list)
    else:
        tags_json = None  # missing

    # child: null or missing or nested record (one level recursion)
    # To avoid infinite recursion, limit depth to 1
    child_choice = draw(st.sampled_from(['null', 'missing', 'nested']))

    if child_choice == 'null':
        child_json = 'null'
    elif child_choice == 'missing':
        child_json = None
    else:
        # nested record: recursive call but no further recursion inside child
        # We produce a nested record with no child field (missing) to avoid deeper recursion
        # Compose nested record fields similarly but no child field
        # id nested: int in int64 range, always int (to reduce complexity)
        nested_id = draw(st.integers(min_value=INT64_MIN, max_value=INT64_MAX))
        nested_id_json = str(nested_id)
        nested_amount = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(min_codepoint=32, max_codepoint=126)))
        nested_amount_json = json_string_literal(nested_amount)
        nested_name_choice = draw(st.sampled_from(['string', 'null', 'missing']))
        if nested_name_choice == 'string':
            nested_name_val = draw(st.text(min_size=0, max_size=20, alphabet=st.characters(min_codepoint=32, max_codepoint=126)))
            nested_name_json = json_string_literal(nested_name_val)
        elif nested_name_choice == 'null':
            nested_name_json = 'null'
        else:
            nested_name_json = None
        nested_status_val = draw(st.sampled_from(['active', 'inactive', 'unknown']))
        nested_status_json = json_string_literal(nested_status_val)
        nested_tags_choice = draw(st.sampled_from(['present', 'missing']))
        if nested_tags_choice == 'present':
            nested_tags_list = draw(st.lists(st.text(min_size=0, max_size=10, alphabet=st.characters(min_codepoint=32, max_codepoint=126)), max_size=5))
            nested_tags_json = json_array_of_strings(nested_tags_list)
        else:
            nested_tags_json = None

        nested_fields = {
            'id': nested_id_json,
            'amount': nested_amount_json,
            'status': nested_status_json,
        }
        if nested_name_json is not None:
            nested_fields['name'] = nested_name_json
        if nested_tags_json is not None:
            nested_fields['tags'] = nested_tags_json
        # no child field in nested record to avoid recursion

        child_json = json_object(nested_fields)

    # Compose top-level object fields
    top_fields = {
        'id': id_json,
        'amount': amount_json,
        'status': status_json,
    }
    if name_json is not None:
        top_fields['name'] = name_json
    if tags_json is not None:
        top_fields['tags'] = tags_json
    if child_json is not None:
        top_fields['child'] = child_json

    json_text = json_object(top_fields)
    return json_text.encode('utf-8')