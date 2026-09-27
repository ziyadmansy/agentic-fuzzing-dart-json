```python
from hypothesis import strategies as st

# Helper strategies for field values
id_strategy = st.integers(min_value=-2**31, max_value=2**31-1)

# Amount: normally a string, but sometimes a number or null to probe type handling
amount_strategy = st.one_of(
    st.text(min_size=0, max_size=20).map(lambda s: f'"{s}"'),
    st.integers().map(str),
    st.just('null')
)

# Name: normally string or null, but sometimes a number or bool
name_strategy = st.one_of(
    st.text(min_size=0, max_size=20).map(lambda s: f'"{s}"'),
    st.just('null'),
    st.integers().map(str),
    st.booleans().map(lambda b: 'true' if b else 'false')
)

# Status: normally one of the three, but sometimes a number or null
status_strategy = st.one_of(
    st.sampled_from(['"active"', '"inactive"', '"unknown"']),
    st.integers().map(str),
    st.just('null')
)

# Tags: normally array of strings, but sometimes array of numbers, or null, or string
tags_strategy = st.one_of(
    st.lists(st.text(min_size=0, max_size=10).map(lambda s: f'"{s}"'), min_size=0, max_size=4)
        .map(lambda items: '[' + ', '.join(items) + ']'),
    st.lists(st.integers(), min_size=0, max_size=4)
        .map(lambda items: '[' + ', '.join(map(str, items)) + ']'),
    st.just('null'),
    st.text(min_size=0, max_size=20).map(lambda s: f'"{s}"')
)

# Child: recursive, but sometimes wrong type or missing fields
def child_strategy(recursion):
    if recursion <= 0:
        return st.just('null')
    # Sometimes null, sometimes a valid record, sometimes a dict with missing/wrong fields
    valid_child = st.deferred(lambda: record_strategy(recursion - 1))
    # Malformed child: missing fields, extra fields, wrong types
    malformed_child = st.fixed_dictionaries({
        "id": st.integers().map(str),
        "amount": st.just('null'),
        "name": st.just('null'),
        "status": st.just('null'),
        "tags": st.just('null'),
        # child field missing or wrong type
    }).map(lambda d: '{' + ', '.join(f'"{k}": {v}' for k, v in d.items() if k != "child") + '}')
    wrong_type_child = st.sampled_from(['"string"', '123', 'true', '[]'])
    return st.one_of(
        st.just('null'),
        valid_child,
        malformed_child,
        wrong_type_child
    )

# Record strategy
def record_strategy(recursion):
    return st.tuples(
        id_strategy,
        amount_strategy,
        name_strategy,
        status_strategy,
        tags_strategy,
        child_strategy(recursion)
    ).map(lambda fields: (
        '{'
        f'"id": {fields[0]}, '
        f'"amount": {fields[1]}, '
        f'"name": {fields[2]}, '
        f'"status": {fields[3]}, '
        f'"tags": {fields[4]}, '
        f'"child": {fields[5]}'
        '}'
    ))

@st.composite
def generated_json(draw) -> bytes:
    # Limit recursion to 1 (top-level + one child)
    json_str = draw(record_strategy(recursion=1))
    return json_str.encode('utf-8')
```
This strategy:

- Always emits syntactically valid JSON objects.
- Varies one or two fields at a time to be "almost" correct but with subtle type or value deviations.
- Sometimes emits wrong types (number/null/bool for string fields, etc).
- Sometimes emits malformed or missing child fields, or wrong type for `child`.
- Keeps recursion and output size bounded.
- Avoids broad malformation, focusing on near-miss cases most likely to trigger divergence.

**No imports except `from hypothesis import strategies as st`.**