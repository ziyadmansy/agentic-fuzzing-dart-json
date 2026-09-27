from hypothesis import strategies as st

# Helper strategies for fields with subtle edge cases
id_strategy = st.one_of(
    st.integers(min_value=-2**31, max_value=2**31-1),  # normal int
    st.integers(min_value=2**31, max_value=2**53),     # large int (may overflow)
    st.floats(allow_nan=False, allow_infinity=False).map(lambda f: int(f)),  # float->int
    st.just(0),  # boundary
)

amount_strategy = st.one_of(
    st.text(min_size=0, max_size=20),  # normal string
    st.just(""),                       # empty string
    st.text(alphabet="0123456789.", min_size=1, max_size=20),  # numeric-looking string
    st.text(alphabet=" \t\n\r", min_size=1, max_size=5),       # whitespace
    st.just("null"),                   # string "null"
    st.just("NaN"),                    # string "NaN"
)

name_strategy = st.one_of(
    st.text(min_size=0, max_size=20),  # normal string
    st.just(""),                       # empty string
    st.none(),                         # null
    st.text(alphabet=" \t\n\r", min_size=1, max_size=5),  # whitespace
    st.just("null"),                   # string "null"
)

status_strategy = st.one_of(
    st.sampled_from(["active", "inactive", "unknown"]),  # valid
    st.text(min_size=0, max_size=10).filter(lambda s: s not in {"active", "inactive", "unknown"}),  # invalid
    st.just(""),  # empty string
    st.just("null"),  # string "null"
)

tags_strategy = st.one_of(
    st.lists(st.text(min_size=0, max_size=10), min_size=0, max_size=5),  # normal
    st.lists(st.text(alphabet=" \t\n\r", min_size=1, max_size=3), min_size=1, max_size=3),  # whitespace
    st.just([]),  # empty list
    st.lists(st.just("null"), min_size=1, max_size=3),  # list of "null" strings
    st.lists(st.none(), min_size=1, max_size=3),  # list of nulls (invalid for schema)
    st.just([None]),  # single null
)

# Recursive child strategy
@st.composite
def record_strategy(draw, allow_child=True):
    # To maximize divergence, sometimes omit or mis-type a field
    field_choices = [
        "id", "amount", "name", "status", "tags", "child"
    ]
    # Sometimes drop a field (simulate missing field)
    maybe_drop = draw(st.booleans())
    if maybe_drop:
        drop_field = draw(st.sampled_from(field_choices))
    else:
        drop_field = None

    fields = []

    if drop_field != "id":
        id_val = draw(id_strategy)
        # Sometimes encode as string instead of int
        if draw(st.booleans()):
            id_json = f'"id":{id_val}'
        else:
            id_json = f'"id":"{id_val}"'
        fields.append(id_json)

    if drop_field != "amount":
        amount_val = draw(amount_strategy)
        # Sometimes encode as non-string
        if draw(st.booleans()):
            amount_json = f'"amount":"{amount_val}"'
        else:
            amount_json = f'"amount":null'
        fields.append(amount_json)

    if drop_field != "name":
        name_val = draw(name_strategy)
        if name_val is None:
            name_json = '"name":null'
        else:
            # Sometimes encode as non-string
            if draw(st.integers(min_value=0, max_value=3)) == 0:
                name_json = f'"name":{draw(st.integers(min_value=0, max_value=100))}'
            else:
                name_json = f'"name":"{name_val}"'
        fields.append(name_json)

    if drop_field != "status":
        status_val = draw(status_strategy)
        # Sometimes encode as null
        if status_val == "null":
            status_json = '"status":null'
        else:
            status_json = f'"status":"{status_val}"'
        fields.append(status_json)

    if drop_field != "tags":
        tags_val = draw(tags_strategy)
        # Sometimes encode as null instead of array
        if tags_val == [None] or (isinstance(tags_val, list) and all(x is None for x in tags_val)):
            tags_json = '"tags":null'
        elif isinstance(tags_val, list):
            tag_strs = []
            for t in tags_val:
                if t is None:
                    tag_strs.append('null')
                else:
                    tag_strs.append(f'"{t}"')
            tags_json = f'"tags":[{",".join(tag_strs)}]'
        else:
            tags_json = '"tags":[]'
        fields.append(tags_json)

    if drop_field != "child":
        # Sometimes encode as null, sometimes as nested record, sometimes as wrong type
        child_type = draw(st.integers(min_value=0, max_value=3))
        if not allow_child or child_type == 0:
            child_json = '"child":null'
        elif child_type == 1:
            # Wrong type: string
            child_json = '"child":"not_a_record"'
        elif child_type == 2:
            # Wrong type: int
            child_json = '"child":123'
        else:
            # Nested record, but only one level deep
            nested = draw(record_strategy(allow_child=False))
            child_json = f'"child":{nested.decode("utf-8")}'
        fields.append(child_json)

    # Shuffle field order to catch order-dependent bugs
    draw(st.permutations(fields))
    json_obj = '{' + ','.join(fields) + '}'
    return json_obj.encode('utf-8')

@st.composite
def generated_json(draw) -> bytes:
    return draw(record_strategy())