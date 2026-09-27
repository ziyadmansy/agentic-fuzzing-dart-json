from hypothesis import strategies as st

# Helper: JSON string escaping for Hypothesis-generated strings.
# We only allow a restricted subset of characters to avoid complex escaping.
# We'll generate strings with no control chars or quotes/backslashes.
json_safe_chars = st.characters(
    whitelist_categories=('Ll', 'Lu', 'Nd', 'Zs'),
    blacklist_characters='"\\',
    min_codepoint=0x20,
    max_codepoint=0x7E,
)

json_string = json_safe_chars.filter(lambda s: s not in ('', 'null', 'true', 'false')).map(
    lambda s: '"' + s + '"'
)

# JSON string or null (nullable string)
json_string_or_null = st.one_of(json_string, st.just("null"))

# JSON array of strings (tags) - always present, but can be empty
json_tags = st.lists(json_string, max_size=4).map(
    lambda lst: "[" + ",".join(lst) + "]"
)

# JSON enum status: "active", "inactive", "unknown"
json_status = st.sampled_from(['"active"', '"inactive"', '"unknown"'])

# JSON integer or double for id field:
# To exploit the difference in id decoding:
# - manual and built_value require int (no decimal point)
# - json_serializable and freezed accept double (with decimal point) and convert to int
# We'll generate either an integer literal or a double literal that looks like an int but is a float.
# Also generate out-of-range integers as doubles to saturate.
def json_id_strategy():
    # 64-bit signed int range
    INT64_MIN = -2**63
    INT64_MAX = 2**63 - 1

    # Generate int in range or out-of-range as double
    in_range_int = st.integers(min_value=INT64_MIN, max_value=INT64_MAX)
    out_of_range_int = st.one_of(
        st.integers(min_value=INT64_MIN - 10**10, max_value=INT64_MIN - 1),
        st.integers(min_value=INT64_MAX + 1, max_value=INT64_MAX + 10**10),
    )

    # Format int as JSON number (no quotes)
    def fmt_int(i: int) -> str:
        return str(i)

    # Format out-of-range int as double literal (with .0)
    def fmt_double(i: int) -> str:
        # Use float literal with .0 to force double
        return f"{float(i):.1f}"

    # Compose strategy:
    # 50% in-range int as int literal
    # 25% out-of-range int as double literal
    # 25% in-range int as double literal (to test saturation)
    return st.one_of(
        in_range_int.map(fmt_int),
        out_of_range_int.map(fmt_double),
        in_range_int.map(fmt_double),
    )

# JSON amount: string, non-null, non-empty, no quotes/backslash/control chars
json_amount = json_string

# JSON name: nullable string (string or null)
json_name = json_string_or_null

# Recursive child record or null, max depth 1 (one level of recursion)
# To avoid complexity, child is either null or a record with no child (child=null)
# We generate a record with child=null or null directly.
# We'll generate a record with all fields present.

@st.composite
def json_record(draw, allow_child=True):
    # id
    id_val = draw(json_id_strategy())
    # amount
    amount_val = draw(json_amount)
    # name
    name_val = draw(json_name)
    # status
    status_val = draw(json_status)
    # tags (always present)
    tags_val = draw(json_tags)
    # child: either null or a record with child=null (only if allow_child)
    if allow_child:
        child_null = st.just("null")
        # child record with child=null to limit recursion depth
        child_record = json_record(allow_child=False)
        child_val = draw(st.one_of(child_null, child_record))
    else:
        child_val = "null"

    # Compose JSON object text with all fields present, no extra whitespace
    # Order fields as in schema: id, amount, name, status, tags, child
    obj = (
        '{'
        f'"id":{id_val},'
        f'"amount":{amount_val},'
        f'"name":{name_val},'
        f'"status":{status_val},'
        f'"tags":{tags_val},'
        f'"child":{child_val}'
        '}'
    )
    return obj

# Main composite strategy: generate JSON bytes of a record object
@st.composite
def generated_json(draw) -> bytes:
    # Generate a record with one-level recursion
    json_text = draw(json_record())
    return json_text.encode("utf-8")