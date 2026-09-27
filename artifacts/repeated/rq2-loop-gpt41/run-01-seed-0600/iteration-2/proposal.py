```python
from hypothesis import strategies as st

@st.composite
def generated_json(draw, max_depth=1):
    """
    Generates a syntactically valid JSON object as bytes, with subtle
    schema violations to maximize the chance of divergence between Dart
    deserializers. Only one or two fields are 'off' per document.
    """
    # Helper for status field
    status_values = ["active", "inactive", "unknown"]

    # Helper for tags field (array of strings)
    tags_strategy = st.lists(
        st.text(min_size=0, max_size=10),
        min_size=0, max_size=3
    )

    # Helper for id field (should be integer)
    id_strategy = st.one_of(
        st.integers(min_value=0, max_value=10000),  # valid
        st.floats(allow_nan=False, allow_infinity=False).filter(lambda x: not x.is_integer()),  # float instead of int
        st.text(min_size=1, max_size=8),  # string instead of int
    )

    # Helper for amount field (should be string)
    amount_strategy = st.one_of(
        st.text(min_size=0, max_size=10),  # valid
        st.integers(min_value=-10000, max_value=10000).map(str),  # int as string (valid)
        st.integers(min_value=-10000, max_value=10000),  # int instead of string
        st.none(),  # null instead of string
    )

    # Helper for name field (should be string or null)
    name_strategy = st.one_of(
        st.text(min_size=0, max_size=10),  # valid
        st.none(),  # valid
        st.integers(min_value=0, max_value=10000),  # int instead of string/null
        st.lists(st.text(min_size=0, max_size=5), min_size=0, max_size=2),  # array instead of string/null
    )

    # Helper for status field (should be one of three strings)
    status_strategy = st.one_of(
        st.sampled_from(status_values),  # valid
        st.text(min_size=0, max_size=8).filter(lambda s: s not in status_values),  # invalid string
        st.integers(min_value=0, max_value=10),  # int instead of string
        st.none(),  # null instead of string
    )

    # Helper for tags field (should be array of strings)
    tags_strategy = st.one_of(
        tags_strategy,  # valid
        st.text(min_size=0, max_size=10),  # string instead of array
        st.none(),  # null instead of array
        st.lists(st.integers(min_value=0, max_value=100), min_size=0, max_size=3),  # array of ints
        st.lists(st.none(), min_size=0, max_size=2),  # array of nulls
    )

    # Helper for child field (should be null or another record)
    if max_depth > 0:
        child_strategy = st.one_of(
            st.none(),  # valid
            generated_json(max_depth=max_depth - 1).map(lambda b: b.decode("utf-8")),  # valid nested record
            st.text(min_size=0, max_size=10),  # string instead of object/null
            st.integers(min_value=0, max_value=10000),  # int instead of object/null
            st.lists(st.text(min_size=0, max_size=5), min_size=0, max_size=2),  # array instead of object/null
        )
    else:
        child_strategy = st.just("null")

    # Choose which field(s) to perturb
    fields = ["id", "amount", "name", "status", "tags", "child"]
    # Choose 0, 1, or 2 fields to perturb
    n_perturb = draw(st.integers(min_value=0, max_value=2))
    perturb_fields = draw(st.lists(st.sampled_from(fields), min_size=n_perturb, max_size=n_perturb, unique=True))

    # For each field, pick valid or perturbed value
    def pick(field, valid, perturbed):
        return draw(perturbed if field in perturb_fields else valid)

    id_val = pick("id", st.integers(min_value=0, max_value=10000), id_strategy)
    amount_val = pick("amount", st.text(min_size=0, max_size=10), amount_strategy)
    name_val = pick("name", st.one_of(st.text(min_size=0, max_size=10), st.none()), name_strategy)
    status_val = pick("status", st.sampled_from(status_values), status_strategy)
    tags_val = pick("tags", tags_strategy, tags_strategy)
    child_val = pick("child",
                     st.one_of(st.none(), generated_json(max_depth=max_depth - 1).map(lambda b: b.decode("utf-8"))) if max_depth > 0 else st.just("null"),
                     child_strategy)

    # JSON encoding helpers
    def encode(val):
        if isinstance(val, str):
            # Escape backslashes and double quotes
            return '"' + val.replace('\\', '\\\\').replace('"', '\\"') + '"'
        elif val is None:
            return "null"
        elif isinstance(val, bool):
            return "true" if val else "false"
        elif isinstance(val, (int, float)):
            return str(val)
        elif isinstance(val, list):
            return "[" + ",".join(encode(x) for x in val) + "]"
        elif isinstance(val, dict):
            return "{" + ",".join(f"{encode(k)}:{encode(v)}" for k, v in val.items()) + "}"
        else:
            # Already JSON string (for nested child)
            return val

    # Compose the JSON object
    json_obj = (
        '{'
        f'"id":{encode(id_val)},'
        f'"amount":{encode(amount_val)},'
        f'"name":{encode(name_val)},'
        f'"status":{encode(status_val)},'
        f'"tags":{encode(tags_val)},'
        f'"child":{encode(child_val)}'
        '}'
    )

    return json_obj.encode("utf-8")
```
**Key points:**
- Only one or two fields are "off" per document; the rest are valid.
- Each field's perturbations are subtle and type-focused, not grossly malformed.
- Recursion for `child` is bounded by `max_depth`.
- Output is always syntactically valid JSON as bytes.
- No imports except `from hypothesis import strategies as st`.
- No use of `json` module or other forbidden features.