from hypothesis import strategies as st

# Helper to produce JSON string literals with proper escaping of quotes and backslashes
def json_string_literal(s: str) -> str:
    # Escape backslash and double quotes for JSON string
    s = s.replace('\\', '\\\\').replace('"', '\\"')
    # Also escape control chars (optional but safer)
    # Replace control chars with \u00XX escapes
    def esc_char(c):
        if ord(c) < 0x20:
            return '\\u%04x' % ord(c)
        return c
    s = ''.join(esc_char(c) for c in s)
    return '"' + s + '"'

# Strategy for id field: integer near boundaries and some normal values
id_strategy = st.one_of(
    st.integers(min_value=-(2**53), max_value=2**53),  # safe JS integer range
    st.sampled_from([-(2**63), -(2**31), 2**31-1, 2**63-1]),  # 64-bit boundaries
    st.integers(min_value=-1000, max_value=1000),
)

# Strategy for amount: string, sometimes numeric-looking, sometimes weird
amount_strategy = st.one_of(
    st.text(min_size=1, max_size=10).filter(lambda s: all(c not in '"\\' for c in s)),  # simple safe strings
    st.sampled_from(["0", "0.0", "-0", "12345678901234567890", "1e10", "NaN", "Infinity", "-Infinity"]),
)

# Strategy for name: string or null, with some empty and unicode
name_strategy = st.one_of(
    st.none(),
    st.text(min_size=0, max_size=20).filter(lambda s: all(c not in '"\\' for c in s)),
)

# Strategy for status: valid enum or invalid string (bad_enum)
status_strategy = st.one_of(
    st.sampled_from(["active", "inactive", "unknown"]),
    st.text(min_size=1, max_size=10).filter(lambda s: s not in {"active", "inactive", "unknown"}),
)

# Strategy for tags: array of strings, sometimes empty, sometimes with weird strings
tags_strategy = st.lists(
    st.text(min_size=0, max_size=10).filter(lambda s: all(c not in '"\\' for c in s)),
    min_size=0,
    max_size=5,
)

# Recursive strategy for child: either null or a nested record (one level deep normally)
# We allow one level of recursion normally, but sometimes deeper (to test deep_nesting)
@st.composite
def child_strategy(draw, depth=0):
    # Limit recursion depth to 3 normally, but sometimes go deeper to test deep_nesting
    if depth >= 3:
        # At max depth, only null child
        return "null"
    else:
        # 50% chance null, 50% chance nested record
        is_null = draw(st.booleans())
        if is_null:
            return "null"
        else:
            # Compose nested record JSON text
            nested = draw(record_strategy(depth=depth + 1))
            return nested

# Compose a record JSON text string from fields
@st.composite
def record_strategy(draw, depth=0):
    # id field: sometimes boundary values
    id_val = draw(id_strategy)
    # amount field: string, sometimes numeric-looking
    amount_val = draw(amount_strategy)
    # name field: string or null
    name_val = draw(name_strategy)
    # status field: valid or invalid enum string
    status_val = draw(status_strategy)
    # tags field: array of strings
    tags_val = draw(tags_strategy)
    # child field: null or nested record JSON text
    child_val = draw(child_strategy(depth=depth))

    # Compose JSON text for each field
    id_json = str(id_val)
    amount_json = json_string_literal(amount_val)
    if name_val is None:
        name_json = "null"
    else:
        name_json = json_string_literal(name_val)
    status_json = json_string_literal(status_val)
    # tags array JSON
    tags_json = "[" + ",".join(json_string_literal(t) for t in tags_val) + "]"
    child_json = child_val  # already JSON text or "null"

    # Compose full JSON object text
    json_text = (
        '{'
        + '"id":' + id_json + ','
        + '"amount":' + amount_json + ','
        + '"name":' + name_json + ','
        + '"status":' + status_json + ','
        + '"tags":' + tags_json + ','
        + '"child":' + child_json
        + '}'
    )
    return json_text

@st.composite
def generated_json(draw) -> bytes:
    # Generate a record JSON text string
    json_text = draw(record_strategy())
    # Return as UTF-8 bytes
    return json_text.encode("utf-8")