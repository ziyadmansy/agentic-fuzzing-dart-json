from hypothesis import strategies as st

# Constants for fixed sets
STATUS_VALUES = ['"active"', '"inactive"', '"unknown"']

# Helper to produce a JSON string literal with proper escaping for Hypothesis strings
def json_string_literal(s: str) -> str:
    # Escape backslash and double quote for JSON string literal
    s = s.replace('\\', '\\\\').replace('"', '\\"')
    # Also escape control characters minimally (newline, tab)
    s = s.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
    return '"' + s + '"'

@st.composite
def generated_json(draw) -> bytes:
    """
    Generate syntactically valid JSON objects as bytes, representing the Record schema,
    with subtle variations to trigger divergence among four Dart JSON deserializers.
    """

    # --- Primitive fields ---

    # id: integer or double (to trigger divergence on id decoding)
    # Manual and built_value require int; json_serializable and freezed accept double.toInt()
    # We produce either a JSON integer literal or a JSON number literal with decimal point.
    # Also produce out-of-64-bit-range integers as doubles (e.g. > 2**63)
    id_choice = draw(st.integers(min_value=-(2**63), max_value=2**63 - 1).map(str) | 
                     st.floats(min_value=-(2**63)*10, max_value=(2**63)*10, allow_nan=False, allow_infinity=False)
                       .filter(lambda f: f != int(f))  # force fractional
                       .map(lambda f: format(f, '.6f').rstrip('0').rstrip('.')))
    # id_choice is a string representing a JSON number (int or float)

    # amount: string, always present, non-null
    # Use simple decimal strings, or sometimes numeric strings with leading zeros or signs to test parsing
    amount_str = draw(st.text(min_size=1, max_size=10).filter(lambda s: all(c in '0123456789+-.' for c in s)))
    amount_json = json_string_literal(amount_str)

    # name: nullable string or null
    # Use None or a string, including empty string and unicode
    name_val = draw(st.none() | st.text(min_size=0, max_size=20))
    if name_val is None:
        name_json = "null"
    else:
        name_json = json_string_literal(name_val)

    # status: one of the three known strings, or an unknown string to test rejection
    # But per known facts, unknown status is rejected by all four, so no divergence there.
    # So only produce known status values.
    status_json = draw(st.sampled_from(STATUS_VALUES))

    # tags: array of strings, or missing (to trigger divergence)
    # built_value accepts missing tags as empty list, others reject missing tags
    # So we produce either missing tags or present tags (empty or non-empty)
    tags_present = draw(st.booleans())
    if tags_present:
        # tags array: zero or more strings
        tags_list = draw(st.lists(st.text(min_size=0, max_size=10), max_size=5))
        # JSON array of strings
        tags_json = '[' + ','.join(json_string_literal(t) for t in tags_list) + ']'
    else:
        tags_json = None  # missing

    # child: nullable Record or null
    # To keep recursion bounded, limit depth to 1 (child can be null or a record with no child)
    # We produce either null or a record with child=null (no further recursion)
    child_present = draw(st.booleans())
    if child_present:
        # child record with no child (child=null)
        # We reuse the same field generation but with child=null forced
        # id for child: integer or float as above
        child_id_choice = draw(st.integers(min_value=-(2**63), max_value=2**63 - 1).map(str) | 
                               st.floats(min_value=-(2**63)*10, max_value=(2**63)*10, allow_nan=False, allow_infinity=False)
                                 .filter(lambda f: f != int(f))
                                 .map(lambda f: format(f, '.6f').rstrip('0').rstrip('.')))
        child_amount_str = draw(st.text(min_size=1, max_size=10).filter(lambda s: all(c in '0123456789+-.' for c in s)))
        child_amount_json = json_string_literal(child_amount_str)
        child_name_val = draw(st.none() | st.text(min_size=0, max_size=20))
        if child_name_val is None:
            child_name_json = "null"
        else:
            child_name_json = json_string_literal(child_name_val)
        child_status_json = draw(st.sampled_from(STATUS_VALUES))
        child_tags_present = draw(st.booleans())
        if child_tags_present:
            child_tags_list = draw(st.lists(st.text(min_size=0, max_size=10), max_size=3))
            child_tags_json = '[' + ','.join(json_string_literal(t) for t in child_tags_list) + ']'
        else:
            child_tags_json = None  # missing

        # Compose child JSON object fields
        child_fields = [
            '"id":' + child_id_choice,
            '"amount":' + child_amount_json,
            '"name":' + child_name_json,
            '"status":' + child_status_json,
        ]
        if child_tags_json is not None:
            child_fields.append('"tags":' + child_tags_json)
        # else omit tags to trigger built_value default empty list

        # child field is null (no recursion)
        child_fields.append('"child":null')

        child_json_obj = '{' + ','.join(child_fields) + '}'
        child_json = child_json_obj
    else:
        child_json = "null"

    # Compose top-level JSON object fields
    fields = [
        '"id":' + id_choice,
        '"amount":' + amount_json,
        '"name":' + name_json,
        '"status":' + status_json,
    ]
    if tags_json is not None:
        fields.append('"tags":' + tags_json)
    # else omit tags to trigger built_value default empty list

    fields.append('"child":' + child_json)

    # Shuffle fields order to avoid positional bias
    # Hypothesis does not have a built-in shuffle for lists, so we do a simple random permutation by drawing a permutation of indices
    indices = list(range(len(fields)))
    permuted_indices = draw(st.permutations(indices))
    fields_permuted = [fields[i] for i in permuted_indices]

    json_obj = '{' + ','.join(fields_permuted) + '}'

    return json_obj.encode('utf-8')