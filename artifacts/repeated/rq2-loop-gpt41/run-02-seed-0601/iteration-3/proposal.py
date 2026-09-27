```python
from hypothesis import strategies as st

# Helper strategies for fields, with subtle edge cases
id_strategy = st.one_of(
    st.integers(min_value=-2**31, max_value=2**31-1),  # normal int
    st.floats(allow_nan=False, allow_infinity=False).filter(lambda x: x.is_integer()).map(int),  # int as float
    st.text(min_size=1, max_size=20).filter(lambda s: s.isdigit()).map(int),  # int as string (will be wrong type)
)

amount_strategy = st.one_of(
    st.text(min_size=0, max_size=20),  # normal string
    st.integers(min_value=-999999, max_value=999999).map(str),  # numeric string
    st.just(""),  # empty string
    st.none().map(lambda _: "null"),  # string "null"
)

name_strategy = st.one_of(
    st.text(min_size=0, max_size=20),  # normal string
    st.none(),  # null
    st.just("null"),  # string "null"
    st.just(""),  # empty string
    st.integers(min_value=-10, max_value=10).map(str),  # numeric string
)

status_strategy = st.one_of(
    st.sampled_from(["active", "inactive", "unknown"]),  # valid
    st.text(min_size=0, max_size=10).filter(lambda s: s not in {"active", "inactive", "unknown"}),  # invalid
    st.none().map(lambda _: "null"),  # string "null"
)

tags_strategy = st.one_of(
    st.lists(st.text(min_size=0, max_size=10), min_size=0, max_size=3),  # normal
    st.lists(st.integers(min_value=0, max_value=10).map(str), min_size=0, max_size=3),  # numeric strings
    st.lists(st.none(), min_size=0, max_size=3),  # nulls in array
    st.just([]),  # empty array
    st.just([""]),  # array with empty string
)

# Bounded recursion for "child"
@st.composite
def record_strategy(draw, depth=0):
    # At depth 1, child is always null to avoid deep recursion
    child_value = (
        "null" if depth >= 1 else
        draw(st.one_of(
            st.none(),
            record_strategy(depth=1)
        ))
    )
    # Compose fields, with subtle type errors possible
    id_val = draw(id_strategy)
    amount_val = draw(amount_strategy)
    name_val = draw(name_strategy)
    status_val = draw(status_strategy)
    tags_val = draw(tags_strategy)

    # Build JSON fields
    def json_str(val):
        # Properly escape strings for JSON
        return '"' + val.replace('\\', '\\\\').replace('"', '\\"') + '"'

    id_field = str(id_val) if isinstance(id_val, int) else json_str(str(id_val))
    amount_field = json_str(amount_val)
    name_field = "null" if name_val is None else json_str(str(name_val))
    status_field = json_str(status_val)
    tags_field = (
        "[" + ",".join(
            "null" if t is None else json_str(str(t)) for t in tags_val
        ) + "]"
    )
    child_field = "null" if child_value is None or child_value == "null" else child_value

    # Compose the JSON object
    json_obj = (
        "{"
        f"\"id\":{id_field},"
        f"\"amount\":{amount_field},"
        f"\"name\":{name_field},"
        f"\"status\":{status_field},"
        f"\"tags\":{tags_field},"
        f"\"child\":{child_field}"
        "}"
    )
    return json_obj

@st.composite
def generated_json(draw):
    # Top-level record, as bytes
    json_str = draw(record_strategy())
    return json_str.encode("utf-8")
```
**Key points:**
- Each field is *almost* correct, but sometimes off by type (e.g., string instead of int, nulls, empty strings, invalid enum).
- Recursion for `child` is bounded to one level.
- All output is valid JSON syntax, but may have semantic errors (wrong types, invalid enum, nulls in arrays).
- No imports except `from hypothesis import strategies as st`.
- Output is always a single JSON object as bytes.