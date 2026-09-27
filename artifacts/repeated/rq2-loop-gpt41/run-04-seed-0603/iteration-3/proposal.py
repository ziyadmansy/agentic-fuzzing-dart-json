from hypothesis import strategies as st

# Helper: JSON string escaping (minimal, for ASCII and common cases)
def _json_escape(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"').replace('\b', '\\b').replace('\f', '\\f').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t') + '"'

# Helper: valid status values, plus some edge cases
_status_values = ["active", "inactive", "unknown"]

# Helper: generate a string that is not a valid status
def _not_status():
    return st.text(
        min_size=0, max_size=10
    ).filter(lambda s: s not in _status_values)

# Helper: valid and edge-case string for "amount"
def _amount_strings():
    # valid: decimal, integer, negative, zero, leading zeros, scientific, empty, weird unicode
    valid = [
        "0", "1", "-1", "123.45", "-0.001", "1e10", "000123", "1.0e-5", "0.0", "9999999999999999999999999", "NaN", "Infinity", "-Infinity", "\u20AC1000"
    ]
    return st.one_of(
        st.sampled_from(valid),
        st.text(min_size=0, max_size=20)
    )

# Helper: valid and edge-case string for "name"
def _name_strings():
    # null, empty, normal, unicode, control chars, long, emoji
    valid = [
        "", "Alice", "Bob", "Eve", "A" * 100, "😀", "Núñez", "O'Connor", "Smith\nJones", "李雷", "null", "None"
    ]
    return st.one_of(
        st.sampled_from(valid),
        st.text(min_size=0, max_size=30)
    )

# Helper: tags array, with edge cases
def _tags_arrays():
    # empty, single, long, null in array, non-string in array
    base = st.lists(
        st.one_of(
            st.text(min_size=0, max_size=15),
            st.integers(min_value=-10, max_value=10).map(str),  # integer as string
            st.just(""),  # empty string
        ),
        min_size=0, max_size=5
    )
    # Sometimes inject a non-string
    weird = st.lists(
        st.one_of(
            st.text(min_size=0, max_size=15),
            st.integers(min_value=-10, max_value=10),
            st.just(None),
            st.just(True),
            st.just(False),
        ),
        min_size=0, max_size=5
    )
    return st.one_of(base, weird)

# Helper: integer id, with edge cases
def _id_values():
    # normal, negative, zero, large, float as int, string as int
    return st.one_of(
        st.integers(min_value=-2, max_value=2**31),
        st.floats(allow_nan=False, allow_infinity=False, width=32).map(int),
        st.text(min_size=1, max_size=10).filter(lambda s: s.isdigit()).map(int)
    )

# Helper: sometimes omit a field (to test missing fields), but only one at a time
def _maybe_omit(field, value, omit):
    if field == omit:
        return None
    return value

# Helper: generate a single record as JSON string
@st.composite
def _record(draw, depth=0, omit_field=None):
    # For divergence, sometimes omit one field (but not at top level)
    fields = ["id", "amount", "name", "status", "tags", "child"]
    # Choose one field to omit, but only at depth > 0, and not always
    omit = omit_field
    if depth == 0 and draw(st.booleans()):
        omit = draw(st.sampled_from(fields))
    elif depth > 0:
        omit = None

    # id
    id_val = draw(_id_values())
    id_json = str(id_val) if _maybe_omit("id", id_val, omit) is not None else None

    # amount
    amount_val = draw(_amount_strings())
    amount_json = _json_escape(amount_val) if _maybe_omit("amount", amount_val, omit) is not None else None

    # name: string or null, but sometimes wrong type (int, bool, array)
    name_choice = draw(st.integers(min_value=0, max_value=4))
    if name_choice == 0:
        name_val = None
        name_json = "null"
    elif name_choice == 1:
        name_val = draw(_name_strings())
        name_json = _json_escape(name_val)
    elif name_choice == 2:
        name_val = draw(st.integers(min_value=-100, max_value=100))
        name_json = str(name_val)
    elif name_choice == 3:
        name_val = draw(st.booleans())
        name_json = "true" if name_val else "false"
    else:
        name_val = draw(st.lists(st.integers(min_value=0, max_value=2), min_size=0, max_size=2))
        name_json = "[" + ",".join(map(str, name_val)) + "]"
    if _maybe_omit("name", name_val, omit) is None:
        name_json = None

    # status: valid, or wrong type, or invalid string
    status_choice = draw(st.integers(min_value=0, max_value=3))
    if status_choice == 0:
        status_val = draw(st.sampled_from(_status_values))
        status_json = _json_escape(status_val)
    elif status_choice == 1:
        status_val = draw(_not_status())
        status_json = _json_escape(status_val)
    elif status_choice == 2:
        status_val = draw(st.integers(min_value=-5, max_value=5))
        status_json = str(status_val)
    else:
        status_val = draw(st.booleans())
        status_json = "true" if status_val else "false"
    if _maybe_omit("status", status_val, omit) is None:
        status_json = None

    # tags: array of strings, or wrong type (int, null, object)
    tags_choice = draw(st.integers(min_value=0, max_value=3))
    if tags_choice == 0:
        tags_val = draw(_tags_arrays())
        tags_json = "[" + ",".join(_json_escape(str(t)) if not isinstance(t, bool) and t is not None else ("true" if t is True else "false" if t is False else "null") for t in tags_val) + "]"
    elif tags_choice == 1:
        tags_val = draw(st.integers(min_value=-10, max_value=10))
        tags_json = str(tags_val)
    elif tags_choice == 2:
        tags_val = None
        tags_json = "null"
    else:
        tags_val = {"foo": "bar"}
        tags_json = '{"foo":"bar"}'
    if _maybe_omit("tags", tags_val, omit) is None:
        tags_json = None

    # child: null, or another record, or wrong type (int, string, array)
    child_choice = draw(st.integers(min_value=0, max_value=4))
    if depth >= 1 or child_choice == 0:
        child_val = None
        child_json = "null"
    elif child_choice == 1:
        child_val = draw(_record(depth=1))
        child_json = child_val.decode("utf-8")
    elif child_choice == 2:
        child_val = draw(st.integers(min_value=-10, max_value=10))
        child_json = str(child_val)
    elif child_choice == 3:
        child_val = draw(st.text(min_size=0, max_size=10))
        child_json = _json_escape(child_val)
    else:
        arr = draw(st.lists(st.integers(min_value=0, max_value=2), min_size=0, max_size=2))
        child_val = arr
        child_json = "[" + ",".join(map(str, arr)) + "]"
    if _maybe_omit("child", child_val, omit) is None:
        child_json = None

    # Compose fields, skipping omitted
    field_items = []
    if id_json is not None:
        field_items.append('"id":' + id_json)
    if amount_json is not None:
        field_items.append('"amount":' + amount_json)
    if name_json is not None:
        field_items.append('"name":' + name_json)
    if status_json is not None:
        field_items.append('"status":' + status_json)
    if tags_json is not None:
        field_items.append('"tags":' + tags_json)
    if child_json is not None:
        field_items.append('"child":' + child_json)

    json_str = '{' + ','.join(field_items) + '}'
    return json_str.encode("utf-8")

@st.composite
def generated_json(draw):
    return draw(_record())