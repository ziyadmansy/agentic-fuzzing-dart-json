from hypothesis import strategies as st

# Helper: JSON string escaping for Hypothesis-generated strings
def json_string(s: str) -> str:
    # Minimal escaping for JSON string: backslash, quote, control chars
    # Hypothesis strings are unicode, so escape control chars and backslash, quote
    # We'll do a simple replace chain
    s = s.replace('\\', '\\\\')
    s = s.replace('"', '\\"')
    s = s.replace('\b', '\\b')
    s = s.replace('\f', '\\f')
    s = s.replace('\n', '\\n')
    s = s.replace('\r', '\\r')
    s = s.replace('\t', '\\t')
    # Other control chars (U+0000..U+001F) replaced with \u00XX
    def escape_ctrl(c):
        if ord(c) < 0x20:
            return '\\u%04x' % ord(c)
        return c
    s = ''.join(escape_ctrl(c) for c in s)
    return '"' + s + '"'

# Strategy for JSON string text, with some control chars to test escapes
json_str_strategy = st.text(
    alphabet=st.characters(
        blacklist_categories=('Cs',),  # no surrogates
        min_codepoint=0x20,
        max_codepoint=0x10FFFF,
    ),
    min_size=0,
    max_size=20,
).map(json_string)

# Strategy for nullable JSON string or null
json_nullable_string = st.one_of(json_str_strategy, st.just("null"))

# Strategy for "status" field: one of three strings
status_values = st.sampled_from(['"active"', '"inactive"', '"unknown"'])

# Strategy for tags: array of strings (possibly empty)
tags_array = st.lists(json_str_strategy, min_size=0, max_size=5).map(
    lambda lst: '[' + ','.join(lst) + ']'
)

# Strategy for id field:
# To exploit known divergence:
# manual and built_value require true int (JSON integer literal decoded as int)
# json_serializable and freezed accept (num).toInt(), so accept doubles too
# jsonDecode turns integer literals outside 64-bit range into double
# toInt() saturates to int64 min/max instead of throwing
#
# So we produce either:
# - a JSON integer literal within 64-bit range (decoded as int)
# - a JSON number literal with fractional part 0 but outside 64-bit range (decoded as double)
#
# 64-bit signed int range: -2**63 .. 2**63-1
# We'll produce:
# - int in [-2**63, 2**63-1] as JSON integer literal
# - or a double outside that range but with .0 fractional part
#
# Also test small doubles with .0 fractional part inside range to see if manual rejects them.
int64_min = -(2**63)
int64_max = 2**63 - 1

# JSON number literal for int or double with .0 fractional part
def json_number_literal(n: int, force_double: bool) -> str:
    if force_double:
        # Represent as float with .0 fractional part
        return str(float(n)) + '0' if '.' not in str(float(n)) else str(float(n))
    else:
        return str(n)

# Strategy for id field producing int or double with .0 fractional part
id_strategy = st.one_of(
    # int in range as integer literal
    st.integers(min_value=int64_min, max_value=int64_max).map(lambda n: str(n)),
    # double outside int64 range with .0 fractional part
    st.one_of(
        st.integers(min_value=int64_max + 1, max_value=int64_max + 10**6),
        st.integers(min_value=int64_min - 10**6, max_value=int64_min - 1),
    ).map(lambda n: str(float(n)) + '.0'),
    # double inside range with .0 fractional part (should be rejected by manual/built_value)
    st.integers(min_value=int64_min, max_value=int64_max).map(lambda n: str(float(n)) + '.0'),
)

# amount field: string, non-nullable
amount_strategy = json_str_strategy

# name field: nullable string or null
name_strategy = json_nullable_string

# child field: nullable record or null
# We'll limit recursion depth to 1 (one level of child)
# To avoid infinite recursion, define a function with depth param

def record_strategy(depth: int) -> st.SearchStrategy[str]:
    # Compose a record JSON object string with all six fields always present
    # We will vary one or two fields to create divergence, mostly one at a time
    # We will sometimes omit tags to trigger built_value acceptance divergence
    # But per problem statement, all six fields always present in well-formed documents
    # So to create divergence, sometimes omit tags field (to test built_value)
    # or produce wrong types for one field at a time
    # or produce out-of-range id as double

    # Field presence control: tags field present or missing
    tags_present = st.booleans()

    # For divergence, sometimes produce wrong type for one field:
    # - id: int or double or string (wrong type)
    # - amount: string or number (wrong type)
    # - name: string or null (nullable, so null allowed)
    # - status: one of three strings or wrong string or number (wrong type)
    # - tags: array of strings or missing or wrong type (string or null)
    # - child: null or record or wrong type (string or number)

    # We'll produce a mostly valid record, then with small probability produce one field wrong type or missing tags

    # Probability of introducing one divergence factor
    divergence_prob = 0.3

    # id field: mostly valid id_strategy, sometimes string (wrong type)
    id_field = st.one_of(
        id_strategy,
        st.just('"wrong_id"')  # wrong type string
    ).flatmap(lambda v: st.just('"id":' + v))

    # amount field: mostly string, sometimes number (wrong type)
    amount_field = st.one_of(
        amount_strategy.map(lambda s: '"amount":' + s),
        st.integers(min_value=0, max_value=1000).map(lambda n: '"amount":' + str(n))
    )

    # name field: nullable string or null
    name_field = name_strategy.map(lambda s: '"name":' + s)

    # status field: mostly valid status string, sometimes invalid string or number
    status_field = st.one_of(
        status_values.map(lambda s: '"status":' + s),
        st.just('"status":"invalid_status"'),
        st.integers(min_value=0, max_value=10).map(lambda n: '"status":' + str(n))
    )

    # tags field: present or missing or wrong type
    # missing tags triggers built_value acceptance divergence
    # wrong type triggers rejection divergence
    tags_field = st.one_of(
        tags_array.map(lambda s: '"tags":' + s),
        st.just('"tags":null'),
        st.just('"tags":"not_an_array"'),
        st.just(None)  # missing tags field
    )

    # child field: null or nested record or wrong type string
    if depth <= 0:
        # no recursion, child null or wrong type string
        child_field = st.one_of(
            st.just('"child":null'),
            json_str_strategy.map(lambda s: '"child":' + s),
        )
    else:
        # recursion allowed: child null or nested record or wrong type string
        child_field = st.one_of(
            st.just('"child":null'),
            record_strategy(depth - 1).map(lambda s: '"child":' + s),
            json_str_strategy.map(lambda s: '"child":' + s),
        )

    # Compose fields with control over tags presence
    def compose_record(fields, tags_val):
        # fields is dict of field_name -> field_json_string (without commas)
        # tags_val is one of:
        # - None: omit tags field
        # - string: tags field JSON string
        # Compose JSON object string with all fields present except tags if None
        parts = []
        for k in ['id', 'amount', 'name', 'status']:
            parts.append(fields[k])
        if tags_val is not None:
            parts.append(tags_val)
        for k in ['child']:
            parts.append(fields[k])
        return '{' + ','.join(parts) + '}'

    # Build a strategy for fields dict
    fields_dict = st.fixed_dictionaries({
        'id': id_field,
        'amount': amount_field,
        'name': name_field,
        'status': status_field,
        'child': child_field,
    })

    # Combine fields and tags_field, then compose record string
    return st.tuples(fields_dict, tags_field).map(
        lambda ft: compose_record(ft[0], ft[1])
    )

@st.composite
def generated_json(draw) -> bytes:
    # Generate a record with depth 1 recursion max
    rec = draw(record_strategy(depth=1))
    # rec is a JSON object string, syntactically valid JSON
    # Return bytes
    return rec.encode('utf-8')