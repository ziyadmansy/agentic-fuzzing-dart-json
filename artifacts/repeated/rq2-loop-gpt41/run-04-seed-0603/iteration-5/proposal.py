from hypothesis import strategies as st

# Helper strategies for fields
id_strategy = st.integers(min_value=-2**31, max_value=2**31-1)

# amount: string, but try edge cases (numbers, null, bool, empty string, weird unicode)
amount_strategy = st.one_of(
    st.text(min_size=0, max_size=32),  # normal string
    st.just(""),                       # empty string
    st.text(alphabet="\u0000\uD800\uDC00\uFFFD", min_size=1, max_size=4),  # odd unicode
    st.integers().map(str),            # number as string
    st.just("null"),                   # literal "null"
    st.just("true"),                   # literal "true"
    st.just("false"),                  # literal "false"
)

# name: string or null, but try numbers, bools, empty, etc.
name_strategy = st.one_of(
    st.none(),
    st.text(min_size=0, max_size=32),
    st.just(""),
    st.integers().map(str),
    st.integers(),
    st.floats(allow_nan=False, allow_infinity=False),
    st.just(True),
    st.just(False),
)

# status: valid enum, but try wrong-case, wrong-type, or missing
status_strategy = st.one_of(
    st.sampled_from(["active", "inactive", "unknown"]),
    st.text(min_size=0, max_size=16).filter(lambda s: s not in {"active", "inactive", "unknown"}),
    st.integers(),
    st.just(None),
    st.just("ACTIVE"),  # upper-case
    st.just("Active"),  # capitalized
    st.just(""),        # empty string
)

# tags: array of strings, but try wrong types, empty, nulls, mixed types
tags_strategy = st.one_of(
    st.lists(st.text(min_size=0, max_size=16), min_size=0, max_size=4),
    st.lists(st.integers(), min_size=1, max_size=3),
    st.lists(st.one_of(st.text(min_size=0, max_size=16), st.integers(), st.none()), min_size=1, max_size=4),
    st.just([]),
    st.just(None),
    st.just("notalist"),
)

# Bounded recursion for child
def record_strategy(max_depth):
    @st.composite
    def _record(draw):
        # At max depth, child is always null
        child_val = None if max_depth <= 0 else draw(
            st.one_of(
                st.deferred(lambda: record_strategy(max_depth - 1)()),
                st.just(None),
                # Try wrong types for child
                st.just(123),
                st.just("notarecord"),
                st.just([]),
            )
        )

        # For each field, with some probability, use a "wrong" type or omit
        id_val = draw(id_strategy)
        amount_val = draw(amount_strategy)
        name_val = draw(name_strategy)
        status_val = draw(status_strategy)
        tags_val = draw(tags_strategy)

        # Build JSON string for each field
        def json_val(val):
            if val is None:
                return "null"
            elif isinstance(val, bool):
                return "true" if val else "false"
            elif isinstance(val, (int, float)):
                return str(val)
            elif isinstance(val, str):
                # Escape JSON special chars
                s = val.replace("\\", "\\\\").replace('"', '\\"')
                return f'"{s}"'
            elif isinstance(val, list):
                return "[" + ",".join(json_val(x) for x in val) + "]"
            else:
                # Should not happen, fallback
                return f'"{str(val)}"'

        # Compose fields, possibly omitting one at random (to test missing fields)
        fields = [
            ('"id"', json_val(id_val)),
            ('"amount"', json_val(amount_val)),
            ('"name"', json_val(name_val)),
            ('"status"', json_val(status_val)),
            ('"tags"', json_val(tags_val)),
            ('"child"', json_val(child_val)),
        ]

        # With small probability, omit a random field (but not more than one)
        omit_idx = draw(st.one_of(st.none(), st.integers(min_value=0, max_value=5)))
        if omit_idx is not None:
            fields = [f for i, f in enumerate(fields) if i != omit_idx]

        # Shuffle field order
        fields = draw(st.permutations(fields))

        obj = "{" + ",".join(f"{k}:{v}" for k, v in fields) + "}"
        return obj.encode("utf-8")

    return _record

@st.composite
def generated_json(draw) -> bytes:
    # Limit recursion to 1 or 2 levels
    max_depth = draw(st.integers(min_value=0, max_value=1))
    return draw(record_strategy(max_depth))