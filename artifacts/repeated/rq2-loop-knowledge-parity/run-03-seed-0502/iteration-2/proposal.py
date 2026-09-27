from hypothesis import strategies as st

# Constants for fixed enums and limits
STATUS_VALUES = ['active', 'inactive', 'unknown']

# Helper to produce JSON string literals with proper escaping for Hypothesis strings
# We'll keep it simple: Hypothesis strings are unicode, we must escape backslash and double quotes.
def json_string_literal(s: str) -> str:
    # Escape backslash and double quote for JSON string literal
    s = s.replace('\\', '\\\\').replace('"', '\\"')
    # Also escape control characters minimally (e.g. newline, tab)
    s = s.replace('\b', '\\b').replace('\f', '\\f').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
    return f'"{s}"'

# Strategy to produce JSON string literals from Hypothesis strings
json_string = st.text(min_size=0, max_size=20).map(json_string_literal)

# Strategy to produce JSON number literals as strings (to embed in JSON text)
# We want to produce integers and doubles that test boundaries for id field decoding.
# id is an integer field, but json_serializable and freezed accept doubles and convert to int.
# We want to produce:
# - integers within 64-bit range (as JSON number literals)
# - integers outside 64-bit range (which jsonDecode turns into double)
# - doubles (including edge cases like 0.0, -0.0, 1.5, large doubles)
# We'll produce numbers as strings to embed in JSON text.

# 64-bit signed int range
INT64_MIN = -2**63
INT64_MAX = 2**63 - 1

# Generate numbers as strings for "id" field:
# - integers in range
# - integers out of range (to become double)
# - doubles with fractional parts
def id_number_strings():
    # Integers in 64-bit range
    in_range_int = st.integers(min_value=INT64_MIN, max_value=INT64_MAX).map(str)
    # Integers out of 64-bit range (large magnitude)
    out_of_range_int = st.one_of(
        st.integers(min_value=INT64_MAX + 1, max_value=INT64_MAX + 10**6),
        st.integers(min_value=INT64_MIN - 10**6, max_value=INT64_MIN - 1)
    ).map(str)
    # Doubles (including fractional and scientific notation)
    # We'll produce floats and convert to JSON number strings without quotes
    # Hypothesis floats can produce inf/nan, but JSON doesn't allow those, so filter them out.
    doubles = st.floats(allow_infinity=False, allow_nan=False, width=32).map(
        lambda f: format(f, '.6g')  # compact decimal or scientific notation
    )
    # Also include some special doubles as strings explicitly
    special_doubles = st.sampled_from(['0.0', '-0.0', '1.5', '-1.5', '1e10', '-1e10', '1.234567e-5'])
    return st.one_of(in_range_int, out_of_range_int, doubles, special_doubles)

# Strategy for "amount" field: string, always present
# Use strings that look like numbers, or arbitrary strings, to test deserializers
amount_string = st.one_of(
    st.text(min_size=1, max_size=10).map(json_string_literal),
    # Also numeric strings that look like numbers but are strings
    st.integers(min_value=0, max_value=1000000).map(lambda i: f'"{i}"'),
    st.floats(allow_infinity=False, allow_nan=False).map(lambda f: json_string_literal(str(f)))
)

# Strategy for "name": nullable string (string or null)
# null is literal null (no quotes)
name_strategy = st.one_of(
    st.none().map(lambda _: 'null'),
    st.text(min_size=0, max_size=20).map(json_string_literal)
)

# Strategy for "status": enum string, always present, but we want to test unrecognized strings too
# Known values: "active", "inactive", "unknown"
# We produce mostly known values, but sometimes an unknown string to test rejection
status_known = st.sampled_from(STATUS_VALUES).map(json_string_literal)
status_unknown = st.text(min_size=1, max_size=10).filter(lambda s: s not in STATUS_VALUES).map(json_string_literal)
status_strategy = st.one_of(
    status_known,
    status_unknown
)

# Strategy for "tags": array of strings, always present normally, but we want to test missing too
# Each string in tags can be arbitrary string literals
tags_array = st.lists(st.text(min_size=0, max_size=10).map(json_string_literal), min_size=0, max_size=5)

# We want to test missing tags field (only built_value accepts missing tags)
# So we produce either a tags field with array or omit it entirely
tags_field_strategy = st.one_of(
    tags_array.map(lambda arr: f'"tags":[{",".join(arr)}]'),
    st.just(None)  # means omit tags field
)

# Strategy for "child": nullable Record or null
# To avoid infinite recursion, limit recursion depth to 1 (one level of child)
# We'll implement a helper function with depth parameter

def record_fields(depth: int):
    # id field as number literal (no quotes)
    id_field = id_number_strings().map(lambda s: f'"id":{s}')
    # amount field as string literal
    amount_field = amount_string.map(lambda s: f'"amount":{s}')
    # name field nullable string or null
    name_field = name_strategy.map(lambda s: f'"name":{s}')
    # status field string (known or unknown)
    status_field = status_strategy.map(lambda s: f'"status":{s}')
    # tags field: either present or missing
    # We'll produce tags field or omit it (None)
    # We'll handle omission at the record level
    # So here just produce tags array string (without quotes)
    tags_arr = tags_array.map(lambda arr: f'"tags":[{",".join(arr)}]')
    # child field: null or nested record (only if depth==0)
    if depth == 0:
        # child can be null or a nested record with depth=1 (no further recursion)
        child_null = st.just('null')
        child_record = record(depth=1).map(lambda s: s)
        child_field = st.one_of(child_null, child_record).map(lambda s: f'"child":{s}')
    else:
        # depth==1 means no further recursion, child must be null
        child_field = st.just('"child":null')

    # Compose fields except tags (tags handled separately for omission)
    fields_no_tags = st.tuples(id_field, amount_field, name_field, status_field, child_field)

    # We want to produce either:
    # - all fields including tags
    # - all fields except tags (omit tags field)
    # So produce a tuple (fields_no_tags, tags_field or None)
    return st.tuples(fields_no_tags, tags_field_strategy)

@st.composite
def record(draw, depth=0):
    (fields_no_tags, tags_field_or_none) = draw(record_fields(depth))
    # fields_no_tags is tuple of 5 strings
    # tags_field_or_none is string or None
    fields_list = list(fields_no_tags)
    if tags_field_or_none is not None:
        fields_list.append(tags_field_or_none)
    # Shuffle fields to avoid fixed order (to test unknown key acceptance)
    # But Hypothesis doesn't have shuffle for lists of strings, so we implement a simple shuffle
    # We'll do a random permutation by drawing a permutation index list
    indices = list(range(len(fields_list)))
    indices = draw(st.permutations(indices))
    fields_shuffled = [fields_list[i] for i in indices]
    # Join fields with commas
    json_obj = '{' + ','.join(fields_shuffled) + '}'
    return json_obj

@st.composite
def generated_json(draw) -> bytes:
    # Produce a top-level record with depth=0
    obj_text = draw(record(depth=0))
    # Return bytes (UTF-8)
    return obj_text.encode('utf-8')