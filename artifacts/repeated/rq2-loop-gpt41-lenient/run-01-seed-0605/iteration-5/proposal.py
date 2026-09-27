from hypothesis import strategies as st

# Helper strategies for fields
id_strategy = st.integers(min_value=-2**31, max_value=2**31-1)

# "amount" is a string, but try edge cases: numbers as strings, empty, weird unicode, etc.
amount_strategy = st.one_of(
    st.text(min_size=0, max_size=32),  # arbitrary string
    st.integers().map(str),            # integer as string
    st.floats(allow_nan=False, allow_infinity=False).map(lambda x: f"{x}"),  # float as string
)

# "name" is string or null, but try edge cases: empty, weird unicode, numbers as string, etc.
name_strategy = st.one_of(
    st.none(),
    st.text(min_size=0, max_size=32),
    st.integers().map(str),
    st.just("null"),  # string "null"
)

# "status" is one of three strings, but try case sensitivity and near-misses
status_strategy = st.one_of(
    st.sampled_from(["active", "inactive", "unknown"]),
    st.sampled_from(["Active", "INACTIVE", "Unknown", "ACTIVE", "inactive "]),  # case/space variants
    st.text(min_size=0, max_size=10).filter(lambda s: s not in {"active", "inactive", "unknown"}),  # wrong value
)

# "tags" is an array of strings, but try empty, single, long, and edge-case strings
tag_string_strategy = st.one_of(
    st.text(min_size=0, max_size=16),
    st.integers().map(str),
    st.just("null"),
)
tags_strategy = st.lists(tag_string_strategy, min_size=0, max_size=5)

# "child" is a Record or null. We'll allow one level of recursion.
def record_strategy(rec_depth):
    # At depth 0, child is always null
    if rec_depth == 0:
        child_strategy = st.just("null")
    else:
        # 70% null, 30% nested record
        child_strategy = st.one_of(
            st.just("null"),
            record_strategy(rec_depth - 1)
        )

    # Compose the record as a JSON object string
    @st.composite
    def record(draw):
        id_val = draw(id_strategy)
        amount_val = draw(amount_strategy)
        name_val = draw(name_strategy)
        status_val = draw(status_strategy)
        tags_val = draw(tags_strategy)
        child_val = draw(child_strategy)

        # Build JSON fields (always present, but with possible type/format edge cases)
        # Use repr() for strings to get proper escaping, but strip the quotes for keys
        def json_str(s):
            # Use repr, but ensure double quotes for JSON
            return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

        tags_json = "[" + ", ".join(json_str(str(tag)) for tag in tags_val) + "]"

        # Compose the record
        fields = [
            f'"id": {id_val}',
            f'"amount": {json_str(str(amount_val))}',
            f'"name": { "null" if name_val is None else json_str(str(name_val)) }',
            f'"status": {json_str(str(status_val))}',
            f'"tags": {tags_json}',
            f'"child": {child_val}',
        ]
        return "{" + ", ".join(fields) + "}"

    return record().map(lambda s: s)

# Top-level strategy: one level of recursion for "child"
@st.composite
def generated_json(draw):
    # Only one level of recursion for "child"
    json_str = draw(record_strategy(rec_depth=1))
    # Output as bytes
    return json_str.encode("utf-8")