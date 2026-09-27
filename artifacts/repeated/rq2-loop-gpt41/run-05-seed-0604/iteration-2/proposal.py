```python
from hypothesis import strategies as st

# Helper: JSON-escape a string (minimal, covers common cases)
def _json_escape(s):
    return (
        '"' +
        s.replace('\\', '\\\\')
         .replace('"', '\\"')
         .replace('\b', '\\b')
         .replace('\f', '\\f')
         .replace('\n', '\\n')
         .replace('\r', '\\r')
         .replace('\t', '\\t')
        + '"'
    )

# Helper: produce a valid JSON string (with some edge cases)
_json_string = st.text(
    alphabet=st.characters(
        blacklist_categories=('Cs',),  # no surrogates
        blacklist_characters=['"', '\\'],
        min_codepoint=0x20, max_codepoint=0x10FFFF
    ),
    min_size=0, max_size=24
).map(_json_escape)

# Helper: valid status values, plus some edge cases
_status_values = st.sampled_from([
    '"active"', '"inactive"', '"unknown"',
    '"ACTIVE"', '"Inactive"',  # case variants
    '""',  # empty string
    '"active "',  # trailing space
])

# Helper: valid tags array, plus some edge cases
def _tags_strategy():
    # Sometimes empty, sometimes with duplicates, sometimes with nulls or numbers
    base = st.lists(
        st.one_of(
            _json_string,
            st.just('null'),  # illegal, but valid JSON
            st.integers(-2, 2).map(str),  # numbers as elements
        ),
        min_size=0, max_size=5
    )
    # Sometimes, force all strings (valid), sometimes mix in edge cases
    return st.one_of(
        st.lists(_json_string, min_size=0, max_size=5),
        base
    )

# Helper: amount as string, but sometimes as number or null
def _amount_strategy():
    return st.one_of(
        _json_string,
        st.integers(-1000, 1000).map(str),  # as string
        st.integers(-1000, 1000).map(lambda n: str(n)),  # as string
        st.integers(-1000, 1000).map(lambda n: str(n)),  # as string
        st.just('null'),  # illegal, but valid JSON
        st.floats(-1e6, 1e6, allow_nan=False, allow_infinity=False).map(lambda f: '"%.2f"' % f),
        st.just('""'),  # empty string
    )

# Helper: id as int, but sometimes as string or float or null
def _id_strategy():
    return st.one_of(
        st.integers(0, 100000).map(str),
        st.integers(-10, 10).map(lambda n: '"%d"' % n),  # as string
        st.floats(-10, 10, allow_nan=False, allow_infinity=False).map(lambda f: str(f)),
        st.just('null'),  # illegal, but valid JSON
    )

# Helper: name as string or null, but sometimes as number or missing
def _name_strategy():
    return st.one_of(
        _json_string,
        st.just('null'),
        st.integers(-100, 100).map(str),  # as number
        st.just('""'),  # empty string
    )

# Helper: child as null or another record (one level only)
def _child_strategy(recursion_depth):
    if recursion_depth <= 0:
        return st.just('null')
    # 70% null, 30% nested object
    return st.one_of(
        st.just('null'),
        st.deferred(lambda: _record_strategy(recursion_depth - 1))
    )

# Compose the record fields, with some fields possibly omitted (to test missing fields)
def _record_strategy(recursion_depth):
    # Sometimes omit a field (but not all), to test missing-field handling
    field_strategies = {
        'id': _id_strategy(),
        'amount': _amount_strategy(),
        'name': _name_strategy(),
        'status': _status_values,
        'tags': _tags_strategy().map(lambda tags: '[' + ','.join(tags) + ']'),
        'child': _child_strategy(recursion_depth),
    }

    # Sometimes omit one field at random (except id, which is always present)
    keys = ['id', 'amount', 'name', 'status', 'tags', 'child']
    omit_one = st.sampled_from([k for k in keys if k != 'id'])
    def build(fields, omit):
        items = []
        for k in keys:
            if k == omit:
                continue
            items.append('"%s":%s' % (k, fields[k]))
        return '{' + ','.join(items) + '}'

    # 80% all fields, 20% omit one (except id)
    return st.one_of(
        st.fixed_dictionaries(field_strategies).map(
            lambda fields: '{' + ','.join('"%s":%s' % (k, fields[k]) for k in keys) + '}'
        ),
        st.tuples(
            st.fixed_dictionaries(field_strategies),
            omit_one
        ).map(lambda t: build(t[0], t[1]))
    )

@st.composite
def generated_json(draw) -> bytes:
    # Top-level record, recursion depth 1 (child can be a record or null, but not deeper)
    doc = draw(_record_strategy(1))
    # Ensure valid JSON object (no trailing commas, etc)
    return doc.encode('utf-8')
```
This strategy:
- Produces **syntactically valid JSON objects** only.
- Varies one or two fields at a time: wrong type, missing, null, edge-case values, etc.
- Sometimes omits a non-id field, sometimes includes all.
- Recurses only one level for `child`.
- Uses string concatenation, not `json` module.
- Keeps output size bounded and suitable for 500 examples.

This should maximize the chance of finding divergence between implementations, especially on edge cases and near-miss documents.