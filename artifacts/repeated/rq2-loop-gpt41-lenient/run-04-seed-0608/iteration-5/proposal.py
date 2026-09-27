Certainly! Here’s a **Hypothesis strategy** that generates *syntactically valid JSON objects* matching your schema, but with subtle, targeted variations that are likely to trigger divergence between Dart deserializers. This strategy:

- Always emits all six fields, but sometimes with slightly off-type or boundary values.
- Varies only one or two fields at a time, keeping the rest strictly valid.
- Uses bounded recursion for the `child` field.
- Produces output as `bytes` (UTF-8 encoded JSON).

```python
from hypothesis import strategies as st

@st.composite
def generated_json(draw, max_depth=1):
    # Helper: valid and "almost valid" values for each field
    id_valid = st.integers(min_value=0, max_value=2**31-1)
    id_offtype = st.sampled_from([
        '"123"', 'null', '1.0', 'true', 'false', '[]', '{}'
    ])
    id_strategy = st.one_of(
        id_valid.map(str),
        id_offtype
    )

    amount_valid = st.text(min_size=0, max_size=12)
    amount_offtype = st.sampled_from([
        '123', 'null', 'true', 'false', '[]', '{}'
    ])
    amount_strategy = st.one_of(
        amount_valid.map(lambda s: '"' + s.replace('"', '\\"') + '"'),
        amount_offtype
    )

    name_valid = st.one_of(
        st.text(min_size=0, max_size=12).map(lambda s: '"' + s.replace('"', '\\"') + '"'),
        st.just('null')
    )
    name_offtype = st.sampled_from([
        '123', 'true', 'false', '[]', '{}'
    ])
    name_strategy = st.one_of(
        name_valid,
        name_offtype
    )

    status_valid = st.sampled_from(['"active"', '"inactive"', '"unknown"'])
    status_offtype = st.sampled_from([
        'null', '123', 'true', 'false', '"ACTIVE"', '"Active"', '[]', '{}'
    ])
    status_strategy = st.one_of(
        status_valid,
        status_offtype
    )

    tag_str = st.text(min_size=0, max_size=8).map(lambda s: '"' + s.replace('"', '\\"') + '"')
    tags_valid = st.lists(tag_str, min_size=0, max_size=3).map(lambda l: '[' + ','.join(l) + ']')
    tags_offtype = st.sampled_from([
        'null', '123', 'true', 'false', '{}', '"notalist"'
    ])
    tags_strategy = st.one_of(
        tags_valid,
        tags_offtype
    )

    # Recursion: child is either null or another record (with depth limit)
    if max_depth <= 0:
        child_valid = st.just('null')
    else:
        child_valid = st.one_of(
            st.just('null'),
            generated_json(max_depth=max_depth-1).map(lambda b: b.decode('utf-8'))
        )
    child_offtype = st.sampled_from([
        '123', 'true', 'false', '[]', '"notarecord"'
    ])
    child_strategy = st.one_of(
        child_valid,
        child_offtype
    )

    # Pick one or two fields to "perturb" per document, rest are strictly valid
    fields = ['id', 'amount', 'name', 'status', 'tags', 'child']
    perturb_count = draw(st.integers(min_value=0, max_value=2))
    perturb_fields = draw(st.lists(st.sampled_from(fields), min_size=perturb_count, max_size=perturb_count, unique=True))

    def pick(field, valid, offtype):
        return draw(offtype if field in perturb_fields else valid)

    id_val = pick('id', id_valid.map(str), id_offtype)
    amount_val = pick('amount', amount_valid.map(lambda s: '"' + s.replace('"', '\\"') + '"'), amount_offtype)
    name_val = pick('name', name_valid, name_offtype)
    status_val = pick('status', status_valid, status_offtype)
    tags_val = pick('tags', tags_valid, tags_offtype)
    child_val = pick('child', child_valid, child_offtype)

    json_str = (
        '{'
        f'"id": {id_val}, '
        f'"amount": {amount_val}, '
        f'"name": {name_val}, '
        f'"status": {status_val}, '
        f'"tags": {tags_val}, '
        f'"child": {child_val}'
        '}'
    )
    return json_str.encode('utf-8')
```

**Key points:**
- Only one or two fields are "off" per document, maximizing the chance of divergence.
- All JSON is syntactically valid.
- Recursion for `child` is bounded by `max_depth`.
- Output is always `bytes`.

**Usage:**  
Use this as your Hypothesis strategy for generating test documents. Adjust `max_depth` or field perturbation as needed for your campaign.