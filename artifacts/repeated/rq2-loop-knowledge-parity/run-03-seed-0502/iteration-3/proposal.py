from hypothesis import strategies as st

# We will produce JSON objects as strings, carefully controlling fields.
# The record schema:
# {
#   "id": <integer>,
#   "amount": <string>,
#   "name": <string or null>,
#   "status": <"active"|"inactive"|"unknown">,
#   "tags": <array of strings>,
#   "child": <Record or null>
# }
#
# Constraints and known divergences:
# - id: manual and built_value require true int; json_serializable and freezed accept double and convert to int.
#   jsonDecode turns large int literals outside int64 range into double.
#   toInt() saturates instead of throwing.
# - tags missing: built_value accepts with empty list; others reject.
# - missing nullable fields (name, child) accepted by all.
# - wrong type or null for non-nullable rejected by all (private _TypeError or public DeserializationError).
# - unrecognized status string rejected by all.
# - extra unknown keys accepted by all.
#
# Strategy:
# - Generate mostly well-formed objects.
# - Vary presence/absence of tags to trigger built_value acceptance divergence.
# - Vary id as int, large int (causing double), or double to trigger id decoding divergence.
# - Vary name and child as null or string/object.
# - Vary status among valid values only (to avoid universal rejection).
# - Occasionally omit tags to trigger built_value acceptance divergence.
# - Occasionally put tags as wrong type to cause universal rejection (not scored).
# - Keep recursion depth bounded (max 1 level child).
#
# We produce JSON text manually, using string concatenation and escaping strings.
# We do not import json, so we must escape strings ourselves.
#
# We produce bytes output (UTF-8 encoded JSON text).
#
# We produce syntactically valid JSON objects only.

# Helper: escape JSON string (minimal, only backslash and quote)
def json_escape(s: str) -> str:
    # Escape backslash and double quote, and control chars as \uXXXX
    res = []
    for c in s:
        o = ord(c)
        if c == '"':
            res.append('\\"')
        elif c == '\\':
            res.append('\\\\')
        elif 0 <= o <= 0x1F:
            res.append('\\u%04x' % o)
        else:
            res.append(c)
    return ''.join(res)

# Strategy for JSON string, limited chars to avoid complex escaping
json_string_chars = st.characters(
    blacklist_characters='"\\',
    min_codepoint=0x20,
    max_codepoint=0x7E,
)
json_string = st.text(json_string_chars, min_size=0, max_size=12)

# Strategy for JSON string or null
json_string_or_null = st.one_of(
    st.just("null"),
    json_string.map(lambda s: '"' + json_escape(s) + '"')
)

# Strategy for status field (only valid values)
status_values = st.sampled_from(['"active"', '"inactive"', '"unknown"'])

# Strategy for tags array (array of strings)
tags_array = st.lists(json_string, min_size=0, max_size=5).map(
    lambda lst: '[' + ','.join('"' + json_escape(s) + '"' for s in lst) + ']'
)

# Strategy for id field:
# - normal int in 32-bit range (manual and built_value accept)
# - large int outside 64-bit range (encoded as number literal, but jsonDecode makes it double)
# - double with fractional part (accepted by json_serializable and freezed but rejected by manual and built_value)
#
# We produce JSON number literals as strings.
#
# JSON numbers: no quotes.
#
# Large int outside int64 range:
# int64 max = 9223372036854775807
# int64 min = -9223372036854775808
# We'll pick values outside this range to force jsonDecode to produce double.
#
# double with fractional part: e.g. 123.456
#
# We'll produce a tagged union of these three cases.

id_normal_int = st.integers(min_value=-2**31, max_value=2**31-1).map(str)
id_large_int = st.one_of(
    st.integers(min_value=2**63, max_value=2**63+10),
    st.integers(min_value=-(2**63+10), max_value=-(2**63))
).map(str)
id_double = st.floats(min_value=-1e9, max_value=1e9, allow_nan=False, allow_infinity=False).filter(lambda f: abs(f) > 1e-3 and f != int(f)).map(lambda f: ('%.6f' % f).rstrip('0').rstrip('.'))

id_field = st.one_of(id_normal_int, id_large_int, id_double)

# amount field: string, non-nullable
amount_field = json_string.map(lambda s: '"' + json_escape(s) + '"')

# name field: string or null (nullable)
name_field = json_string_or_null

# status field: one of three strings
status_field = status_values

# child field: null or a record (one level recursion)
# To avoid infinite recursion, child record is generated with depth=0 (no further child)
# We'll define a helper function for record generation with depth param

def record_strategy(depth: int):
    # depth 0 means child=null only
    if depth <= 0:
        child_field = st.just("null")
    else:
        child_field = record_strategy(depth - 1).map(lambda s: s)

    # tags field: either present or missing (to trigger built_value divergence)
    # We'll produce two variants:
    # - tags present: array of strings
    # - tags missing: omit the field entirely (to trigger built_value acceptance divergence)
    # We produce a tuple (tags_present: bool, tags_value: str or None)
    tags_present = st.booleans()
    tags_value = tags_array

    # Compose the record fields:
    # id, amount, name, status, tags (optional), child

    def build_record(args):
        idv, amountv, namev, statusv, tags_presentv, tagsv, childv = args
        fields = []
        # id
        fields.append('"id":' + idv)
        # amount
        fields.append('"amount":' + amountv)
        # name
        fields.append('"name":' + namev)
        # status
        fields.append('"status":' + statusv)
        # tags (optional)
        if tags_presentv:
            fields.append('"tags":' + tagsv)
        # child
        fields.append('"child":' + childv)
        return '{' + ','.join(fields) + '}'

    return st.tuples(
        id_field,
        amount_field,
        name_field,
        status_field,
        tags_present,
        tags_value,
        child_field
    ).map(build_record)

@st.composite
def generated_json(draw) -> bytes:
    # Generate a record with depth=1 (one level child)
    s = draw(record_strategy(1))
    return s.encode('utf-8')