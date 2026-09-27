from hypothesis import strategies as st

# Helper strategies for individual fields
id_field = st.integers(min_value=-2**31, max_value=2**31-1)

# amount: valid is string, but try numbers, null, bool, empty string, long string, etc.
amount_field = st.one_of(
    st.text(min_size=0, max_size=32),  # valid
    st.integers(),                     # wrong type
    st.floats(allow_nan=False, allow_infinity=False),  # wrong type
    st.none(),                         # wrong type
    st.booleans(),                     # wrong type
)

# name: valid is string or null, but try numbers, bool, missing, empty string, etc.
name_field = st.one_of(
    st.text(min_size=0, max_size=32),  # valid
    st.none(),                         # valid
    st.integers(),                     # wrong type
    st.booleans(),                     # wrong type
    st.just(""),                       # edge: empty string
)

# status: valid is "active", "inactive", "unknown"
status_field = st.one_of(
    st.sampled_from(["active", "inactive", "unknown"]),  # valid
    st.text(min_size=0, max_size=12).filter(lambda s: s not in {"active", "inactive", "unknown"}),  # wrong string
    st.integers(),                     # wrong type
    st.none(),                         # wrong type
    st.booleans(),                     # wrong type
)

# tags: valid is array of strings, but try arrays of wrong types, empty array, null, etc.
tags_field = st.one_of(
    st.lists(st.text(min_size=0, max_size=16), min_size=0, max_size=5),  # valid
    st.lists(st.integers(), min_size=0, max_size=5),                     # wrong type in array
    st.lists(st.none(), min_size=0, max_size=5),                         # wrong type in array
    st.lists(st.booleans(), min_size=0, max_size=5),                     # wrong type in array
    st.none(),                                                           # wrong type
)

# child: valid is null or another record (one level of recursion)
def child_field(rec_strategy):
    return st.one_of(
        st.none(),        # valid
        rec_strategy,     # valid
        st.text(min_size=0, max_size=32),  # wrong type
        st.lists(st.text(), min_size=0, max_size=2),  # wrong type
        st.integers(),    # wrong type
        st.booleans(),    # wrong type
    )

# Helper to encode a value as JSON
def json_encode(val):
    if val is None:
        return "null"
    elif isinstance(val, bool):
        return "true" if val else "false"
    elif isinstance(val, int):
        return str(val)
    elif isinstance(val, float):
        # Avoid NaN/inf
        return repr(val)
    elif isinstance(val, str):
        # Escape backslashes and quotes minimally
        return '"' + val.replace('\\', '\\\\').replace('"', '\\"') + '"'
    elif isinstance(val, list):
        return "[" + ",".join(json_encode(x) for x in val) + "]"
    elif isinstance(val, dict):
        return "{" + ",".join(f"{json_encode(k)}:{json_encode(v)}" for k, v in val.items()) + "}"
    else:
        # Should not happen
        raise RuntimeError("Unexpected type: %r" % (val,))

# The main strategy
@st.composite
def generated_json(draw):
    # Recursive record strategy, one level of recursion for child
    def record_strategy(rec_level):
        # For the child field, only allow recursion if rec_level < 1
        child_strat = child_field(st.deferred(lambda: record_strategy(rec_level + 1))) if rec_level < 1 else st.none()
        # Sometimes omit a field (simulate missing field)
        def maybe(field, strat):
            # 80% present, 20% missing
            return st.one_of(
                strat.map(lambda v: ("present", v)),
                st.just(("missing", None))
            )
        # Compose fields, sometimes missing
        return st.tuples(
            maybe("id", id_field),
            maybe("amount", amount_field),
            maybe("name", name_field),
            maybe("status", status_field),
            maybe("tags", tags_field),
            maybe("child", child_strat),
        ).map(lambda fields: [
            (fname, val) for (fname, (present, val)) in zip(
                ["id", "amount", "name", "status", "tags", "child"], fields
            ) if present == "present"
        ])
    # Draw a record (top-level)
    fields = draw(record_strategy(0))
    # Shuffle field order to test order sensitivity
    draw(st.permutations(fields))
    # Compose JSON object
    json_obj = "{" + ",".join(
        json_encode(k) + ":" + json_encode(v) for k, v in fields
    ) + "}"
    # Return as bytes
    return json_obj.encode("utf-8")