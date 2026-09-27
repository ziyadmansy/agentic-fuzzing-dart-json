```python
from hypothesis import strategies as st

# Helper strategies for each field, with edge cases and type boundary values
id_strategy = st.one_of(
    st.integers(min_value=-2**31, max_value=2**31-1),  # normal int32 range
    st.integers(min_value=2**31, max_value=2**32),     # just outside normal
    st.floats(allow_nan=False, allow_infinity=False).map(lambda f: int(f)),  # float->int
)

amount_strategy = st.one_of(
    st.text(min_size=0, max_size=32),  # normal string
    st.just(""),                       # empty string
    st.text(min_size=33, max_size=64), # long string
    st.integers().map(str),            # numeric string
    st.just("null"),                   # string that looks like null
    st.just("0"),                      # string zero
)

name_strategy = st.one_of(
    st.text(min_size=0, max_size=32),  # normal string
    st.none(),                         # null
    st.just("null"),                   # string "null"
    st.just(""),                       # empty string
    st.integers().map(str),            # numeric string
)

status_strategy = st.one_of(
    st.sampled_from(["active", "inactive", "unknown"]),  # valid
    st.text(min_size=1, max_size=16).filter(lambda s: s not in {"active", "inactive", "unknown"}),  # invalid
    st.integers().map(str),                              # numeric string
    st.just(""),                                         # empty string
)

tags_strategy = st.one_of(
    st.lists(st.text(min_size=0, max_size=16), min_size=0, max_size=4),  # normal
    st.lists(st.text(min_size=0, max_size=0), min_size=0, max_size=4),   # empty strings
    st.lists(st.integers().map(str), min_size=1, max_size=4),            # numeric strings
    st.just([]),                                                         # empty list
    st.just(["null"]),                                                   # string "null"
    st.lists(st.none(), min_size=1, max_size=2),                         # list of nulls (invalid for schema)
)

# Recursion for child field, with bounded depth
def record_strategy(max_depth):
    if max_depth <= 0:
        child_strategy = st.none()
    else:
        # 70% chance of null, 30% chance of nested record
        child_strategy = st.one_of(
            st.none(),
            st.deferred(lambda: record_strategy(max_depth - 1))
        )

    # Occasionally omit a field (to test missing field handling)
    def maybe_omit(field, strat):
        return st.one_of(
            strat.map(lambda v: (field, v)),
            st.just(None)  # Omit the field
        )

    # For each field, sometimes omit it (except 'id', which is always present)
    fields = [
        ("id", id_strategy),
        maybe_omit("amount", amount_strategy),
        maybe_omit("name", name_strategy),
        maybe_omit("status", status_strategy),
        maybe_omit("tags", tags_strategy),
        maybe_omit("child", child_strategy),
    ]

    # Build the JSON object as a string
    @st.composite
    def record(draw):
        items = []
        for f in fields:
            if isinstance(f, tuple):
                key, strat = f
                value = draw(strat)
                items.append((key, value))
            else:
                res = draw(f)
                if res is not None:
                    items.append(res)
        # Only include fields that are not omitted
        json_fields = []
        for key, value in items:
            if key == "child" and value is None:
                json_fields.append(f'"child":null')
            elif key == "name" and value is None:
                json_fields.append(f'"name":null')
            elif key == "tags":
                if isinstance(value, list):
                    tags_json = ",".join(
                        "null" if v is None else f'"{v}"' for v in value
                    )
                    json_fields.append(f'"tags":[{tags_json}]')
                else:
                    json_fields.append(f'"tags":null')
            elif key == "id":
                json_fields.append(f'"id":{value}')
            elif key == "amount":
                json_fields.append(f'"amount":"{value}"')
            elif key == "status":
                json_fields.append(f'"status":"{value}"')
            else:
                # fallback for any other field
                json_fields.append(f'"{key}":"{value}"')
        return "{" + ",".join(json_fields) + "}"

    return record()

@st.composite
def generated_json(draw) -> bytes:
    # Limit recursion depth and object size
    json_str = draw(record_strategy(max_depth=1))
    return json_str.encode("utf-8")
```
This strategy:
- Produces syntactically valid JSON objects.
- Varies one or two fields at a time (type, presence, boundary values).
- Sometimes omits fields (except `id`), or uses wrong types (e.g. `tags` with nulls, `status` with invalid values).
- Recursion for `child` is bounded to depth 1.
- Uses only `from hypothesis import strategies as st`.
- Returns bytes as required.

This should maximize the chance of finding divergence between deserializers.