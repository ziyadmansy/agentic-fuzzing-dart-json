from hypothesis import strategies as st

# Constants for the "status" field
STATUS_VALUES = ['"active"', '"inactive"', '"unknown"']

# Helper to produce a JSON string literal from a Python str (escaping quotes and backslashes)
def json_string_literal(s: str) -> str:
    # Minimal escaping for JSON string literals: backslash and quote
    # Hypothesis strings won't contain control chars by default, so this suffices
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

@st.composite
def generated_json(draw) -> bytes:
    """
    Generate syntactically valid JSON objects as bytes, matching the schema with
    controlled variations to provoke divergence among four Dart JSON deserializers.
    """

    # --- id field ---
    # To exploit difference in id decoding:
    # manual and built_value require int (jsonDecode produces int for integer literals in range)
    # json_serializable and freezed accept double and convert to int via toInt()
    # jsonDecode produces double for integer literals outside 64-bit range.
    # So generate id as either:
    # - a JSON integer literal in 64-bit range (accepted by all)
    # - a JSON number literal outside 64-bit int range but integer-valued (encoded as double by jsonDecode)
    # - a JSON number literal with fractional part (should be rejected by all)
    # We'll produce mostly in-range ints and some out-of-range ints as doubles (e.g. 2^63)
    # and some fractional numbers to cause rejection.

    # 64-bit signed int range
    INT64_MIN = -(2**63)
    INT64_MAX = 2**63 - 1

    # Strategy for id:
    # 70% in-range int (as JSON int literal)
    # 15% out-of-range int (as JSON number with .0 fractional to force double)
    # 15% fractional number (to cause rejection)
    id_choice = draw(st.weighted_choices([
        (0.7, 'in_range_int'),
        (0.15, 'out_of_range_int_double'),
        (0.15, 'fractional_double'),
    ]))

    if id_choice == 'in_range_int':
        id_val = draw(st.integers(min_value=INT64_MIN, max_value=INT64_MAX))
        id_json = str(id_val)
    elif id_choice == 'out_of_range_int_double':
        # Pick an integer outside 64-bit range, encode as float with .0
        # Use 2^63 or -2^63-1 or larger
        out_of_range_int = draw(st.sampled_from([2**63, 2**63+1, 2**63+12345, -(2**63)-1, -(2**63)-12345]))
        id_json = str(out_of_range_int) + ".0"
    else:
        # fractional double, e.g. 123.456
        fractional = draw(st.floats(min_value=-1e12, max_value=1e12, allow_nan=False, allow_infinity=False))
        # Ensure fractional part is nonzero
        fractional = fractional if fractional % 1 != 0 else fractional + 0.1
        # Format with decimal point
        id_json = repr(fractional)

    # --- amount field ---
    # amount is a string, always present, non-null
    # Generate a JSON string literal with ASCII printable chars, length 1-20
    amount_str = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))))
    amount_json = json_string_literal(amount_str)

    # --- name field ---
    # nullable string, optional presence: always present (per schema), but can be null or string
    # Generate either null or string (empty allowed)
    name_is_null = draw(st.booleans())
    if name_is_null:
        name_json = "null"
    else:
        name_str = draw(st.one_of(
            st.text(min_size=0, max_size=20, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))),
            st.just("")  # empty string allowed
        ))
        name_json = json_string_literal(name_str)

    # --- status field ---
    # one of "active", "inactive", "unknown"
    # Also try to provoke rejection by generating invalid strings rarely
    status_choice = draw(st.weighted_choices([
        (0.9, 'valid'),
        (0.1, 'invalid'),
    ]))
    if status_choice == 'valid':
        status_json = draw(st.sampled_from(STATUS_VALUES))
    else:
        # invalid status string: random string not in STATUS_VALUES
        # generate a string not equal to any valid status
        invalid_status = draw(st.text(min_size=1, max_size=10).filter(lambda s: f'"{s}"' not in STATUS_VALUES))
        status_json = json_string_literal(invalid_status)

    # --- tags field ---
    # array of strings, always present (but built_value accepts missing tags as empty list)
    # To provoke divergence, sometimes omit tags field (built_value accepts, others reject)
    # Sometimes present with empty array, sometimes with array of strings
    tags_field_present = draw(st.booleans())
    if tags_field_present:
        # tags array: length 0-5, strings length 1-10 ascii printable
        tags_list = draw(st.lists(
            st.text(min_size=1, max_size=10, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))),
            min_size=0, max_size=5
        ))
        # encode tags array as JSON array of string literals
        tags_json = "[" + ",".join(json_string_literal(t) for t in tags_list) + "]"
    else:
        tags_json = None  # omit field

    # --- child field ---
    # nullable Record or null
    # To keep recursion bounded, limit depth to 1 (child.child always null)
    # child can be null or a nested record with child=null
    # To provoke divergence, sometimes omit child (all accept missing nullable fields)
    child_field_present = draw(st.booleans())
    if child_field_present:
        # child is either null or a nested record with child=null
        child_is_null = draw(st.booleans())
        if child_is_null:
            child_json = "null"
        else:
            # nested record with child=null, all fields present and valid
            # For nested record, use simpler fixed valid values to avoid combinatorial explosion
            nested_id = draw(st.integers(min_value=0, max_value=1000))
            nested_amount = json_string_literal("nested_amt")
            nested_name = draw(st.one_of(st.just("null"), st.just(json_string_literal("nested_name"))))
            if nested_name == "null":
                nested_name_json = "null"
            else:
                nested_name_json = nested_name
            nested_status = draw(st.sampled_from(STATUS_VALUES))
            nested_tags = "[]"
            nested_child = "null"
            child_json = (
                "{" +
                f'"id":{nested_id},' +
                f'"amount":{nested_amount},' +
                f'"name":{nested_name_json},' +
                f'"status":{nested_status},' +
                f'"tags":{nested_tags},' +
                f'"child":{nested_child}' +
                "}"
            )
    else:
        child_json = None  # omit field

    # --- Compose top-level JSON object ---
    # Fields: id, amount, name, status, tags?, child?
    # Order fields in canonical order for readability
    fields = [
        ('"id"', id_json),
        ('"amount"', amount_json),
        ('"name"', name_json),
        ('"status"', status_json),
    ]
    if tags_json is not None:
        fields.append(('"tags"', tags_json))
    if child_json is not None:
        fields.append(('"child"', child_json))

    # Join fields with commas
    json_text = "{" + ",".join(f"{k}:{v}" for k, v in fields) + "}"

    # Return as bytes
    return json_text.encode('utf-8')