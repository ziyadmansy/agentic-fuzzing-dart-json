from hypothesis import strategies as st

# Helper strategies for field values
id_strategy = st.integers(min_value=-2**31, max_value=2**31-1)

# Amount is a string, but try edge cases: numbers, empty, weird floats, etc.
amount_strategy = st.one_of(
    st.text(min_size=0, max_size=32),  # Normal string
    st.integers().map(str),            # Integer as string
    st.floats(allow_nan=True, allow_infinity=True).map(str),  # Float as string
)

# Name: string or null, but try edge cases: empty, long, special chars, numbers as string
name_strategy = st.one_of(
    st.none(),
    st.text(min_size=0, max_size=32),
    st.integers().map(str),
    st.just("null"),  # String "null"
    st.just(""),      # Empty string
)

# Status: one of three, but try case, misspelling, extra whitespace, etc.
status_strategy = st.one_of(
    st.sampled_from(["active", "inactive", "unknown"]),
    st.sampled_from(["Active", "INACTIVE", "Unknown"]),  # Case variants
    st.just(" active"),  # Leading space
    st.just("inactive "),  # Trailing space
    st.just("unkn0wn"),    # Misspelling
    st.just(""),           # Empty string
)

# Tags: array of strings, but try empty, nulls, numbers as string, nested arrays
tag_string_strategy = st.one_of(
    st.text(min_size=0, max_size=16),
    st.integers().map(str),
    st.just("null"),
    st.just(""),
)
tags_strategy = st.one_of(
    st.lists(tag_string_strategy, min_size=0, max_size=4),
    st.just([]),
    st.lists(st.none(), min_size=1, max_size=2),  # Array of nulls
    st.lists(st.lists(tag_string_strategy, min_size=1, max_size=2), min_size=1, max_size=1),  # Nested array
)

# Child: null or another record (one level of recursion)
@st.composite
def record(draw, allow_child=True):
    id_val = draw(id_strategy)
    amount_val = draw(amount_strategy)
    name_val = draw(name_strategy)
    status_val = draw(status_strategy)
    tags_val = draw(tags_strategy)
    if allow_child:
        child_val = draw(st.one_of(st.none(), record(allow_child=False)))
    else:
        child_val = None

    # Build JSON fields
    def json_str(val):
        # Escape JSON string
        return '"' + val.replace('\\', '\\\\').replace('"', '\\"') + '"'

    # id: always integer
    id_field = f'"id": {id_val}'

    # amount: always string
    amount_field = f'"amount": {json_str(str(amount_val))}'

    # name: string or null
    if name_val is None:
        name_field = '"name": null'
    else:
        name_field = f'"name": {json_str(str(name_val))}'

    # status: string
    status_field = f'"status": {json_str(str(status_val))}'

    # tags: array of strings (or nulls/nested)
    if isinstance(tags_val, list):
        def tag_json(v):
            if v is None:
                return "null"
            elif isinstance(v, list):
                return "[" + ",".join(tag_json(x) for x in v) + "]"
            else:
                return json_str(str(v))
        tags_field = '"tags": [' + ",".join(tag_json(x) for x in tags_val) + "]"
    else:
        tags_field = '"tags": []'

    # child: null or record
    if child_val is None:
        child_field = '"child": null'
    else:
        child_field = f'"child": {child_val}'

    # Compose object
    fields = [id_field, amount_field, name_field, status_field, tags_field, child_field]
    obj = "{" + ",".join(fields) + "}"
    return obj

@st.composite
def generated_json(draw):
    # Compose the record and encode as bytes
    json_str = draw(record())
    # Bound the size to avoid huge outputs
    if len(json_str) > 2048:
        json_str = json_str[:2048]
        # Try to close any open braces for syntactic validity
        if not json_str.endswith("}"):
            json_str += "}"
    return json_str.encode("utf-8")