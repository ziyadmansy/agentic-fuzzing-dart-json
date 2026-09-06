from hypothesis import strategies as st

# Constants for enum values
STATUS_VALUES = ['active', 'inactive', 'unknown']

# Helper to produce JSON string literal with proper escaping of quotes and backslashes
def json_string_literal(s: str) -> str:
    # Minimal escaping for JSON strings: backslash and double quote
    # Hypothesis strings can contain any unicode, but we keep it simple here
    # Replace backslash first, then double quote
    s = s.replace('\\', '\\\\').replace('"', '\\"')
    return '"' + s + '"'

@st.composite
def generated_json(draw) -> bytes:
    # Strategy for id near boundaries: normal int, or near 2**53, 2**64 boundaries
    boundary_ids = [
        0,
        1,
        2**53 - 1,
        2**53,
        2**53 + 1,
        2**64 - 1,
        2**64,
        2**64 + 1,
        -1,
        -2**53,
        -2**64,
    ]
    # 70% chance normal int in range, 30% chance boundary id
    use_boundary = draw(st.booleans())
    if use_boundary:
        id_val = draw(st.sampled_from(boundary_ids))
    else:
        id_val = draw(st.integers(min_value=-2**63, max_value=2**63-1))

    # amount: string, but try normal decimal strings, or weird strings that look numeric but with spaces, signs, or empty
    # 80% normal decimal string, 20% weird strings
    if draw(st.booleans()):
        # normal decimal string, possibly negative, possibly decimal point
        sign = draw(st.sampled_from(['', '-', '+']))
        int_part = draw(st.integers(min_value=0, max_value=10**10)).__str__()
        frac_part = draw(st.one_of(st.just(''), st.floats(min_value=0, max_value=1).map(lambda f: f'{f:.8f}'.split('.')[1])))
        if frac_part:
            amount_str = sign + int_part + '.' + frac_part
        else:
            amount_str = sign + int_part
    else:
        # weird strings: empty, spaces, scientific notation, or non-numeric
        weird = draw(st.sampled_from(['', ' ', '  ', 'NaN', 'inf', '-inf', '1e10', '+1e-10', '0x10', 'ten']))
        amount_str = weird

    # name: string or null, with 70% chance string, 30% null
    if draw(st.booleans()):
        # string: sometimes empty, sometimes unicode, sometimes with quotes or backslashes
        raw_name = draw(st.text(min_size=0, max_size=20))
        name_val = raw_name
    else:
        name_val = None

    # status: mostly valid enum, sometimes bad enum string, sometimes null (null_override)
    status_choice = draw(st.integers(min_value=0, max_value=9))
    if status_choice <= 6:
        # valid enum
        status_val = draw(st.sampled_from(STATUS_VALUES))
    elif status_choice == 7:
        # bad enum string
        status_val = draw(st.text(min_size=1, max_size=10).filter(lambda s: s not in STATUS_VALUES))
    elif status_choice == 8:
        # null override (normally not allowed)
        status_val = None
    else:
        # number instead of string
        status_val = draw(st.integers(min_value=-10, max_value=10))

    # tags: array of strings, sometimes empty, sometimes with null inside (wrong_type)
    # length 0 to 5
    tags_len = draw(st.integers(min_value=0, max_value=5))
    tags_list = []
    for _ in range(tags_len):
        # 80% string, 20% null
        if draw(st.booleans()):
            tag_str = draw(st.text(min_size=0, max_size=10))
            tags_list.append(tag_str)
        else:
            tags_list.append(None)

    # child: null or one level of recursion (no deeper)
    # To avoid deep nesting, child.child is always null
    # child can be null or a record with child=null
    child_present = draw(st.booleans())
    if not child_present:
        child_val = None
    else:
        # child record fields, but less variation to keep complexity down
        # id near boundaries or normal
        child_id = draw(st.one_of(
            st.sampled_from(boundary_ids),
            st.integers(min_value=-2**63, max_value=2**63-1)
        ))
        # amount string normal decimal or weird
        if draw(st.booleans()):
            sign = draw(st.sampled_from(['', '-', '+']))
            int_part = draw(st.integers(min_value=0, max_value=10**6)).__str__()
            frac_part = draw(st.one_of(st.just(''), st.floats(min_value=0, max_value=1).map(lambda f: f'{f:.8f}'.split('.')[1])))
            if frac_part:
                child_amount = sign + int_part + '.' + frac_part
            else:
                child_amount = sign + int_part
        else:
            child_amount = draw(st.sampled_from(['', 'NaN', 'inf', '-inf', '1e10']))

        # name string or null
        if draw(st.booleans()):
            child_name = draw(st.text(min_size=0, max_size=10))
        else:
            child_name = None

        # status valid enum or bad enum or null override or wrong type
        sc = draw(st.integers(min_value=0, max_value=9))
        if sc <= 6:
            child_status = draw(st.sampled_from(STATUS_VALUES))
        elif sc == 7:
            child_status = draw(st.text(min_size=1, max_size=10).filter(lambda s: s not in STATUS_VALUES))
        elif sc == 8:
            child_status = None
        else:
            child_status = draw(st.integers(min_value=-10, max_value=10))

        # tags array of strings or nulls, length 0-3
        child_tags_len = draw(st.integers(min_value=0, max_value=3))
        child_tags = []
        for _ in range(child_tags_len):
            if draw(st.booleans()):
                child_tags.append(draw(st.text(min_size=0, max_size=10)))
            else:
                child_tags.append(None)

        # child.child always null to avoid deep nesting
        child_child = None

        # Build child JSON text
        # Compose tags array text
        def json_array_of_strings_or_nulls(arr):
            elems = []
            for v in arr:
                if v is None:
                    elems.append('null')
                else:
                    elems.append(json_string_literal(v))
            return '[' + ','.join(elems) + ']'

        child_json = (
            '{'
            + '"id":' + str(child_id)
            + ',"amount":' + json_string_literal(child_amount)
            + ',"name":' + ('null' if child_name is None else json_string_literal(child_name))
            + ',"status":' + (
                'null' if child_status is None else
                (json_string_literal(child_status) if isinstance(child_status, str) else str(child_status))
            )
            + ',"tags":' + json_array_of_strings_or_nulls(child_tags)
            + ',"child":null'
            + '}'
        )
        child_val = child_json

    # Compose tags array text for top-level
    def json_array_of_strings_or_nulls(arr):
        elems = []
        for v in arr:
            if v is None:
                elems.append('null')
            else:
                elems.append(json_string_literal(v))
        return '[' + ','.join(elems) + ']'

    # Compose top-level JSON text
    # status field: if None, output null; if string, output quoted; else output as is (number)
    status_text = (
        'null' if status_val is None else
        (json_string_literal(status_val) if isinstance(status_val, str) else str(status_val))
    )

    # child_val is either None or JSON text string (already serialized)
    child_text = 'null' if child_val is None else child_val

    # name field
    name_text = 'null' if name_val is None else json_string_literal(name_val)

    json_text = (
        '{'
        + '"id":' + str(id_val)
        + ',"amount":' + json_string_literal(amount_str)
        + ',"name":' + name_text
        + ',"status":' + status_text
        + ',"tags":' + json_array_of_strings_or_nulls(tags_list)
        + ',"child":' + child_text
        + '}'
    )

    return json_text.encode('utf-8')