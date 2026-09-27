from hypothesis import strategies as st

# Helper: JSON string escaping for Hypothesis-generated strings.
# We must produce valid JSON strings with proper escaping.
# We'll keep it simple: allow only characters safe in JSON strings without escaping,
# plus escape backslash and double quote.
# Control chars and others are omitted to keep output simple and valid.
def json_string(s: str) -> str:
    # Escape backslash and double quote
    s = s.replace('\\', '\\\\').replace('"', '\\"')
    # Replace control chars with unicode escapes (optional, but safer)
    # We'll just omit control chars by filtering them out in generation.
    return '"' + s + '"'

# Strategy for JSON string content safe for JSON string literal without complex escaping.
json_str_chars = st.characters(
    whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs', 'Po', 'Pc'),
    blacklist_characters=['\\', '"', '\b', '\f', '\n', '\r', '\t']
)
json_str = st.text(json_str_chars, min_size=0, max_size=20).map(json_string)

# Strategy for "status" field: one of "active", "inactive", "unknown"
status_values = st.sampled_from(['"active"', '"inactive"', '"unknown"'])

# Strategy for "tags" array: array of strings
tags_array = st.lists(json_str, min_size=0, max_size=3).map(
    lambda lst: '[' + ','.join(lst) + ']'
)

# Strategy for nullable string field "name": either null or a JSON string
name_field = st.one_of(st.just('null'), json_str)

# Strategy for "amount": string (non-nullable)
amount_field = json_str

# Strategy for "id": integer or double (to exploit known difference in decoding)
# We produce either:
# - a JSON integer literal within 64-bit signed int range (safe for all)
# - a JSON number literal with decimal point (double) representing an integer value,
#   to trigger json_serializable/freezed accepting double but manual/built_value rejecting
# - a JSON number literal outside 64-bit int range, encoded as double (e.g. 1e20)
#   to trigger saturation behavior in json_serializable/freezed
#
# We'll produce a union of these cases.
int64_min = -(2**63)
int64_max = 2**63 - 1

# JSON integer literal as string
def json_int_literal(n: int) -> str:
    return str(n)

# JSON double literal as string (with decimal point)
def json_double_literal(n: int) -> str:
    # Represent integer as double with .0 suffix
    return f"{n}.0"

# JSON double literal outside int64 range
def json_double_out_of_range() -> str:
    # Use a large number outside int64 range, e.g. 1e20 or -1e20
    # JSON allows exponent notation
    return st.sampled_from(['1e20', '-1e20'])

# Compose id field strategy
id_field = st.one_of(
    st.integers(min_value=int64_min, max_value=int64_max).map(json_int_literal),
    st.integers(min_value=int64_min, max_value=int64_max).map(json_double_literal),
    json_double_out_of_range()
)

# Strategy for "child" field: either null or a nested record (one level recursion)
# To avoid infinite recursion, limit depth to 1 (child.child is always null)
# We'll define a helper function for record generation with depth parameter.

def record_fields(depth: int) -> st.SearchStrategy[str]:
    # Compose fields except child first
    # id, amount, name, status, tags
    # We'll produce a dict of field strings and join them later.
    # To maximize disagreement, sometimes omit 'tags' field (to trigger built_value behavior)
    # but only at top level (depth==0), because child is always present or null.
    # We'll produce two variants at top level: with tags present or missing.
    # At child level, tags always present.

    # id field
    id_s = id_field.map(lambda v: f'"id":{v}')
    # amount field
    amount_s = amount_field.map(lambda v: f'"amount":{v}')
    # name field (nullable string)
    name_s = name_field.map(lambda v: f'"name":{v}')
    # status field
    status_s = status_values.map(lambda v: f'"status":{v}')
    # tags field (array of strings)
    tags_s = tags_array.map(lambda v: f'"tags":{v}')

    # child field: null or nested record (depth+1)
    if depth >= 1:
        # child.child is always null at max depth
        child_s = st.just('"child":null')
    else:
        # child is null or nested record at depth+1
        child_record_s = record_fields(depth + 1)
        child_s = st.one_of(
            st.just('"child":null'),
            child_record_s.map(lambda v: f'"child":{v}')
        )

    # Compose fields into a list, then join with commas
    # At top level (depth==0), sometimes omit 'tags' to trigger divergence
    if depth == 0:
        # tags present or missing
        # If missing, built_value accepts with empty list, others reject
        # So produce both variants to find divergence
        def with_or_without_tags(tags_present: bool):
            fields = [id_s, amount_s, name_s, status_s, child_s]
            if tags_present:
                fields.append(tags_s)
            # Combine all fields with commas
            return st.tuples(*fields).map(lambda fs: '{' + ','.join(fs) + '}')

        return st.booleans().flatmap(with_or_without_tags)
    else:
        # child level: tags always present
        fields = [id_s, amount_s, name_s, status_s, tags_s, child_s]
        return st.tuples(*fields).map(lambda fs: '{' + ','.join(fs) + '}')

@st.composite
def generated_json(draw) -> bytes:
    # Generate top-level record JSON text
    json_text = draw(record_fields(depth=0))
    # Return as bytes (UTF-8)
    return json_text.encode('utf-8')