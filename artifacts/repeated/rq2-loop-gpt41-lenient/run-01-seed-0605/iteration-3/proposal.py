from hypothesis import strategies as st

# Constants for field values
STATUSES = ["active", "inactive", "unknown"]

# Helper: JSON-escape a string (minimal, for test data)
def _json_escape(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

# Helper: Generate a JSON array of strings
def _json_array_of_strings(strings):
    return "[" + ",".join(_json_escape(s) for s in strings) + "]"

# Helper: Generate a JSON object from field dict
def _json_object(fields):
    return "{" + ",".join(f"{_json_escape(k)}:{v}" for k, v in fields.items()) + "}"

# Main record generator
@st.composite
def generated_json(draw, *, _recursion=0):
    # 1. id: integer, but try boundary and off-type values
    id_strategy = st.one_of(
        st.integers(min_value=-2**31, max_value=2**31-1),  # normal int
        st.just(0),  # boundary
        st.just(-1),  # negative
        st.just(2**31-1),  # max 32-bit
        st.just(-2**31),  # min 32-bit
        st.floats(allow_nan=False, allow_infinity=False).map(lambda f: str(f)),  # as string (wrong type)
        st.text(min_size=1, max_size=6),  # as string (wrong type)
        st.just("null"),  # as string "null"
    )
    id_val = draw(id_strategy)
    if isinstance(id_val, int):
        id_json = str(id_val)
    else:
        id_json = _json_escape(str(id_val))

    # 2. amount: string, but try numbers and null
    amount_strategy = st.one_of(
        st.text(min_size=0, max_size=12),  # normal string
        st.integers(min_value=-10000, max_value=10000).map(str),  # numeric string
        st.just(""),  # empty string
        st.just(None),  # null
        st.floats(allow_nan=False, allow_infinity=False).map(str),  # float string
        st.integers(min_value=-10000, max_value=10000),  # wrong type: int
        st.just("null"),  # string "null"
    )
    amount_val = draw(amount_strategy)
    if amount_val is None:
        amount_json = "null"
    elif isinstance(amount_val, int):
        amount_json = str(amount_val)
    else:
        amount_json = _json_escape(str(amount_val))

    # 3. name: string or null, but try numbers, bools, empty, missing
    name_strategy = st.one_of(
        st.text(min_size=0, max_size=10),  # normal string
        st.just(None),  # null
        st.integers(min_value=-100, max_value=100).map(str),  # numeric string
        st.integers(min_value=-100, max_value=100),  # wrong type: int
        st.just(True),  # bool
        st.just(False),  # bool
        st.just("null"),  # string "null"
    )
    name_val = draw(name_strategy)
    if name_val is None:
        name_json = "null"
    elif isinstance(name_val, bool):
        name_json = "true" if name_val else "false"
    elif isinstance(name_val, int):
        name_json = str(name_val)
    else:
        name_json = _json_escape(str(name_val))

    # 4. status: enum, but try wrong case, wrong type, null, missing
    status_strategy = st.one_of(
        st.sampled_from(STATUSES),
        st.sampled_from([s.upper() for s in STATUSES]),  # wrong case
        st.text(min_size=3, max_size=8),  # random string
        st.just(None),  # null
        st.integers(min_value=0, max_value=2),  # wrong type: int
        st.just(""),  # empty string
        st.just("null"),  # string "null"
    )
    status_val = draw(status_strategy)
    if status_val is None:
        status_json = "null"
    elif isinstance(status_val, int):
        status_json = str(status_val)
    else:
        status_json = _json_escape(str(status_val))

    # 5. tags: array of strings, but try empty, wrong types, null, mixed
    tag_elem_strategy = st.one_of(
        st.text(min_size=0, max_size=8),
        st.integers(min_value=-10, max_value=10).map(str),  # numeric string
        st.integers(min_value=-10, max_value=10),  # wrong type: int
        st.just(None),  # null in array
        st.just("null"),  # string "null"
        st.just(""),  # empty string
    )
    tags_strategy = st.one_of(
        st.lists(tag_elem_strategy, min_size=0, max_size=4),
        st.just(None),  # tags: null
        st.just("not-an-array"),  # tags: wrong type
        st.just([]),  # empty array
    )
    tags_val = draw(tags_strategy)
    if tags_val is None:
        tags_json = "null"
    elif isinstance(tags_val, str):
        tags_json = _json_escape(tags_val)
    elif isinstance(tags_val, list):
        # Mixed types in array
        tags_json = "[" + ",".join(
            "null" if v is None else (str(v) if isinstance(v, int) else _json_escape(str(v)))
            for v in tags_val
        ) + "]"
    else:
        tags_json = "null"

    # 6. child: Record or null or wrong type
    child_strategy = st.one_of(
        st.just(None),
        st.just("not-an-object"),
        st.just(123),
        st.just([]),
        st.just("null"),
        # Recurse only once
        generated_json(_recursion=_recursion+1) if _recursion < 1 else st.just(None),
    )
    child_val = draw(child_strategy)
    if child_val is None:
        child_json = "null"
    elif isinstance(child_val, bytes):
        child_json = child_val.decode("utf-8")
    elif isinstance(child_val, int):
        child_json = str(child_val)
    elif isinstance(child_val, list):
        child_json = "[]"
    else:
        child_json = _json_escape(str(child_val))

    # Optionally omit one field to test missing fields (but only one at a time)
    fields = {
        "id": id_json,
        "amount": amount_json,
        "name": name_json,
        "status": status_json,
        "tags": tags_json,
        "child": child_json,
    }
    # Randomly drop one field (rarely)
    if draw(st.booleans()) and draw(st.integers(min_value=0, max_value=6)) == 0:
        drop_field = draw(st.sampled_from(list(fields.keys())))
        del fields[drop_field]

    json_obj = _json_object(fields)
    return json_obj.encode("utf-8")