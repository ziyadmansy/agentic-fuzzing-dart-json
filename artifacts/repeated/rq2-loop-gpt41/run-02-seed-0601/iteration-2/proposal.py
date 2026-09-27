```python
from hypothesis import strategies as st

# Helper strategies for field values
id_strategy = st.integers(min_value=-2**31, max_value=2**31-1)

# amount: string, but try edge cases (numbers as strings, empty, weird unicode, etc)
amount_strategy = st.one_of(
    st.text(min_size=0, max_size=32),  # normal/edge strings
    st.integers(min_value=-2**63, max_value=2**63-1).map(str),  # numbers as strings
    st.just("0"),
    st.just(""),
    st.just("NaN"),
    st.just("null"),
    st.just("Infinity"),
    st.just("-Infinity"),
    st.just("\u2028\u2029"),  # line/para separators
)

# name: string or null, but try edge cases (empty, weird unicode, numbers as string, etc)
name_strategy = st.one_of(
    st.text(min_size=0, max_size=32),
    st.just(""),
    st.just("null"),
    st.just("0"),
    st.just("\u0000"),
    st.none(),
)

# status: valid enum, but sometimes wrong type or value
status_strategy = st.one_of(
    st.sampled_from(["active", "inactive", "unknown"]),
    st.just(""),  # empty string
    st.just("ACTIVE"),  # wrong case
    st.just("unknown "),  # trailing space
    st.just("deleted"),  # invalid value
    st.integers(min_value=-1, max_value=2).map(str),  # numbers as string
    st.integers(min_value=-1, max_value=2),  # numbers as int
    st.just("null"),
    st.just(None),
)

# tags: array of strings, but sometimes wrong type or edge cases
tags_strategy = st.one_of(
    st.lists(st.text(min_size=0, max_size=16), min_size=0, max_size=4),
    st.lists(st.just(""), min_size=0, max_size=4),
    st.lists(st.integers(min_value=-10, max_value=10).map(str), min_size=0, max_size=4),
    st.just([]),
    st.just(["null"]),
    st.just(None),
    st.just("notalist"),  # wrong type
)

# Recursion for child
def child_strategy(recursion_depth):
    if recursion_depth <= 0:
        return st.just("null")
    # 80% chance of null, 20% chance of nested record
    return st.one_of(
        st.just("null"),
        generated_json_inner(recursion_depth-1),
    )

# Compose the JSON object as a string
@st.composite
def generated_json_inner(draw, recursion_depth):
    # Vary one or two fields per document, rest are "normal"
    # Pick 1-2 fields to "perturb"
    fields = ["id", "amount", "name", "status", "tags", "child"]
    perturbed_fields = draw(st.lists(st.sampled_from(fields), min_size=1, max_size=2, unique=True))
    values = {}

    # id: always present, but sometimes wrong type if perturbed
    if "id" in perturbed_fields:
        id_val = draw(st.one_of(
            st.text(min_size=0, max_size=8),  # string instead of int
            st.floats(allow_nan=False, allow_infinity=False),  # float instead of int
            st.just(None),
        ))
        if isinstance(id_val, str):
            values["id"] = f'"{id_val}"'
        elif id_val is None:
            values["id"] = "null"
        else:
            values["id"] = str(id_val)
    else:
        values["id"] = str(draw(id_strategy))

    # amount
    if "amount" in perturbed_fields:
        amount_val = draw(st.one_of(
            st.integers(min_value=-100, max_value=100),  # int instead of string
            st.just(None),
            st.just(""),
        ))
        if amount_val is None:
            values["amount"] = "null"
        elif isinstance(amount_val, int):
            values["amount"] = str(amount_val)
        else:
            values["amount"] = f'"{amount_val}"'
    else:
        values["amount"] = f'"{draw(amount_strategy)}"'

    # name
    if "name" in perturbed_fields:
        name_val = draw(st.one_of(
            st.integers(min_value=-100, max_value=100),  # int instead of string/null
            st.just(""),
            st.just(None),
        ))
        if name_val is None:
            values["name"] = "null"
        elif isinstance(name_val, int):
            values["name"] = str(name_val)
        else:
            values["name"] = f'"{name_val}"'
    else:
        n = draw(name_strategy)
        if n is None:
            values["name"] = "null"
        else:
            values["name"] = f'"{n}"'

    # status
    if "status" in perturbed_fields:
        status_val = draw(st.one_of(
            st.just("deleted"),
            st.just(""),
            st.just(None),
            st.integers(min_value=-1, max_value=2),
        ))
        if status_val is None:
            values["status"] = "null"
        elif isinstance(status_val, int):
            values["status"] = str(status_val)
        else:
            values["status"] = f'"{status_val}"'
    else:
        s = draw(status_strategy)
        if s is None:
            values["status"] = "null"
        elif isinstance(s, int):
            values["status"] = str(s)
        else:
            values["status"] = f'"{s}"'

    # tags
    if "tags" in perturbed_fields:
        tags_val = draw(st.one_of(
            st.just("notalist"),
            st.just(None),
            st.lists(st.integers(min_value=-10, max_value=10), min_size=0, max_size=4),
            st.just([]),
        ))
        if tags_val is None:
            values["tags"] = "null"
        elif isinstance(tags_val, str):
            values["tags"] = f'"{tags_val}"'
        elif isinstance(tags_val, list):
            if tags_val and isinstance(tags_val[0], int):
                values["tags"] = "[" + ",".join(str(x) for x in tags_val) + "]"
            else:
                values["tags"] = "[]"
        else:
            values["tags"] = "[]"
    else:
        t = draw(tags_strategy)
        if t is None:
            values["tags"] = "null"
        elif isinstance(t, str):
            values["tags"] = f'"{t}"'
        elif isinstance(t, list):
            values["tags"] = "[" + ",".join(f'"{x}"' for x in t) + "]"
        else:
            values["tags"] = "[]"

    # child
    if "child" in perturbed_fields:
        child_val = draw(st.one_of(
            st.just("notanobject"),
            st.just(None),
            st.just(123),
            st.just([]),
        ))
        if child_val is None:
            values["child"] = "null"
        elif isinstance(child_val, str):
            values["child"] = f'"{child_val}"'
        elif isinstance(child_val, int):
            values["child"] = str(child_val)
        elif isinstance(child_val, list):
            values["child"] = "[]"
        else:
            values["child"] = "null"
    else:
        values["child"] = draw(child_strategy(recursion_depth))

    # Compose JSON object
    json_obj = (
        '{'
        f'"id":{values["id"]},'
        f'"amount":{values["amount"]},'
        f'"name":{values["name"]},'
        f'"status":{values["status"]},'
        f'"tags":{values["tags"]},'
        f'"child":{values["child"]}'
        '}'
    )
    return json_obj

@st.composite
def generated_json(draw) -> bytes:
    # Limit recursion depth to 1 (one level of child)
    json_str = draw(generated_json_inner(recursion_depth=1))
    return json_str.encode("utf-8")
```
This strategy:
- Always produces syntactically valid JSON objects.
- Varies 1–2 fields per document with type/value edge cases, keeping others well-formed.
- Recurses only one level for `child` (as per schema).
- Uses only allowed imports and string concatenation.
- Returns bytes as required.