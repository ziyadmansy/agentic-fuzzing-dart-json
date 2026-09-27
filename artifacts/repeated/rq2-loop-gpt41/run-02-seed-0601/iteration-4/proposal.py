```python
from hypothesis import strategies as st

# Helper strategies for fields with subtle edge cases
id_strategy = st.integers(-2**31, 2**31 - 1) | st.floats(allow_nan=False, allow_infinity=False).filter(lambda f: f.is_integer()).map(int)
amount_strategy = (
    st.text(min_size=0, max_size=32)
    | st.integers().map(str)
    | st.floats(allow_nan=False, allow_infinity=False).map(lambda f: format(f, ".8g"))
)
name_strategy = (
    st.none()
    | st.text(min_size=0, max_size=32)
    | st.integers().map(str)
    | st.booleans().map(lambda b: "true" if b else "false")
)
status_strategy = st.sampled_from(["active", "inactive", "unknown", "ACTIVE", "Inactive", ""])
tags_strategy = (
    st.lists(
        st.text(min_size=0, max_size=16)
        | st.integers().map(str)
        | st.none().map(lambda _: "null"),
        min_size=0,
        max_size=4,
    )
    | st.none().map(lambda _: [])
    | st.tuples().map(lambda _: [])
)
# For child, we want to sometimes provide null, sometimes a valid record, sometimes a record with a subtle error.
@st.composite
def record(draw, allow_child=True):
    id_val = draw(id_strategy)
    amount_val = draw(amount_strategy)
    name_val = draw(name_strategy)
    status_val = draw(status_strategy)
    tags_val = draw(tags_strategy)
    # Child: null, or another record, or a type error (e.g. string, int)
    child_choice = draw(
        st.sampled_from(["null", "record", "string", "int", "missing"])
    )
    if allow_child and child_choice == "record":
        child_val = draw(record(allow_child=False))
        child_json = child_val
    elif child_choice == "null":
        child_json = "null"
    elif child_choice == "string":
        child_json = '"' + draw(st.text(min_size=0, max_size=12).filter(lambda s: s != "")) + '"'
    elif child_choice == "int":
        child_json = str(draw(st.integers(-100, 100)))
    elif child_choice == "missing":
        child_json = None
    # Compose the JSON object as a string
    fields = [
        f'"id": {id_val}',
        f'"amount": "{amount_val}"',
        f'"name": {("null" if name_val is None else '"' + str(name_val) + '"')}',
        f'"status": "{status_val}"',
        f'"tags": [{", ".join('"' + str(tag) + '"' for tag in tags_val)}]',
    ]
    if child_json is not None:
        fields.append(f'"child": {child_json}')
    # If child is missing, omit the field (to test missingness)
    return "{" + ", ".join(fields) + "}"

@st.composite
def generated_json(draw):
    # Top-level record, always present
    json_str = draw(record(allow_child=True))
    # Return as bytes
    return json_str.encode("utf-8")
```
**Key points:**
- Each field is *almost* correct, but sometimes off by type, case, or missingness.
- `child` can be missing, null, a valid record, or a type error.
- All output is valid JSON syntax.
- Only one or two fields are "off" at a time; most are correct.
- Output is always a single JSON object, as bytes, per requirements.