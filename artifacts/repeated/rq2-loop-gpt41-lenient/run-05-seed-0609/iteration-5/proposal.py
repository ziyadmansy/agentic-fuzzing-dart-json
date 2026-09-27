from hypothesis import strategies as st

# Helper strategies for fields
id_strategy = st.integers(min_value=-2**31, max_value=2**31-1)

# amount: string, but try edge cases (numbers as strings, empty, large, etc.)
amount_strategy = st.one_of(
    st.text(min_size=0, max_size=32),  # arbitrary string
    st.integers().map(str),            # integer as string
    st.floats(allow_nan=False, allow_infinity=False).map(lambda f: repr(f)),  # float as string
)

# name: string or null, but sometimes wrong type (number, bool, empty string, etc.)
name_strategy = st.one_of(
    st.text(min_size=0, max_size=32),
    st.none(),
    st.just(""),                # empty string
    st.integers(),              # wrong type: int
    st.booleans(),              # wrong type: bool
)

# status: correct or off-by-one (wrong case, unknown value, int, null)
status_strategy = st.one_of(
    st.sampled_from(["active", "inactive", "unknown"]),
    st.text(min_size=0, max_size=16).filter(lambda s: s not in {"active", "inactive", "unknown"}),  # invalid string
    st.integers(),      # wrong type
    st.none(),          # null
)

# tags: array of strings, but sometimes wrong type (numbers, nulls, mixed)
tag_elem_strategy = st.one_of(
    st.text(min_size=0, max_size=16),
    st.integers(),      # wrong type
    st.none(),          # null in array
)
tags_strategy = st.one_of(
    st.lists(st.text(min_size=0, max_size=16), min_size=0, max_size=5),
    st.lists(tag_elem_strategy, min_size=0, max_size=5),
    st.none(),  # wrong type: null instead of array
)

# child: Record or null or wrong type (int, string, empty object)
# Bounded recursion: only one level of child nesting
@st.composite
def record(draw, allow_child=True):
    id_val = draw(id_strategy)
    amount_val = draw(amount_strategy)
    name_val = draw(name_strategy)
    status_val = draw(status_strategy)
    tags_val = draw(tags_strategy)
    if allow_child:
        child_val = draw(st.one_of(
            st.none(),
            record(allow_child=False),
            st.integers(),  # wrong type
            st.text(min_size=0, max_size=16),  # wrong type
            st.just({}),    # empty object
        ))
    else:
        child_val = draw(st.one_of(
            st.none(),
            st.integers(),
            st.text(min_size=0, max_size=16),
            st.just({}),
        ))

    # Build JSON string for the record
    def json_escape(s):
        return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

    def json_value(val):
        if isinstance(val, str):
            return json_escape(val)
        elif val is None:
            return "null"
        elif isinstance(val, bool):
            return "true" if val else "false"
        elif isinstance(val, int) or isinstance(val, float):
            return str(val)
        elif isinstance(val, list):
            return "[" + ",".join(json_value(x) for x in val) + "]"
        elif isinstance(val, dict):
            # Should only occur for empty object
            return "{}"
        else:
            # Should not occur
            return "null"

    # Compose the JSON object
    fields = [
        f'"id":{json_value(id_val)}',
        f'"amount":{json_value(amount_val)}',
        f'"name":{json_value(name_val)}',
        f'"status":{json_value(status_val)}',
        f'"tags":{json_value(tags_val)}',
        f'"child":{json_value(child_val)}',
    ]
    return "{" + ",".join(fields) + "}"

@st.composite
def generated_json(draw) -> bytes:
    # Top-level record, always present all six fields
    json_str = draw(record())
    return json_str.encode("utf-8")