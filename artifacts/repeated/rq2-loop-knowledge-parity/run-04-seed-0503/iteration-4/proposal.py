from hypothesis import strategies as st

# Constants for fixed enums and limits
STATUS_VALUES = ['active', 'inactive', 'unknown']

# Helper to produce JSON string literals with proper escaping of quotes and backslashes
def json_string(s: str) -> str:
    # Minimal escaping for " and \ to keep JSON valid
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

# Compose JSON array of strings
def json_array_of_strings(lst):
    return '[' + ','.join(json_string(s) for s in lst) + ']'

# Compose JSON object from dict of key->json_value (already serialized strings)
def json_object(d):
    # keys are always strings, values are JSON text
    items = []
    for k, v in d.items():
        items.append(json_string(k) + ':' + v)
    return '{' + ','.join(items) + '}'

# Compose JSON number from int or float, ensuring no trailing .0 for ints
def json_number(n):
    if isinstance(n, int):
        return str(n)
    else:
        # For floats, use repr to preserve precision, but avoid scientific notation if possible
        s = repr(n)
        # JSON allows scientific notation, so repr is fine
        return s

@st.composite
def generated_json(draw) -> bytes:
    """
    Generate syntactically valid JSON objects matching the record schema,
    with controlled variations to maximize behavioral divergence between
    four Dart JSON deserializers.
    """

    # --- id field ---
    # id must be present and is int for manual and built_value,
    # but json_serializable and freezed accept double and convert to int.
    # jsonDecode converts large int literals out of 64-bit range to double.
    # So generate either:
    # - a true int within 64-bit range (safe for all)
    # - a double that is an integer value but out of 64-bit range (to cause divergence)
    # - a double with fractional part (should cause all to reject)
    id_type = draw(st.sampled_from(['int64', 'double_int', 'double_frac']))

    if id_type == 'int64':
        # int within signed 64-bit range
        id_val = draw(st.integers(min_value=-(2**63), max_value=2**63 - 1))
        id_json = json_number(id_val)
    elif id_type == 'double_int':
        # double representing an integer outside 64-bit range
        # choose a double integer > 2**63 or < -2**63
        # Use float to represent it
        # Pick sign
        sign = draw(st.sampled_from([-1, 1]))
        # Pick magnitude between 2**63 and 2**65 (to avoid too large)
        mag = draw(st.integers(min_value=2**63, max_value=2**65))
        val = float(sign * mag)
        id_val = val  # float
        id_json = json_number(val)
    else:
        # double with fractional part (should cause rejection by all)
        val = draw(st.floats(min_value=-1e10, max_value=1e10, allow_nan=False, allow_infinity=False))
        # Ensure fractional part
        if val == int(val):
            val += 0.1
        id_val = val
        id_json = json_number(val)

    # --- amount field ---
    # amount is a string, always present, no special known divergence
    # But can try empty string, numeric string, or normal string
    amount_val = draw(st.one_of(
        st.just("0"),
        st.just(""),
        st.text(min_size=1, max_size=10),
        st.from_regex(r"^-?\d+(\.\d+)?$", fullmatch=True).filter(lambda s: len(s) <= 10)
    ))
    amount_json = json_string(amount_val)

    # --- name field ---
    # nullable string, missing accepted by all, but we always include it (per schema)
    # name can be null or string
    name_val = draw(st.one_of(st.none(), st.text(min_size=0, max_size=20)))
    if name_val is None:
        name_json = "null"
    else:
        name_json = json_string(name_val)

    # --- status field ---
    # one of "active", "inactive", "unknown"
    # unrecognized strings rejected by all
    status_val = draw(st.sampled_from(STATUS_VALUES))
    status_json = json_string(status_val)

    # --- tags field ---
    # array of strings, always present in well-formed document
    # Missing tags is accepted only by built_value, rejected by others
    # To maximize divergence, sometimes omit tags field entirely
    omit_tags = draw(st.booleans())
    if not omit_tags:
        # tags present, array of strings (possibly empty)
        tags_len = draw(st.integers(min_value=0, max_value=5))
        tags_list = draw(st.lists(st.text(min_size=0, max_size=10), min_size=tags_len, max_size=tags_len))
        tags_json = json_array_of_strings(tags_list)

    # --- child field ---
    # nullable record or null
    # missing child accepted by all, but schema says always present
    # We'll always include child field (null or nested record)
    # Limit recursion depth to 1 (one level)
    # Generate child as either null or a record with no child (child=null)
    child_is_null = draw(st.booleans())
    if child_is_null:
        child_json = "null"
    else:
        # child record with child=null (no further recursion)
        # id: int64 only here to keep simple
        child_id = draw(st.integers(min_value=-(2**63), max_value=2**63 - 1))
        child_amount = draw(st.text(min_size=1, max_size=10))
        child_name = draw(st.one_of(st.none(), st.text(min_size=0, max_size=20)))
        child_status = draw(st.sampled_from(STATUS_VALUES))
        child_tags_len = draw(st.integers(min_value=0, max_value=3))
        child_tags_list = draw(st.lists(st.text(min_size=0, max_size=10), min_size=child_tags_len, max_size=child_tags_len))

        child_obj = {
            "id": json_number(child_id),
            "amount": json_string(child_amount),
            "name": "null" if child_name is None else json_string(child_name),
            "status": json_string(child_status),
            "tags": json_array_of_strings(child_tags_list),
            "child": "null"
        }
        child_json = json_object(child_obj)

    # Compose top-level object fields
    obj_fields = {
        "id": id_json,
        "amount": amount_json,
        "name": name_json,
        "status": status_json,
        "child": child_json,
    }
    if not omit_tags:
        obj_fields["tags"] = tags_json

    json_text = json_object(obj_fields)

    # Return bytes
    return json_text.encode("utf-8")