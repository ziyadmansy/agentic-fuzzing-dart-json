from hypothesis import strategies as st

# Helper strategies for individual fields
id_strategy = st.integers(min_value=-2**31, max_value=2**31-1)

amount_strategy = st.text(
    min_size=0, max_size=32,
    alphabet=st.characters(blacklist_categories=["Cs", "Cc", "Zl", "Zp", "Cn"])
).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

name_strategy = (
    st.none() |
    st.text(
        min_size=0, max_size=32,
        alphabet=st.characters(blacklist_categories=["Cs", "Cc", "Zl", "Zp", "Cn"])
    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')
)

status_strategy = st.sampled_from(['"active"', '"inactive"', '"unknown"'])

tags_strategy = st.lists(
    st.text(
        min_size=0, max_size=16,
        alphabet=st.characters(blacklist_categories=["Cs", "Cc", "Zl", "Zp", "Cn"])
    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'),
    min_size=0, max_size=4
).map(lambda tags: '[' + ','.join(tags) + ']')

# Divergence triggers: each field can be "off" in a subtle way
def field_variants(field_name, valid, off_types):
    # off_types: list of (description, strategy)
    # returns st.one_of(valid, *off_types)
    return st.one_of(
        valid,
        *[off for desc, off in off_types]
    )

# For each field, define a valid and a few "almost valid" variants
id_field = field_variants(
    "id",
    id_strategy.map(str),
    [
        ("as string", id_strategy.map(lambda i: '"' + str(i) + '"')),
        ("as float", st.floats(allow_nan=False, allow_infinity=False).map(str)),
        ("as bool", st.booleans().map(lambda b: "true" if b else "false")),
        ("as null", st.just("null")),
    ]
)

amount_field = field_variants(
    "amount",
    amount_strategy,
    [
        ("as number", id_strategy.map(str)),
        ("as bool", st.booleans().map(lambda b: "true" if b else "false")),
        ("as null", st.just("null")),
        ("as array", st.lists(st.integers(), min_size=0, max_size=2).map(lambda l: str(l).replace("'", ""))),
    ]
)

name_field = field_variants(
    "name",
    name_strategy,
    [
        ("as number", id_strategy.map(str)),
        ("as bool", st.booleans().map(lambda b: "true" if b else "false")),
        ("as array", st.lists(st.text(min_size=0, max_size=4), min_size=0, max_size=2).map(lambda l: '[' + ','.join('"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"' for s in l) + ']')),
    ]
)

status_field = field_variants(
    "status",
    status_strategy,
    [
        ("as number", id_strategy.map(str)),
        ("as bool", st.booleans().map(lambda b: "true" if b else "false")),
        ("as null", st.just("null")),
        ("as string but invalid", st.sampled_from(['"pending"', '"deleted"', '""'])),
    ]
)

tags_field = field_variants(
    "tags",
    tags_strategy,
    [
        ("as string", amount_strategy),
        ("as null", st.just("null")),
        ("as object", st.just('{"foo": "bar"}')),
        ("as array of numbers", st.lists(id_strategy, min_size=0, max_size=2).map(lambda l: '[' + ','.join(map(str, l)) + ']')),
    ]
)

# For child, allow null, valid record, or "off" variants
@st.composite
def child_field(draw, depth):
    if depth <= 0:
        return "null"
    valid_child = generated_json(draw, depth=depth-1).decode("utf-8")
    off_variants = [
        "42",  # number
        '"not an object"',  # string
        "true",  # bool
        "[]",  # array
    ]
    return draw(st.one_of(
        st.just("null"),
        st.just(valid_child),
        st.sampled_from(off_variants)
    ))

# Compose the full record
@st.composite
def generated_json(draw, depth=1):
    # Choose one or two fields to be "off", rest valid
    fields = ["id", "amount", "name", "status", "tags", "child"]
    off_fields = draw(st.lists(st.sampled_from(fields), min_size=0, max_size=2, max_size=2, unique=True))
    def pick(field, valid, off):
        return off if field in off_fields else valid

    id_val = draw(pick("id", id_strategy.map(str), id_field))
    amount_val = draw(pick("amount", amount_strategy, amount_field))
    name_val = draw(pick("name", name_strategy, name_field))
    status_val = draw(pick("status", status_strategy, status_field))
    tags_val = draw(pick("tags", tags_strategy, tags_field))
    child_val = draw(child_field(depth=depth)) if "child" not in off_fields else draw(st.one_of(
        st.just("null"),
        st.just("42"),
        st.just('"not an object"'),
        st.just("true"),
        st.just("[]"),
    ))

    # Compose JSON object
    json_obj = (
        '{'
        f'"id":{id_val},'
        f'"amount":{amount_val},'
        f'"name":{name_val},'
        f'"status":{status_val},'
        f'"tags":{tags_val},'
        f'"child":{child_val}'
        '}'
    )
    return json_obj.encode("utf-8")