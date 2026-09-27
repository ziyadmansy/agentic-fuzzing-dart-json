from hypothesis import strategies as st

# Helper: JSON-escaped string
def json_escape(s):
    # Minimal escaping for ASCII and common control chars
    return '"' + (
        s.replace('\\', '\\\\')
         .replace('"', '\\"')
         .replace('\b', '\\b')
         .replace('\f', '\\f')
         .replace('\n', '\\n')
         .replace('\r', '\\r')
         .replace('\t', '\\t')
    ) + '"'

# Helper: JSON-encode a list of strings
def json_array_of_strings(strings):
    return '[' + ','.join(json_escape(s) for s in strings) + ']'

# Helper: JSON-encode a field (name, value)
def json_field(name, value):
    return json_escape(name) + ':' + value

# Helper: JSON-encode a full object from fields
def json_object(fields):
    return '{' + ','.join(fields) + '}'

# Main strategy
@st.composite
def generated_json(draw):
    # Recursion limit: only one level of child nesting
    def record_strategy(recursion_allowed):
        # id: integer, but try some edge cases
        id_strategy = st.one_of(
            st.integers(min_value=-2**31, max_value=2**31-1),  # normal
            st.just(0),
            st.just(-1),
            st.just(2**31-1),
            st.just(-2**31),
            # Wrong type: string, float, bool, null
            st.sampled_from(['"123"', '123.0', 'true', 'null'])
        ).map(lambda v: str(v) if isinstance(v, int) else v)

        # amount: string, but try numbers, null, bool
        amount_strategy = st.one_of(
            st.text(min_size=0, max_size=12).map(json_escape),
            st.integers(min_value=-9999, max_value=9999).map(str),
            st.just('null'),
            st.just('true'),
            st.just('false'),
        )

        # name: string or null, but try numbers, bool, missing
        name_strategy = st.one_of(
            st.text(min_size=0, max_size=12).map(json_escape),
            st.just('null'),
            st.integers(min_value=-9999, max_value=9999).map(str),
            st.just('true'),
            st.just('false'),
        )

        # status: valid enum, but try wrong string, int, null, bool
        status_strategy = st.one_of(
            st.sampled_from(['"active"', '"inactive"', '"unknown"']),
            st.text(min_size=1, max_size=8).filter(lambda s: s not in ['active', 'inactive', 'unknown']).map(json_escape),
            st.integers(min_value=-5, max_value=5).map(str),
            st.just('null'),
            st.just('true'),
            st.just('false'),
        )

        # tags: array of strings, but try array of numbers, null, bool, string, empty array
        tags_strategy = st.one_of(
            st.lists(st.text(min_size=0, max_size=8), min_size=0, max_size=4).map(json_array_of_strings),
            st.lists(st.integers(min_value=-5, max_value=5), min_size=0, max_size=4).map(lambda l: '[' + ','.join(map(str, l)) + ']'),
            st.just('null'),
            st.just('true'),
            st.just('false'),
            st.text(min_size=0, max_size=12).map(json_escape),
            st.just('[]'),
        )

        # child: null or nested record, but try wrong types, empty object, array
        if recursion_allowed:
            child_strategy = st.one_of(
                st.just('null'),
                st.deferred(lambda: record_strategy(False)).map(lambda s: s),
                st.just('{}'),
                st.just('[]'),
                st.just('true'),
                st.just('false'),
                st.integers(min_value=-5, max_value=5).map(str),
                st.text(min_size=0, max_size=8).map(json_escape),
            )
        else:
            child_strategy = st.one_of(
                st.just('null'),
                st.just('{}'),
                st.just('[]'),
                st.just('true'),
                st.just('false'),
                st.integers(min_value=-5, max_value=5).map(str),
                st.text(min_size=0, max_size=8).map(json_escape),
            )

        # Field order: randomize to catch order sensitivity
        field_names = ['id', 'amount', 'name', 'status', 'tags', 'child']
        draw_fields = draw(st.permutations(field_names))

        # For each field, draw value
        field_values = {}
        field_values['id'] = draw(id_strategy)
        field_values['amount'] = draw(amount_strategy)
        field_values['name'] = draw(name_strategy)
        field_values['status'] = draw(status_strategy)
        field_values['tags'] = draw(tags_strategy)
        field_values['child'] = draw(child_strategy)

        # Occasionally drop a field (simulate missing field vs null)
        missing_field = draw(st.sampled_from(field_names + [None]))
        fields = []
        for fname in draw_fields:
            if fname == missing_field:
                continue
            fields.append(json_field(fname, field_values[fname]))

        # Occasionally add an unknown field
        if draw(st.booleans()):
            fields.append(json_field('extra_' + draw(st.text(min_size=1, max_size=5, alphabet='abcdefghijklmnopqrstuvwxyz')), draw(st.text(min_size=0, max_size=8).map(json_escape))))

        return json_object(fields)

    # Top-level record, always allow recursion for child
    json_doc = record_strategy(recursion_allowed=True)
    # Output as bytes
    return draw(json_doc).encode('utf-8')