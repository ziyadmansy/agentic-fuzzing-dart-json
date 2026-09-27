from hypothesis import strategies as st

# Helper: JSON string escaping for a limited safe subset (no control chars, no quotes inside)
# We'll generate simple ASCII strings without quotes or backslashes to avoid escaping complexity.
json_string_safe = st.text(
    alphabet=st.characters(
        whitelist_categories=('Ll', 'Lu', 'Nd', 'Zs'),
        blacklist_characters=['"', '\\', '\b', '\f', '\n', '\r', '\t']
    ),
    min_size=0,
    max_size=10,
)

# JSON string with explicit quotes added
def json_string(s: str) -> str:
    # s guaranteed to have no quotes or backslashes, so safe to just quote
    return '"' + s + '"'

# JSON array of strings, serialized
def json_array_of_strings(lst):
    # lst is list of strings (already escaped)
    return '[' + ','.join(json_string(s) for s in lst) + ']'

# JSON null literal
json_null = "null"

# JSON enum for status
status_values = ["active", "inactive", "unknown"]

# Compose a JSON record string from fields (all fields present)
def json_record_str(id_str, amount_str, name_str, status_str, tags_str, child_str):
    # Compose fields in fixed order with keys quoted
    # name_str and child_str are either JSON string or null literal
    # tags_str is JSON array string
    # id_str and amount_str are JSON literals (number or string)
    return (
        '{'
        + '"id":' + id_str + ','
        + '"amount":' + amount_str + ','
        + '"name":' + name_str + ','
        + '"status":' + status_str + ','
        + '"tags":' + tags_str + ','
        + '"child":' + child_str
        + '}'
    )

# Strategy for a valid status string literal (quoted)
status_json = st.sampled_from(status_values).map(json_string)

# Strategy for amount field: always a JSON string literal (non-null)
amount_json = json_string_safe.map(json_string)

# Strategy for name field: nullable string (string or null)
name_json = st.one_of(json_string_safe.map(json_string), st.just(json_null))

# Strategy for tags field: array of strings (possibly empty)
tags_json = st.lists(json_string_safe, max_size=5).map(json_array_of_strings)

# Strategy for child field: nullable record or null literal (recursive)
# We'll limit recursion depth to 1 (child can have no child)
def record_json_strategy(depth=0):
    # id field: to maximize divergence, produce either int or double for id
    # manual and built_value require int (Dart int), json_serializable and freezed accept double and convert to int
    # jsonDecode converts large int literals out of 64-bit range to double
    # So produce id as either int literal or double literal (with .0)
    # Also produce some out-of-range int as double to trigger saturation in json_serializable/freezed
    # Dart int64 range: -2^63 to 2^63-1 approx -9.22e18 to 9.22e18
    # We'll produce:
    # - normal int in 32-bit range
    # - large int as double (e.g. 1e20)
    # - negative large int as double (-1e20)
    id_int_normal = st.integers(min_value=0, max_value=2**31 - 1).map(str)
    id_double_large_pos = st.just("1e20")  # JSON number literal as double
    id_double_large_neg = st.just("-1e20")
    id_json = st.one_of(id_int_normal, id_double_large_pos, id_double_large_neg)

    # amount: always string
    amount = amount_json

    # name: nullable string
    name = name_json

    # status: one of enum strings
    status = status_json

    # tags: array of strings, but also try missing tags field (to trigger built_value acceptance)
    # But missing tags is rejected by manual, json_serializable, freezed
    # To maximize disagreement, produce either present tags or missing tags
    # But top-level missing keys are not allowed by the problem statement (all six fields always present)
    # So we cannot omit tags field here, must always present
    # Instead, produce empty array or non-empty array
    tags = tags_json

    # child: nullable record or null
    if depth == 0:
        # child can be null or a record with depth=1 (no further recursion)
        child = st.one_of(
            st.just(json_null),
            record_json_strategy(depth=1)
        )
    else:
        # depth=1: child must be null (no further recursion)
        child = st.just(json_null)

    # Compose record string
    return st.tuples(id_json, amount, name, status, tags, child).map(
        lambda t: json_record_str(*t)
    )

# Top-level composite strategy
@st.composite
def generated_json(draw) -> bytes:
    # Draw a record string with depth=0
    s = draw(record_json_strategy(depth=0))
    # Return bytes (UTF-8 encoded)
    return s.encode("utf-8")