from hypothesis import strategies as st

# Helper strategies for field values
id_strategy = st.integers(min_value=-2**31, max_value=2**31-1)

# "amount" is a string, but try edge cases: numbers as strings, empty, weird unicode, etc.
amount_strategy = st.one_of(
    st.text(min_size=0, max_size=32),  # arbitrary string
    st.integers().map(str),            # integer as string
    st.floats(allow_nan=False, allow_infinity=False).map(str),  # float as string
    st.just(""),                       # empty string
    st.just("0"),                      # zero as string
    st.just("null"),                   # the literal "null"
    st.just("NaN"),                    # "NaN" as string
)

# "name" is string or null, but try some edge cases
name_strategy = st.one_of(
    st.text(min_size=0, max_size=32),
    st.just(None),
    st.just("null"),  # string "null"
    st.just(""),      # empty string
)

status_strategy = st.sampled_from(["active", "inactive", "unknown"])

# "tags" is array of strings, but try edge cases: empty, nulls, numbers as strings, etc.
tag_string_strategy = st.one_of(
    st.text(min_size=0, max_size=16),
    st.integers().map(str),
    st.just("null"),
    st.just(""),
)
tags_strategy = st.one_of(
    st.lists(tag_string_strategy, min_size=0, max_size=4),
    st.just([]),  # explicitly empty
)

# For recursion, we want to sometimes omit or null the child, sometimes include a child
@st.composite
def record_strategy(draw, allow_recursion=True):
    # To maximize divergence, sometimes omit or null fields, sometimes wrong types
    # But always emit syntactically valid JSON
    # For each field, with small probability, use a "wrong" type
    def maybe_wrong(field_st, wrong_st, p=0.1):
        return st.one_of(field_st, wrong_st) if draw(st.booleans()) and draw(st.randoms()).random() < p else field_st

    id_val = draw(maybe_wrong(id_strategy, st.text(min_size=1, max_size=8), p=0.08))
    amount_val = draw(maybe_wrong(amount_strategy, st.integers(), p=0.08))
    name_val = draw(maybe_wrong(name_strategy, st.integers(), p=0.06))
    status_val = draw(maybe_wrong(status_strategy, st.integers().map(str), p=0.05))
    tags_val = draw(maybe_wrong(tags_strategy, st.lists(st.integers(), min_size=1, max_size=3), p=0.07))

    # For child: sometimes null, sometimes a record, sometimes wrong type
    child_val = None
    if allow_recursion and draw(st.booleans()):
        # 60%: valid child, 30%: null, 10%: wrong type
        which = draw(st.integers(min_value=0, max_value=9))
        if which < 6:
            child_val = draw(record_strategy(allow_recursion=False))
        elif which < 9:
            child_val = None
        else:
            child_val = draw(st.integers())
    else:
        child_val = None

    # Build JSON string for this record
    def json_escape(s):
        # Minimal escape for double quotes and backslash
        return s.replace('\\', '\\\\').replace('"', '\\"')

    def to_json(val):
        if val is None:
            return "null"
        elif isinstance(val, str):
            return '"' + json_escape(val) + '"'
        elif isinstance(val, bool):
            return "true" if val else "false"
        elif isinstance(val, int) or isinstance(val, float):
            return str(val)
        elif isinstance(val, list):
            return "[" + ",".join(to_json(x) for x in val) + "]"
        elif isinstance(val, dict):
            return "{" + ",".join(f'"{k}":{to_json(v)}' for k, v in val.items()) + "}"
        else:
            # fallback: string representation
            return '"' + json_escape(str(val)) + '"'

    # Compose the record as a JSON object
    fields = [
        f'"id":{to_json(id_val)}',
        f'"amount":{to_json(amount_val)}',
        f'"name":{to_json(name_val)}',
        f'"status":{to_json(status_val)}',
        f'"tags":{to_json(tags_val)}',
        f'"child":{to_json(child_val)}',
    ]
    json_obj = "{" + ",".join(fields) + "}"
    return json_obj

@st.composite
def generated_json(draw):
    # Draw a record and encode as bytes
    json_str = draw(record_strategy())
    return json_str.encode("utf-8")