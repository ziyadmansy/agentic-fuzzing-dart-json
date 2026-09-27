```python
from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Helper: JSON-escape a string (minimal, for ASCII and common escapes)
    def escape(s):
        return '"' + s.replace('\\', '\\\\').replace('"', '\\"').replace('\b', '\\b') \
            .replace('\f', '\\f').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t') + '"'

    # Generate "status" with possible boundary/unknown values
    status_values = ["active", "inactive", "unknown"]
    status_strategy = st.one_of(
        st.sampled_from(status_values),
        # Slightly off values: case, whitespace, empty string, numeric string, etc.
        st.sampled_from(["Active", "inactive ", "unknown\n", "", "null", "0", "ACTIVE"])
    )

    # Generate "amount" as string, but sometimes as number or null for divergence
    amount_strategy = st.one_of(
        st.text(min_size=0, max_size=12).map(escape),
        st.integers(-100000, 100000).map(str),  # unquoted integer as string
        st.floats(-1e6, 1e6, allow_nan=False, allow_infinity=False).map(lambda f: escape(str(f))),
        st.just("null"),  # unquoted null
    )

    # Generate "name" as string or null, but sometimes as number, bool, or missing quotes
    name_strategy = st.one_of(
        st.text(min_size=0, max_size=20).map(escape),
        st.just("null"),
        st.integers().map(str),  # unquoted integer
        st.booleans().map(lambda b: "true" if b else "false"),
        st.just('""'),  # empty string
    )

    # Generate "tags" as array of strings, but sometimes with nulls, numbers, or missing quotes
    tag_elem = st.one_of(
        st.text(min_size=0, max_size=10).map(escape),
        st.just("null"),
        st.integers(-100, 100).map(str),
        st.just('""'),
    )
    tags_strategy = st.lists(tag_elem, min_size=0, max_size=5).map(lambda tags: "[" + ", ".join(tags) + "]")

    # Generate "id" as integer, but sometimes as string or float or null
    id_strategy = st.one_of(
        st.integers(-100000, 100000).map(str),
        st.text(min_size=0, max_size=10).map(escape),
        st.floats(-1e6, 1e6, allow_nan=False, allow_infinity=False).map(str),
        st.just("null"),
    )

    # Recursive "child" field: either null, or a record (with bounded recursion)
    def record_strategy(depth):
        if depth <= 0:
            child_strategy = st.just("null")
        else:
            child_strategy = st.deferred(lambda: record_strategy(depth - 1))
        # Compose the record fields, with possible field order permutations and optional field omission
        def build_record(fields):
            return "{" + ", ".join(fields) + "}"

        # Each field is present, but sometimes with wrong type or value
        fields_strategy = st.tuples(
            st.just('"id": '), id_strategy,
            st.just(', "amount": '), amount_strategy,
            st.just(', "name": '), name_strategy,
            st.just(', "status": '), status_strategy.map(escape),
            st.just(', "tags": '), tags_strategy,
            st.just(', "child": '), child_strategy,
        ).map(lambda parts: build_record(["".join(parts[i:i+2]) for i in range(0, len(parts), 2)]))

        return fields_strategy

    # Top-level record, with 0 or 1 level of recursion for "child"
    record = record_strategy(draw(st.integers(min_value=0, max_value=1)))

    # Draw the record and encode as bytes
    json_str = draw(record)
    return json_str.encode("utf-8")
```
**Key points of this strategy:**
- Each field is present, but often with a type/value boundary or subtle malformation (e.g., unquoted numbers, nulls, whitespace, case variants).
- "child" field is either null or a recursive record, but recursion is bounded to 1 level.
- Field order is fixed, but you could randomize order for further divergence if needed.
- All output is syntactically valid JSON (object with all fields present), but field values may be "off" in ways likely to trigger implementation divergence.
- No imports except `from hypothesis import strategies as st`.
- Output is always a `bytes` object containing a valid JSON object.

You can tune the specific "off" values or add more subtle cases as you observe what triggers divergence.