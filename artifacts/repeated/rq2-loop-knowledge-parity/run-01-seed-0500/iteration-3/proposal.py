from hypothesis import strategies as st

# Constants for fixed sets
STATUS_VALUES = ['active', 'inactive', 'unknown']

# Helper to produce a JSON string literal from a Python string (with escapes)
def json_string_literal(s: str) -> str:
    # Minimal escaping for JSON string literals: backslash and double quote
    # plus control chars replaced by \uXXXX
    def esc_char(c):
        o = ord(c)
        if c == '"':
            return r'\"'
        elif c == '\\':
            return r'\\'
        elif 0x20 <= o <= 0x7E:
            return c
        else:
            return '\\u%04x' % o
    return '"' + ''.join(esc_char(c) for c in s) + '"'

# Compose a JSON array of strings from a Python list of strings
def json_array_of_strings(lst):
    return '[' + ','.join(json_string_literal(s) for s in lst) + ']'

# Compose a JSON object from a dict of key->string values (values are JSON text)
def json_object(d):
    # keys are always strings, no escaping needed for keys here (fixed keys)
    return '{' + ','.join(f'"{k}":{v}' for k, v in d.items()) + '}'

@st.composite
def generated_json(draw) -> bytes:
    # We produce a JSON object with keys:
    # "id": int or double (to trigger divergence)
    # "amount": string (always present)
    # "name": string or null or missing (nullable)
    # "status": one of fixed strings (always present)
    # "tags": array of strings or missing (missing triggers built_value accept vs others reject)
    # "child": null or nested record or missing (nullable)
    #
    # We want to vary one or two fields at a time around borderline cases:
    # - id: int or double (including out-of-64-bit-range large int as double)
    # - tags: present or missing
    # - name: string or null or missing (missing accepted by all)
    # - child: null or nested record or missing (missing accepted by all)
    # - amount: always string (to avoid universal rejection)
    # - status: always valid string (to avoid universal rejection)
    #
    # We do bounded recursion for child, max depth 1 (child.child always null)
    #
    # We produce JSON text as bytes.

    # Strategy for id field:
    # - Either a true int within 64-bit range (accepted by all)
    # - Or a double (float) that json_serializable/freezed accept but manual/built_value reject
    # - Or a large int outside 64-bit range encoded as double (to test saturation)
    #
    # We produce the JSON text for the id field value directly (number literal)
    def id_json_text():
        # Choose one of three cases:
        choice = draw(st.integers(min_value=0, max_value=2))
        if choice == 0:
            # true int in 64-bit range
            v = draw(st.integers(min_value=-(2**63), max_value=2**63-1))
            return str(v)
        elif choice == 1:
            # double with fractional part (e.g. 123.456)
            # This will be accepted by json_serializable/freezed but rejected by manual/built_value
            whole = draw(st.integers(min_value=0, max_value=100000))
            frac = draw(st.integers(min_value=1, max_value=999999))
            s = f"{whole}.{frac}"
            return s
        else:
            # large int outside 64-bit range, encoded as double literal (e.g. 1e20)
            # jsonDecode produces double, toInt() saturates in json_serializable/freezed
            # manual/built_value require int, so reject
            exp = draw(st.integers(min_value=20, max_value=30))
            base = draw(st.integers(min_value=1, max_value=9))
            s = f"{base}e{exp}"
            return s

    # amount: always string, non-empty ascii printable
    amount_str = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E)).filter(lambda x: '"' not in x and '\\' not in x))
    amount_json = json_string_literal(amount_str)

    # name: nullable string or null or missing
    # missing accepted by all, null accepted by all, string accepted by all
    name_choice = draw(st.sampled_from(['present_string', 'present_null', 'missing']))
    if name_choice == 'present_string':
        name_str = draw(st.text(min_size=0, max_size=20, alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E)).filter(lambda x: '"' not in x and '\\' not in x))
        name_json = json_string_literal(name_str)
        name_field = ('name', name_json)
    elif name_choice == 'present_null':
        name_field = ('name', 'null')
    else:
        name_field = None  # missing

    # status: always one of fixed strings
    status_val = draw(st.sampled_from(STATUS_VALUES))
    status_json = json_string_literal(status_val)

    # tags: array of strings or missing
    # missing triggers divergence: built_value accepts with empty list, others reject
    tags_choice = draw(st.sampled_from(['present', 'missing']))
    if tags_choice == 'present':
        # array of 0 to 3 strings (empty array allowed)
        tags_list = draw(st.lists(st.text(min_size=1, max_size=10, alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E)).filter(lambda x: '"' not in x and '\\' not in x), max_size=3))
        tags_json = json_array_of_strings(tags_list)
        tags_field = ('tags', tags_json)
    else:
        tags_field = None  # missing

    # child: null or nested record or missing
    # missing accepted by all, null accepted by all, nested record must be well-formed
    child_choice = draw(st.sampled_from(['present_null', 'present_record', 'missing']))

    # To avoid infinite recursion, child.child is always null or missing (never nested record)
    def child_record_json():
        # id field for child: always int in 64-bit range (to avoid complexity)
        child_id = draw(st.integers(min_value=-(2**63), max_value=2**63-1))
        child_id_json = str(child_id)
        # amount string
        child_amount_str = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E)).filter(lambda x: '"' not in x and '\\' not in x))
        child_amount_json = json_string_literal(child_amount_str)
        # name nullable string or null or missing
        child_name_choice = draw(st.sampled_from(['present_string', 'present_null', 'missing']))
        if child_name_choice == 'present_string':
            child_name_str = draw(st.text(min_size=0, max_size=20, alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E)).filter(lambda x: '"' not in x and '\\' not in x))
            child_name_json = json_string_literal(child_name_str)
            child_name_field = ('name', child_name_json)
        elif child_name_choice == 'present_null':
            child_name_field = ('name', 'null')
        else:
            child_name_field = None
        # status fixed
        child_status_val = draw(st.sampled_from(STATUS_VALUES))
        child_status_json = json_string_literal(child_status_val)
        # tags present or missing (same logic as top-level)
        child_tags_choice = draw(st.sampled_from(['present', 'missing']))
        if child_tags_choice == 'present':
            child_tags_list = draw(st.lists(st.text(min_size=1, max_size=10, alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E)).filter(lambda x: '"' not in x and '\\' not in x), max_size=3))
            child_tags_json = json_array_of_strings(child_tags_list)
            child_tags_field = ('tags', child_tags_json)
        else:
            child_tags_field = None
        # child.child is always null or missing (never nested record)
        child_child_choice = draw(st.sampled_from(['present_null', 'missing']))
        if child_child_choice == 'present_null':
            child_child_field = ('child', 'null')
        else:
            child_child_field = None

        # Compose child object fields
        fields = {
            'id': child_id_json,
            'amount': child_amount_json,
            'status': child_status_json,
        }
        if child_name_field is not None:
            fields[child_name_field[0]] = child_name_field[1]
        if child_tags_field is not None:
            fields[child_tags_field[0]] = child_tags_field[1]
        if child_child_field is not None:
            fields[child_child_field[0]] = child_child_field[1]

        return json_object(fields)

    if child_choice == 'present_null':
        child_field = ('child', 'null')
    elif child_choice == 'present_record':
        child_field = ('child', child_record_json())
    else:
        child_field = None  # missing

    # Compose top-level fields dict
    fields = {
        'id': id_json_text(),
        'amount': amount_json,
        'status': status_json,
    }
    if name_field is not None:
        fields[name_field[0]] = name_field[1]
    if tags_field is not None:
        fields[tags_field[0]] = tags_field[1]
    if child_field is not None:
        fields[child_field[0]] = child_field[1]

    json_text = json_object(fields)
    return json_text.encode('utf-8')