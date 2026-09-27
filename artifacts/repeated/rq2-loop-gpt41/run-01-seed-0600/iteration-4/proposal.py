from hypothesis import strategies as st

# Helper strategies for each field
id_strategy = st.integers(min_value=-2**31, max_value=2**31-1)

# amount is a string, but we can try edge cases: numbers as strings, empty, weird unicode, etc.
amount_strategy = st.one_of(
    st.text(min_size=0, max_size=32),  # arbitrary string
    st.integers().map(str),            # integer as string
    st.floats(allow_nan=False, allow_infinity=False).map(lambda x: f"{x}"),  # float as string
)

# name: string or null, but try edge cases: empty string, long, unicode, etc.
name_strategy = st.one_of(
    st.none(),
    st.text(min_size=0, max_size=32),
)

# status: valid values, but also try wrong-case, wrong-type, or off-by-one
status_strategy = st.one_of(
    st.sampled_from(["active", "inactive", "unknown"]),
    st.sampled_from(["Active", "INACTIVE", "Unknown"]),  # wrong-case
    st.integers(min_value=0, max_value=2).map(str),      # as stringified int
    st.integers(min_value=0, max_value=2),               # as int (wrong type)
    st.just(""),                                         # empty string
)

# tags: array of strings, but try edge cases: empty, nulls, wrong types, etc.
tags_strategy = st.one_of(
    st.lists(st.text(min_size=0, max_size=16), max_size=4),
    st.lists(st.none(), min_size=1, max_size=2),         # nulls in array
    st.lists(st.integers(), min_size=1, max_size=2),     # ints in array
    st.just([]),                                         # empty array
    st.just([None]),                                     # array with only null
)

# For child, allow null or a recursive record, but limit recursion depth
@st.composite
def record_strategy(draw, depth=0):
    # At depth >= 1, only allow null or a non-recursive record
    allow_child = depth < 1
    child_value = (
        draw(record_strategy(depth=1))
        if allow_child and draw(st.booleans())
        else None
    )
    # Vary one or two fields at a time for divergence
    # Pick one or two fields to "perturb" in this record
    fields = ["id", "amount", "name", "status", "tags", "child"]
    perturb_fields = draw(st.lists(st.sampled_from(fields), min_size=0, max_size=2, unique=True))
    # Default values
    id_val = draw(id_strategy)
    amount_val = draw(amount_strategy)
    name_val = draw(name_strategy)
    status_val = draw(status_strategy)
    tags_val = draw(tags_strategy)
    child_val = child_value
    # Apply perturbations: for each, pick a "wrong" value
    for field in perturb_fields:
        if field == "id":
            # id: wrong type (string or float)
            id_val = draw(st.one_of(
                st.text(min_size=0, max_size=8),
                st.floats(allow_nan=False, allow_infinity=False)
            ))
        elif field == "amount":
            # amount: wrong type (int, null, array)
            amount_val = draw(st.one_of(
                st.integers(),
                st.none(),
                st.lists(st.text(), min_size=1, max_size=2)
            ))
        elif field == "name":
            # name: wrong type (int, array)
            name_val = draw(st.one_of(
                st.integers(),
                st.lists(st.text(), min_size=1, max_size=2)
            ))
        elif field == "status":
            # status: wrong type (null, int, array)
            status_val = draw(st.one_of(
                st.none(),
                st.integers(),
                st.lists(st.text(), min_size=1, max_size=2)
            ))
        elif field == "tags":
            # tags: wrong type (string, null, int)
            tags_val = draw(st.one_of(
                st.text(min_size=0, max_size=8),
                st.none(),
                st.integers()
            ))
        elif field == "child":
            # child: wrong type (string, int, array)
            child_val = draw(st.one_of(
                st.text(min_size=0, max_size=8),
                st.integers(),
                st.lists(st.text(), min_size=1, max_size=2)
            ))
    # Build JSON string for this record
    def json_escape(s):
        return s.replace('\\', '\\\\').replace('"', '\\"').replace('\b', '\\b').replace('\f', '\\f').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
    def to_json(val):
        if val is None:
            return "null"
        elif isinstance(val, str):
            return '"' + json_escape(val) + '"'
        elif isinstance(val, bool):
            return "true" if val else "false"
        elif isinstance(val, (int, float)):
            return str(val)
        elif isinstance(val, list):
            return "[" + ",".join(to_json(x) for x in val) + "]"
        elif isinstance(val, dict):
            return "{" + ",".join(f'"{k}":{to_json(v)}' for k, v in val.items()) + "}"
        else:
            # fallback: string repr
            return '"' + json_escape(str(val)) + '"'
    # Compose the record as a JSON object
    json_obj = (
        '{'
        f'"id":{to_json(id_val)},'
        f'"amount":{to_json(amount_val)},'
        f'"name":{to_json(name_val)},'
        f'"status":{to_json(status_val)},'
        f'"tags":{to_json(tags_val)},'
        f'"child":{to_json(child_val)}'
        '}'
    )
    return json_obj

@st.composite
def generated_json(draw):
    # Generate a single record, as bytes
    json_str = draw(record_strategy())
    return json_str.encode("utf-8")