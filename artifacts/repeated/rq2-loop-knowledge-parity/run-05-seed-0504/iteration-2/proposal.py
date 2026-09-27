from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for fields
    STATUS_VALUES = ["active", "inactive", "unknown"]
    
    # Strategy for id field:
    # To exploit the difference in int decoding:
    # - manual and built_value require true int
    # - json_serializable and freezed accept double and convert to int with toInt()
    # jsonDecode converts large integers outside int64 range into double.
    # So we generate either:
    #  - a normal int in 64-bit range (accepted by all)
    #  - a large int outside 64-bit range (encoded as JSON number, but jsonDecode will parse as double)
    #  - a double (float) value that is integral (e.g. 1.0) to test acceptance by json_serializable/freezed but rejection by manual/built_value
    #
    # We generate a union of:
    #  - int64-range int
    #  - int64-range int encoded as float (e.g. 1.0)
    #  - large int outside int64 range (encoded as int literal, but jsonDecode will parse as double)
    #
    # We must produce JSON text, so we produce the number as string representation.
    #
    # We produce the JSON text for the number ourselves, so we can produce e.g. "1.0" or "9223372036854775808"
    
    # 64-bit signed int range
    INT64_MIN = -9223372036854775808
    INT64_MAX = 9223372036854775807
    
    # Large int outside 64-bit range (positive and negative)
    LARGE_INT_POS = 9223372036854775808  # INT64_MAX + 1
    LARGE_INT_NEG = -9223372036854775809 # INT64_MIN - 1
    
    # Strategy for producing id JSON number text
    id_number_text = st.one_of(
        # Normal int in 64-bit range, as integer literal
        st.integers(min_value=INT64_MIN, max_value=INT64_MAX).map(str),
        # Normal int in 64-bit range, encoded as float with .0 suffix (e.g. "42.0")
        st.integers(min_value=INT64_MIN, max_value=INT64_MAX).map(lambda i: f"{i}.0"),
        # Large int outside 64-bit range, as integer literal (will be parsed as double by jsonDecode)
        st.sampled_from([LARGE_INT_POS, LARGE_INT_NEG]).map(str),
    )
    
    # amount: always string, non-null
    amount_str = st.text(min_size=1, max_size=10).map(lambda s: s.replace('"', '\\"'))  # escape quotes if any
    
    # name: nullable string or null
    name_str_or_null = st.one_of(
        st.none(),
        st.text(min_size=0, max_size=10).map(lambda s: s.replace('"', '\\"'))
    )
    
    # status: one of the three known strings, or an unrecognized string to test rejection
    # But unrecognized status rejected by all four, so no divergence there.
    # So only generate valid status values.
    status_str = st.sampled_from(STATUS_VALUES)
    
    # tags: array of strings, always present (empty or non-empty)
    # We want to test missing tags (accepted only by built_value), but missing fields are rejected by all except built_value.
    # So we do not omit tags here, but we can test empty vs non-empty.
    tags_list = st.lists(
        st.text(min_size=1, max_size=5).map(lambda s: s.replace('"', '\\"')),
        max_size=3
    )
    
    # child: nullable record or null
    # To keep recursion bounded, child is either null or a record with child=null (one level recursion)
    # We generate child as either null or a record with child=null (no further recursion)
    # We reuse the same field strategies for child, but child.child is always null to avoid deep recursion.
    
    # Helper to produce a record JSON text given field JSON texts
    def record_json_text(id_text, amount_text, name_json, status_text, tags_json, child_json):
        # Compose JSON object text with fields in fixed order for determinism
        # name_json and child_json are already JSON text (either "null" or quoted string or object)
        return (
            '{'
            f'"id":{id_text},'
            f'"amount":"{amount_text}",'
            f'"name":{name_json},'
            f'"status":"{status_text}",'
            f'"tags":{tags_json},'
            f'"child":{child_json}'
            '}'
        )
    
    # Strategy for JSON string literal (quoted and escaped)
    def json_string_literal(s):
        # s is already escaped for quotes, but we must also escape backslashes and control chars
        # For simplicity, replace backslash with double backslash, and quotes with \"
        # Also replace control chars with \uXXXX
        # Hypothesis text is unicode, so we must escape properly
        def escape_char(c):
            if c == '\\':
                return '\\\\'
            elif c == '"':
                return '\\"'
            elif c == '\b':
                return '\\b'
            elif c == '\f':
                return '\\f'
            elif c == '\n':
                return '\\n'
            elif c == '\r':
                return '\\r'
            elif c == '\t':
                return '\\t'
            elif ord(c) < 0x20:
                return f'\\u{ord(c):04x}'
            else:
                return c
        escaped = ''.join(escape_char(c) for c in s)
        return f'"{escaped}"'
    
    # name_json: either "null" or JSON string literal
    name_json = draw(
        st.one_of(
            st.just("null"),
            st.text(min_size=0, max_size=10).map(json_string_literal)
        )
    )
    
    # tags_json: JSON array of strings
    tags = draw(tags_list)
    tags_json = '[' + ','.join(json_string_literal(t) for t in tags) + ']'
    
    # status_text
    status_text = draw(status_str)
    
    # amount_text
    amount_text = draw(amount_str)
    
    # id_text
    id_text = draw(id_number_text)
    
    # child_json: either "null" or a record with child=null (no further recursion)
    # Compose child record fields similarly, but child=null always
    child_is_null = draw(st.booleans())
    if child_is_null:
        child_json = "null"
    else:
        # child record fields:
        # id
        child_id_text = draw(id_number_text)
        # amount
        child_amount_text = draw(amount_str)
        # name
        child_name_json = draw(
            st.one_of(
                st.just("null"),
                st.text(min_size=0, max_size=10).map(json_string_literal)
            )
        )
        # status
        child_status_text = draw(status_str)
        # tags
        child_tags = draw(tags_list)
        child_tags_json = '[' + ','.join(json_string_literal(t) for t in child_tags) + ']'
        # child.child is always null (no further recursion)
        child_child_json = "null"
        
        child_json = record_json_text(
            child_id_text,
            child_amount_text,
            child_name_json,
            child_status_text,
            child_tags_json,
            child_child_json
        )
    
    # Compose top-level record JSON text
    json_text = record_json_text(
        id_text,
        amount_text,
        name_json,
        status_text,
        tags_json,
        child_json
    )
    
    # Return as bytes
    return json_text.encode("utf-8")