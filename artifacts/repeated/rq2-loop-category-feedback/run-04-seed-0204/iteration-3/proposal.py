from hypothesis import strategies as st

# Helper to escape JSON string content minimally for this context
def json_string_escape(s: str) -> str:
    # Escape backslash and double quote, and control chars minimally
    # Hypothesis strings won't contain control chars by default, but be safe
    s = s.replace('\\', '\\\\').replace('"', '\\"')
    # Replace control chars with \uXXXX escapes
    def esc_char(c):
        o = ord(c)
        if o < 0x20:
            return '\\u%04x' % o
        return c
    return ''.join(esc_char(c) for c in s)

@st.composite
def generated_json(draw) -> bytes:
    # Constants
    STATUS_VALUES = ['active', 'inactive', 'unknown']
    # Weights for null_override category (highest scoring last iteration)
    # We'll produce some null_override on normally non-nullable fields (id, amount, status)
    # Also produce some bad_enum, boundary_id, extra_key, deep_nesting, but keep mostly valid

    # id: integer near 53-bit boundary or normal int, or null (null_override)
    id_normal = st.integers(min_value=0, max_value=2**53-1)
    id_boundary = st.sampled_from([2**53-1, 2**53, 2**53+1, 2**63-1, 2**63, 2**63+1])
    id_null_override = st.just(None)
    id_choice = draw(st.one_of(id_normal, id_boundary, id_null_override))

    # amount: string normally required, but sometimes null_override or wrong_type (number)
    amount_str = st.text(min_size=1, max_size=20).map(json_string_escape)
    amount_null_override = st.just(None)
    amount_wrong_type = st.integers(min_value=0, max_value=1000000).map(str)  # as string but numeric string is valid
    amount_choice = draw(st.one_of(amount_str, amount_null_override))

    # name: string or null normally, also test empty string and unicode
    name_str = st.one_of(
        st.none(),
        st.text(min_size=0, max_size=30).map(json_string_escape)
    )
    name_choice = draw(name_str)

    # status: enum normally, but sometimes bad_enum or null_override
    status_good = st.sampled_from(STATUS_VALUES)
    status_bad_enum = st.text(min_size=1, max_size=10).filter(lambda s: s not in STATUS_VALUES)
    status_null_override = st.just(None)
    status_choice = draw(st.one_of(status_good, status_bad_enum, status_null_override))

    # tags: array of strings, sometimes empty, sometimes with null or wrong_type inside
    tag_str = st.text(min_size=1, max_size=10).map(json_string_escape)
    tag_null = st.just(None)
    tag_wrong_type = st.integers(min_value=0, max_value=1000)
    tag_element = draw(st.one_of(tag_str, tag_null, tag_wrong_type.map(str)))
    # tags array length 0-3 for bounded size
    tags_len = draw(st.integers(min_value=0, max_value=3))
    tags_list = []
    for _ in range(tags_len):
        # Mix normal strings and occasionally null_override or wrong_type as string
        t = draw(st.one_of(tag_str, tag_null, tag_wrong_type.map(str)))
        tags_list.append(t)
    # Build tags JSON array string
    tags_json = '[' + ','.join('null' if t is None else ('"%s"' % t) for t in tags_list) + ']'

    # child: null or one-level recursion (no deeper than 1)
    # To keep bounded recursion, child can be null or a record with child=null
    # We'll produce child with similar fields but no further recursion
    child_null = st.just('null')
    # child record fields similar but child=null
    def child_record():
        # id for child: normal int or null_override
        cid = draw(st.one_of(id_normal, id_null_override))
        # amount string or null_override
        camount = draw(st.one_of(amount_str, amount_null_override))
        # name string or null
        cname = draw(name_str)
        # status enum or bad_enum or null_override
        cstatus = draw(st.one_of(status_good, status_bad_enum, status_null_override))
        # tags array as above but smaller length 0-2
        ctags_len = draw(st.integers(min_value=0, max_value=2))
        ctags_list = []
        for _ in range(ctags_len):
            t = draw(st.one_of(tag_str, tag_null, tag_wrong_type.map(str)))
            ctags_list.append(t)
        ctags_json = '[' + ','.join('null' if t is None else ('"%s"' % t) for t in ctags_list) + ']'
        # child=null always here
        # Compose child JSON string
        parts = []
        # id
        if cid is None:
            parts.append('"id":null')
        else:
            parts.append(f'"id":{cid}')
        # amount
        if camount is None:
            parts.append('"amount":null')
        else:
            parts.append(f'"amount":"{camount}"')
        # name
        if cname is None:
            parts.append('"name":null')
        else:
            parts.append(f'"name":"{cname}"')
        # status
        if cstatus is None:
            parts.append('"status":null')
        else:
            parts.append(f'"status":"{cstatus}"')
        # tags
        parts.append(f'"tags":{ctags_json}')
        # child
        parts.append('"child":null')
        return '{' + ','.join(parts) + '}'

    child_choice = draw(st.one_of(child_null, st.deferred(child_record)))

    # Compose top-level JSON object string
    parts = []
    # id
    if id_choice is None:
        parts.append('"id":null')
    else:
        parts.append(f'"id":{id_choice}')
    # amount
    if amount_choice is None:
        parts.append('"amount":null')
    else:
        parts.append(f'"amount":"{amount_choice}"')
    # name
    if name_choice is None:
        parts.append('"name":null')
    else:
        parts.append(f'"name":"{name_choice}"')
    # status
    if status_choice is None:
        parts.append('"status":null')
    else:
        parts.append(f'"status":"{status_choice}"')
    # tags
    parts.append(f'"tags":{tags_json}')
    # child
    parts.append(f'"child":{child_choice}')

    # Occasionally add an extra unexpected key (extra_key category)
    add_extra_key = draw(st.booleans())
    if add_extra_key:
        # extra key with string or null or number
        extra_key_name = draw(st.text(min_size=1, max_size=10).filter(lambda s: s not in ["id","amount","name","status","tags","child"]).map(json_string_escape))
        extra_key_value = draw(st.one_of(
            st.none().map(lambda _: 'null'),
            st.text(min_size=0, max_size=20).map(lambda s: '"' + json_string_escape(s) + '"'),
            st.integers(min_value=0, max_value=100000).map(str)
        ))
        parts.append(f'"{extra_key_name}":{extra_key_value}')

    json_text = '{' + ','.join(parts) + '}'
    return json_text.encode('utf-8')