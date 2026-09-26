from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status field
    statuses = st.sampled_from(['"active"', '"inactive"', '"unknown"'])

    # id: integer, but allow also strings or floats to provoke divergence
    id_base = st.integers(min_value=0, max_value=1000)
    id_alt = st.one_of(
        id_base,
        st.floats(allow_infinity=False, allow_nan=False, width=32).filter(lambda f: f.is_integer() and 0 <= f <= 1000),
        st.text(min_size=1, max_size=5).filter(lambda s: s.isdigit())
    )

    # amount: string normally, but allow numbers or null to provoke divergence
    amount_base = st.text(min_size=1, max_size=10).filter(lambda s: all(c in '0123456789.' for c in s))
    amount_alt = st.one_of(
        amount_base,
        st.integers(min_value=0, max_value=100000).map(str),
        st.integers(min_value=0, max_value=100000),
        st.floats(allow_infinity=False, allow_nan=False).map(lambda f: format(f, 'g')),
        st.just("null"),
        st.just("true"),
        st.just("false"),
    )

    # name: string or null, but also allow numbers or booleans as strings (to provoke divergence)
    name_base = st.one_of(
        st.none().map(lambda _: "null"),
        st.text(min_size=0, max_size=10).map(lambda s: '"' + s.replace('"', '\\"') + '"')
    )
    name_alt = st.one_of(
        name_base,
        st.integers(min_value=0, max_value=1000).map(str),
        st.floats(allow_infinity=False, allow_nan=False).map(lambda f: format(f, 'g')),
        st.just("true"),
        st.just("false"),
    )

    # status: one of "active", "inactive", "unknown", but also allow null or other strings
    status_base = statuses
    status_alt = st.one_of(
        status_base,
        st.none().map(lambda _: "null"),
        st.text(min_size=1, max_size=10).filter(lambda s: s not in ['active', 'inactive', 'unknown']).map(lambda s: '"' + s.replace('"', '\\"') + '"'),
        st.integers(min_value=0, max_value=10).map(str),
    )

    # tags: array of strings, but also allow null, empty array, or array with non-string elements
    tag_str = st.text(min_size=0, max_size=5).map(lambda s: '"' + s.replace('"', '\\"') + '"')
    tags_base = st.lists(tag_str, max_size=3).map(lambda lst: '[' + ','.join(lst) + ']')
    tags_alt = st.one_of(
        tags_base,
        st.just("null"),
        st.lists(st.one_of(tag_str, st.integers().map(str), st.just("null")), max_size=3).map(lambda lst: '[' + ','.join(lst) + ']'),
        st.just("[]"),
    )

    # Recursive child: either null or a nested record (one level only)
    # To avoid infinite recursion, child can be null or a record with child=null only
    # We'll build the record as a JSON string here

    # Compose a record JSON string from fields (all strings, no Python dict)
    def make_record(id_s, amount_s, name_s, status_s, tags_s, child_s):
        # id_s, amount_s, name_s, status_s, tags_s, child_s are strings representing JSON values (including quotes if strings)
        return (
            '{'
            + '"id":' + id_s + ','
            + '"amount":' + amount_s + ','
            + '"name":' + name_s + ','
            + '"status":' + status_s + ','
            + '"tags":' + tags_s + ','
            + '"child":' + child_s
            + '}'
        )

    # Draw fields for child record (child's child is always null)
    def draw_child():
        id_c = draw(id_alt).map(str) if hasattr(draw(id_alt), 'map') else str(draw(id_alt))
        # id_alt can be int, float, or string digits, so convert to string representation
        id_c_val = draw(id_alt)
        if isinstance(id_c_val, int):
            id_c = str(id_c_val)
        elif isinstance(id_c_val, float):
            # Represent floats as JSON numbers
            id_c = format(id_c_val, 'g')
        else:
            # string digits or other string
            id_c = '"' + str(id_c_val).replace('"', '\\"') + '"'

        amount_c_val = draw(amount_alt)
        if isinstance(amount_c_val, (int, float)):
            amount_c = format(amount_c_val, 'g')
        else:
            amount_c = amount_c_val if amount_c_val in ['null', 'true', 'false'] else '"' + amount_c_val.replace('"', '\\"') + '"'

        name_c_val = draw(name_alt)
        if name_c_val in ['null', 'true', 'false']:
            name_c = name_c_val
        elif isinstance(name_c_val, (int, float)):
            name_c = format(name_c_val, 'g')
        else:
            name_c = '"' + str(name_c_val).replace('"', '\\"') + '"'

        status_c_val = draw(status_alt)
        if status_c_val in ['null', 'true', 'false']:
            status_c = status_c_val
        elif status_c_val.startswith('"') and status_c_val.endswith('"'):
            status_c = status_c_val
        else:
            status_c = '"' + str(status_c_val).replace('"', '\\"') + '"'

        tags_c = draw(tags_alt)

        child_c = "null"

        return make_record(id_c, amount_c, name_c, status_c, tags_c, child_c)

    # Draw top-level fields
    id_val = draw(id_alt)
    if isinstance(id_val, int):
        id_s = str(id_val)
    elif isinstance(id_val, float):
        id_s = format(id_val, 'g')
    else:
        id_s = '"' + str(id_val).replace('"', '\\"') + '"'

    amount_val = draw(amount_alt)
    if isinstance(amount_val, (int, float)):
        amount_s = format(amount_val, 'g')
    else:
        amount_s = amount_val if amount_val in ['null', 'true', 'false'] else '"' + amount_val.replace('"', '\\"') + '"'

    name_val = draw(name_alt)
    if name_val in ['null', 'true', 'false']:
        name_s = name_val
    elif isinstance(name_val, (int, float)):
        name_s = format(name_val, 'g')
    else:
        name_s = '"' + str(name_val).replace('"', '\\"') + '"'

    status_val = draw(status_alt)
    if status_val in ['null', 'true', 'false']:
        status_s = status_val
    elif status_val.startswith('"') and status_val.endswith('"'):
        status_s = status_val
    else:
        status_s = '"' + str(status_val).replace('"', '\\"') + '"'

    tags_s = draw(tags_alt)

    # child: null or nested record (one level)
    child_choice = draw(st.booleans())
    if child_choice:
        child_s = draw_child()
    else:
        child_s = "null"

    json_text = make_record(id_s, amount_s, name_s, status_s, tags_s, child_s)

    return json_text.encode('utf-8')