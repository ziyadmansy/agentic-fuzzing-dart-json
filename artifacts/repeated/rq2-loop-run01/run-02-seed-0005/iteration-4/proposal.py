from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for fixed fields
    statuses = st.sampled_from(["active", "inactive", "unknown"])
    # id: integer, but allow some edge cases as strings or floats to provoke divergence
    # amount: string, but sometimes numeric strings, sometimes non-numeric strings, sometimes empty
    # name: string or null, but also sometimes a number or boolean to provoke divergence
    # tags: array of strings, but sometimes empty, sometimes with null or numbers to provoke divergence
    # child: either null or a nested record (one level only)
    
    # Strategy for id field: mostly int, but sometimes string or float as string
    id_int = st.integers(min_value=0, max_value=2**31-1)
    id_str = id_int.map(str)
    id_float_str = st.floats(allow_infinity=False, allow_nan=False, width=32).map(lambda f: format(f, '.6g'))
    id_field = st.one_of(id_int, id_str, id_float_str)
    
    # amount field: string, but sometimes numeric string, sometimes empty, sometimes weird strings
    amount_numeric_str = st.one_of(
        st.integers(min_value=0, max_value=10**9).map(str),
        st.floats(allow_infinity=False, allow_nan=False).map(lambda f: format(f, '.6g')),
    )
    amount_weird_str = st.sampled_from(["", "0", "-0", "NaN", "Infinity", "-Infinity", "123abc", " 42 ", "0x10"])
    amount_field = st.one_of(amount_numeric_str, amount_weird_str)
    
    # name field: string or null, but sometimes number or boolean or empty string
    name_str = st.text(min_size=0, max_size=20)
    name_null = st.just(None)
    name_number = st.one_of(st.integers(), st.floats(allow_infinity=False, allow_nan=False))
    name_bool = st.booleans()
    name_field = st.one_of(name_str, name_null, name_number, name_bool)
    
    # status field: one of the three strings, but sometimes null or wrong string
    status_valid = statuses
    status_invalid_str = st.text(min_size=1, max_size=10).filter(lambda s: s not in {"active","inactive","unknown"})
    status_null = st.just(None)
    status_field = st.one_of(status_valid, status_invalid_str, status_null)
    
    # tags field: array of strings, but sometimes empty, sometimes with null or numbers
    tag_str = st.text(min_size=1, max_size=10)
    tag_null = st.just(None)
    tag_number = st.integers(min_value=-100, max_value=100)
    tags_element = st.one_of(tag_str, tag_null, tag_number)
    tags_field = st.lists(tags_element, max_size=5)
    
    # Recursive child field: either null or a nested record (one level only)
    # To avoid infinite recursion, child record fields are simpler: only valid types or nulls
    def child_record():
        # child record fields: id int only, amount string only, name string or null only,
        # status valid only, tags array of strings only, child null only
        id_c = st.integers(min_value=0, max_value=2**31-1)
        amount_c = st.text(min_size=0, max_size=20)
        name_c = st.one_of(st.text(min_size=0, max_size=20), st.just(None))
        status_c = statuses
        tags_c = st.lists(st.text(min_size=1, max_size=10), max_size=3)
        child_c = st.just(None)
        return st.fixed_dictionaries({
            "id": id_c,
            "amount": amount_c,
            "name": name_c,
            "status": status_c,
            "tags": tags_c,
            "child": child_c,
        })
    
    child_field = st.one_of(st.just(None), child_record())
    
    # Compose the full record dictionary with all fields
    record = st.fixed_dictionaries({
        "id": id_field,
        "amount": amount_field,
        "name": name_field,
        "status": status_field,
        "tags": tags_field,
        "child": child_field,
    })
    
    # Now build JSON text manually from the drawn record
    def json_escape_str(s: str) -> str:
        # Minimal JSON string escaping for quotes and backslashes and control chars
        # Hypothesis text can contain any unicode, so escape quotes, backslash, and control chars
        def esc_char(c):
            o = ord(c)
            if c == '"':
                return '\\"'
            elif c == '\\':
                return '\\\\'
            elif c == '\b':
                return '\\b'
            elif c == '\f':
                return '\\f'
            elif c == '\n':
                return '\\n'
            elif c == '\r':
                return '\\r'
            elif c == '\t':
                return '\\t'
            elif o < 0x20:
                return '\\u%04x' % o
            else:
                return c
        return '"' + ''.join(esc_char(c) for c in s) + '"'
    
    def to_json_value(v):
        if v is None:
            return "null"
        elif isinstance(v, bool):
            return "true" if v else "false"
        elif isinstance(v, int):
            return str(v)
        elif isinstance(v, float):
            # JSON floats: use repr but ensure no trailing .0 for ints
            # Use format with 'g' to avoid scientific notation for small numbers
            s = format(v, '.15g')
            if s == "nan" or s == "inf" or s == "-inf":
                # JSON does not support these, but we keep as string to provoke divergence
                return json_escape_str(s)
            return s
        elif isinstance(v, str):
            return json_escape_str(v)
        elif isinstance(v, list):
            return "[" + ",".join(to_json_value(e) for e in v) + "]"
        elif isinstance(v, dict):
            items = []
            for k, val in v.items():
                items.append(json_escape_str(k) + ":" + to_json_value(val))
            return "{" + ",".join(items) + "}"
        else:
            # fallback: convert to string escaped
            return json_escape_str(str(v))
    
    d = draw(record)
    json_text = to_json_value(d)
    return json_text.encode("utf-8")