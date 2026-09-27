from hypothesis import strategies as st

# Constants for fields with limited domain
STATUS_VALUES = ['"active"', '"inactive"', '"unknown"']

# Helper to produce JSON string literal with proper escaping of " and \
def json_string_literal(s: str) -> str:
    # minimal escaping for " and \, no control chars for simplicity
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

@st.composite
def generated_json(draw) -> bytes:
    """
    Generate syntactically valid JSON objects as bytes, representing the described Record schema,
    with subtle variations to maximize behavioral divergence among four Dart JSON deserializers.
    """

    # --- id field ---
    # id must be present and is int for manual and built_value, but json_serializable/freezed accept double.toInt()
    # So generate either:
    # - a true int within 64-bit range (safe)
    # - a double that jsonDecode will parse as double but toInt() saturates (e.g. > 2**63)
    # Also try edge cases: int64 min/max, just outside range as double
    int64_min = -(2**63)
    int64_max = 2**63 - 1

    id_choice = draw(st.integers(min_value=0, max_value=4))
    if id_choice == 0:
        # Normal int in range
        id_val = draw(st.integers(min_value=int64_min, max_value=int64_max))
        id_json = str(id_val)
    elif id_choice == 1:
        # Large int outside 64-bit range, encoded as JSON number literal (will be parsed as double)
        # Use a number > int64_max + 1, e.g. 2**63 + random offset
        large_int = 2**63 + draw(st.integers(min_value=1, max_value=1000))
        # JSON number literal (no quotes)
        id_json = str(large_int)
    elif id_choice == 2:
        # Large negative int outside 64-bit range, encoded as JSON number literal (double)
        large_neg = -(2**63) - draw(st.integers(min_value=1, max_value=1000))
        id_json = str(large_neg)
    elif id_choice == 3:
        # Floating point number with fractional part (should be rejected by manual and built_value)
        # json_serializable/freezed accept (num).toInt() but fractional part lost
        float_val = draw(st.floats(min_value=-1e5, max_value=1e5, allow_nan=False, allow_infinity=False))
        # Format float with decimal point to ensure JSON parses as double
        id_json = format(float_val, '.6f')
    else:
        # Normal int in range again
        id_val = draw(st.integers(min_value=int64_min, max_value=int64_max))
        id_json = str(id_val)

    # --- amount field ---
    # amount is string, required, non-nullable
    # Try normal string or empty string or numeric string or string with unicode escapes
    amount_str = draw(st.one_of(
        st.text(min_size=1, max_size=10).map(json_string_literal),
        st.just(json_string_literal("")),
        st.integers(min_value=0, max_value=1000000).map(lambda x: json_string_literal(str(x))),
        st.just(json_string_literal("💰💰")),
    ))

    # --- name field ---
    # nullable string, missing accepted by all, but we always include it (per problem statement)
    # Try null or string
    name_val = draw(st.one_of(
        st.just("null"),
        st.text(min_size=0, max_size=15).map(json_string_literal)
    ))

    # --- status field ---
    # required, one of "active", "inactive", "unknown"
    # Try correct values or unrecognized string (should be rejected by all)
    # To maximize divergence, mostly valid but sometimes invalid
    status_val = draw(st.one_of(
        st.sampled_from(STATUS_VALUES),
        st.text(min_size=1, max_size=10).filter(lambda s: s not in ['active', 'inactive', 'unknown']).map(json_string_literal)
    ))

    # --- tags field ---
    # array of strings, required but built_value accepts missing and uses empty list silently
    # So sometimes omit tags to trigger divergence
    omit_tags = draw(st.booleans())
    if omit_tags:
        tags_json = None
    else:
        # tags array: empty or small list of strings
        tags_list = draw(st.lists(st.text(min_size=1, max_size=10).map(json_string_literal), max_size=3))
        tags_json = "[" + ",".join(tags_list) + "]"

    # --- child field ---
    # nullable Record or null
    # To keep recursion bounded, only one level deep
    # child can be null or a well-formed record with no child (child=null)
    child_null = draw(st.booleans())
    if child_null:
        child_json = "null"
    else:
        # child record with no further child (child=null)
        # Use simpler values for child to reduce complexity
        child_id = draw(st.integers(min_value=0, max_value=100))
        child_amount = json_string_literal(draw(st.text(min_size=1, max_size=5)))
        child_name = draw(st.one_of(st.just("null"), st.text(min_size=0, max_size=5).map(json_string_literal)))
        child_status = draw(st.sampled_from(STATUS_VALUES))
        child_tags_list = draw(st.lists(st.text(min_size=1, max_size=5).map(json_string_literal), max_size=2))
        child_tags_json = "[" + ",".join(child_tags_list) + "]"
        child_json = (
            "{" +
            f'"id":{child_id},' +
            f'"amount":{child_amount},' +
            f'"name":{child_name},' +
            f'"status":{child_status},' +
            f'"tags":{child_tags_json},' +
            f'"child":null' +
            "}"
        )

    # Compose top-level JSON object fields
    # Include all required fields except sometimes omit tags to trigger divergence
    fields = [
        f'"id":{id_json}',
        f'"amount":{amount_str}',
        f'"name":{name_val}',
        f'"status":{status_val}',
    ]
    if tags_json is not None:
        fields.append(f'"tags":{tags_json}')
    # else omit tags field entirely

    fields.append(f'"child":{child_json}')

    json_text = "{" + ",".join(fields) + "}"

    return json_text.encode("utf-8")