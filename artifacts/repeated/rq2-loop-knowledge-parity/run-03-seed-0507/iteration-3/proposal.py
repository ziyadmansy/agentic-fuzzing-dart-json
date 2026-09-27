from hypothesis import strategies as st

# Helper: JSON string with proper escaping for " and \ only (simplified)
# We avoid control chars for simplicity.
json_escaped_char = st.characters(
    blacklist_characters='"\\',
    min_codepoint=0x20,
    max_codepoint=0x7E,
)
json_string = st.text(json_escaped_char, min_size=0, max_size=20).map(
    lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'
)

# JSON array of strings: ["tag1","tag2",...]
json_string_array = st.lists(json_string, min_size=0, max_size=5).map(
    lambda lst: '[' + ','.join(lst) + ']'
)

# JSON null or a nested record (one level recursion)
# We'll define a recursive strategy with max depth 1 for "child"
# To avoid infinite recursion, child can be null or a record with child=null only.

@st.composite
def json_record(draw, allow_missing_tags=False, allow_tags_wrong_type=False, allow_id_double=False):
    # id: integer or (for json_serializable/freezed) double that .toInt() saturates
    # We produce either an int literal or a double literal (with .0)
    # int range: 64-bit signed: -2**63..2**63-1
    # We'll produce ints mostly in range, but sometimes out-of-range as double
    id_int = draw(st.integers(min_value=-2**63, max_value=2**63 - 1))
    id_double_out_of_range = draw(st.booleans())
    if allow_id_double and id_double_out_of_range:
        # produce a double outside int64 range, e.g. 1e20 or -1e20
        id_val = draw(st.sampled_from([
            "1e20", "-1e20", "9e18", "-9e18", "1.5e19", "-1.5e19"
        ]))
    else:
        id_val = str(id_int)

    # amount: string (non-null)
    amount_val = draw(json_string)

    # name: string or null
    name_val = draw(st.one_of(json_string, st.just("null")))

    # status: one of "active", "inactive", "unknown"
    status_val = draw(st.sampled_from(['"active"', '"inactive"', '"unknown"']))

    # tags: array of strings, or missing (only built_value accepts missing)
    # or wrong type (e.g. null, number, string) to test rejection
    tags_missing = False
    tags_wrong_type = False
    if allow_missing_tags:
        tags_missing = draw(st.booleans())
    if allow_tags_wrong_type:
        tags_wrong_type = draw(st.booleans())

    if tags_missing:
        tags_field = None
    elif tags_wrong_type:
        # wrong type for tags: null, number, string, object
        wrong_tags_val = draw(st.one_of(
            st.just("null"),
            st.integers(min_value=0, max_value=100).map(str),
            json_string,
            st.just("{}")
        ))
        tags_field = wrong_tags_val
    else:
        tags_field = draw(json_string_array)

    # child: null or a nested record with child=null only (one level recursion)
    child_null = draw(st.booleans())
    if child_null:
        child_field = "null"
    else:
        # nested record with child=null, no missing tags here to keep complexity low
        nested_id = draw(st.integers(min_value=-2**63, max_value=2**63 - 1))
        nested_amount = draw(json_string)
        nested_name = draw(st.one_of(json_string, st.just("null")))
        nested_status = draw(st.sampled_from(['"active"', '"inactive"', '"unknown"']))
        nested_tags = draw(json_string_array)
        child_field = (
            '{'
            f'"id":{nested_id},'
            f'"amount":{nested_amount},'
            f'"name":{nested_name},'
            f'"status":{nested_status},'
            f'"tags":{nested_tags},'
            f'"child":null'
            '}'
        )

    # Compose fields, optionally omitting tags if allowed
    fields = [
        f'"id":{id_val}',
        f'"amount":{amount_val}',
        f'"name":{name_val}',
        f'"status":{status_val}',
        f'"child":{child_field}',
    ]
    if tags_field is not None:
        fields.insert(4, f'"tags":{tags_field}')  # insert tags before child

    json_obj = '{' + ','.join(fields) + '}'
    return json_obj


@st.composite
def generated_json(draw) -> bytes:
    # We want to maximize disagreements:
    # - sometimes omit tags (built_value accepts, others reject)
    # - sometimes tags wrong type (all reject)
    # - sometimes id as double out-of-range (manual and built_value reject, others accept)
    # - always produce syntactically valid JSON object with all six fields present or tags missing
    # - child is either null or a well-formed record with child=null (no deeper recursion)
    # - name nullable, status always valid string

    # Control booleans to produce edge cases
    allow_missing_tags = draw(st.booleans())
    allow_tags_wrong_type = draw(st.booleans())
    allow_id_double = draw(st.booleans())

    # To keep "almost well-formed" documents, do not combine all bad things at once:
    # If tags missing, do not do tags wrong type.
    if allow_missing_tags and allow_tags_wrong_type:
        allow_tags_wrong_type = False

    json_text = draw(json_record(
        allow_missing_tags=allow_missing_tags,
        allow_tags_wrong_type=allow_tags_wrong_type,
        allow_id_double=allow_id_double,
    ))

    return json_text.encode("utf-8")