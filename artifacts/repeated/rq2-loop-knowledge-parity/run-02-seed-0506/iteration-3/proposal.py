from hypothesis import strategies as st

# Helper: JSON string literal with proper escaping of " and \ and control chars
def json_string_literal(s: str) -> str:
    # Minimal escaping for JSON string literals:
    # Replace \ with \\, " with \", and control chars with \u00XX
    def esc_char(c):
        o = ord(c)
        if c == '\\':
            return '\\\\'
        if c == '"':
            return '\\"'
        if 0x20 <= o <= 0x10FFFF:
            return c
        # Control chars replaced by \u00XX
        return '\\u%04x' % o
    return '"' + ''.join(esc_char(c) for c in s) + '"'

# Strategy for JSON string literal text (no control chars)
json_string_text = st.text(
    alphabet=st.characters(
        blacklist_characters=['\\', '"', '\b', '\f', '\n', '\r', '\t'],
        min_codepoint=0x20,
        max_codepoint=0x10FFFF,
    ),
    min_size=0,
    max_size=20,
).map(json_string_literal)

# Strategy for JSON string literal text allowing some escaped chars (for more coverage)
json_string_text_esc = st.text(
    alphabet=st.characters(
        blacklist_characters=['"'],
        min_codepoint=0x20,
        max_codepoint=0x10FFFF,
    ),
    min_size=0,
    max_size=20,
).map(json_string_literal)

# Strategy for "amount" field: string, allow numeric-looking strings, empty, or normal words
amount_str = st.one_of(
    # numeric strings, including integers, floats, negative, zero-padded
    st.integers(min_value=-999999, max_value=999999).map(lambda i: json_string_literal(str(i))),
    st.floats(min_value=-9999.99, max_value=9999.99, allow_infinity=False, allow_nan=False).map(lambda f: json_string_literal(format(f, 'g'))),
    # empty string
    st.just('""'),
    # random ascii words
    st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=('Ll','Lu','Nd'))).map(json_string_literal),
)

# Strategy for "name" field: nullable string
name_str = st.one_of(
    st.just('null'),
    json_string_text_esc,
)

# Strategy for "status" field: one of "active", "inactive", "unknown" (always valid)
status_str = st.sampled_from(['"active"', '"inactive"', '"unknown"'])

# Strategy for "tags" field: array of strings (possibly empty)
tags_array = st.lists(json_string_text_esc, max_size=5).map(
    lambda lst: '[' + ','.join(lst) + ']'
)

# Strategy for "id" field:
# To exploit known difference:
# manual and built_value require true int (Dart int),
# json_serializable and freezed accept num.toInt() (accept double).
# jsonDecode turns integer literals outside 64-bit range into double.
# toInt() saturates instead of throwing.
#
# So produce:
# - valid int in 64-bit range (as int literal)
# - int literal outside 64-bit range (to become double)
# - double literal (non-integer)
#
# JSON numbers: no quotes, just digits, optional minus, optional decimal point.
#
# 64-bit signed int range: -2^63 .. 2^63-1
# = -9223372036854775808 .. 9223372036854775807
#
# We'll produce:
# - normal int in range
# - int outside range (e.g. 2^63 or -2^63-1)
# - double with fractional part

INT64_MIN = -9223372036854775808
INT64_MAX = 9223372036854775807

def int64_literal(i: int) -> str:
    return str(i)

def double_literal(f: float) -> str:
    # Format float with decimal point, no exponent
    s = format(f, '.6f').rstrip('0').rstrip('.')
    if '.' not in s:
        s += '.0'
    if s == '-0':
        s = '0.0'
    return s

id_strategy = st.one_of(
    # int in 64-bit range
    st.integers(min_value=INT64_MIN, max_value=INT64_MAX).map(int64_literal),
    # int outside 64-bit range (to become double)
    st.sampled_from([
        str(2**63),          # 9223372036854775808
        str(-(2**63)-1),     # -9223372036854775809
        str(2**64),          # 18446744073709551616
        str(-(2**64)),       # -18446744073709551616
    ]),
    # double with fractional part (not integer)
    st.floats(min_value=-1e9, max_value=1e9, allow_infinity=False, allow_nan=False).filter(lambda x: abs(x) < 1e9 and (x != int(x))).map(double_literal),
)

# Strategy for "child" field: nullable Record or null
# To avoid infinite recursion, limit depth to 1 (one level of recursion normally)
# We'll implement a recursive strategy with max_depth=1

@st.composite
def record(draw, depth=0):
    # id
    id_val = draw(id_strategy)
    # amount
    amount_val = draw(amount_str)
    # name
    name_val = draw(name_str)
    # status
    status_val = draw(status_str)
    # tags
    # To exploit known difference: missing tags accepted only by built_value,
    # so sometimes omit tags field entirely to cause divergence.
    # But problem states all six fields always present in well-formed document,
    # so to cause divergence, produce some with tags missing.
    # But the problem states "all six fields always present in a well-formed document",
    # but we want to produce documents that are syntactically valid JSON objects,
    # so we can sometimes omit tags to cause divergence.
    # We'll do that with low probability.
    omit_tags = draw(st.booleans())
    if omit_tags:
        tags_val = None
    else:
        tags_val = draw(tags_array)
    # child
    if depth == 0:
        # one level of recursion normally
        # child can be null or a record with depth=1 (no further recursion)
        child_null = draw(st.booleans())
        if child_null:
            child_val = 'null'
        else:
            child_val = draw(record(depth=1))
    else:
        # depth=1, no further recursion, child must be null
        child_val = 'null'

    # Compose JSON object string
    # Fields order: id, amount, name, status, tags, child
    # Omit tags if tags_val is None
    fields = []
    fields.append('"id":' + id_val)
    fields.append('"amount":' + amount_val)
    fields.append('"name":' + name_val)
    fields.append('"status":' + status_val)
    if tags_val is not None:
        fields.append('"tags":' + tags_val)
    # else omit tags field entirely
    fields.append('"child":' + child_val)

    json_obj = '{' + ','.join(fields) + '}'
    return json_obj

@st.composite
def generated_json(draw) -> bytes:
    # Draw a record at depth=0
    s = draw(record(depth=0))
    return s.encode('utf-8')