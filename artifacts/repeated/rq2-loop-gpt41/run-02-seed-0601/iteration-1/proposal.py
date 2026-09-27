from hypothesis import strategies as st

# Helper: JSON-escaped string
def json_escape(s):
    # Minimal escaping for control chars, backslash, and double quote
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"').replace('\b', '\\b').replace('\f', '\\f').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t') + '"'

# Helper: JSON array of strings
def json_string_array(draw, min_size=0, max_size=5):
    # Sometimes empty, sometimes with duplicates, sometimes with nulls or numbers (boundary)
    # But mostly valid
    base = draw(
        st.lists(
            st.one_of(
                st.text(min_size=0, max_size=10).map(json_escape),
                st.just('null'),  # provoke type confusion
                st.integers(-1, 1).map(str),  # provoke type confusion
            ),
            min_size=min_size,
            max_size=max_size,
        )
    )
    return '[' + ', '.join(base) + ']'

# Helper: status field
status_values = [
    '"active"',
    '"inactive"',
    '"unknown"',
    'null',  # provoke type confusion
    '42',    # provoke type confusion
    '""',    # empty string
]

# Helper: amount field
def amount_strategy():
    # Mostly valid, sometimes boundary/invalid
    return st.one_of(
        st.text(min_size=0, max_size=12).map(json_escape),  # valid
        st.integers(-1, 1).map(str),  # provoke type confusion
        st.just('null'),  # provoke type confusion
        st.just('""'),    # empty string
    )

# Helper: name field
def name_strategy():
    # Sometimes null, sometimes string, sometimes wrong type
    return st.one_of(
        st.text(min_size=0, max_size=12).map(json_escape),
        st.just('null'),
        st.integers(-1, 1).map(str),  # provoke type confusion
        st.just('""'),                # empty string
    )

# Helper: id field
def id_strategy():
    # Mostly integer, sometimes string or null
    return st.one_of(
        st.integers(-2, 2).map(str),
        st.text(min_size=0, max_size=6).map(json_escape),  # provoke type confusion
        st.just('null'),  # provoke type confusion
    )

# Helper: child field (recursive)
def child_strategy(draw, depth):
    if depth <= 0:
        # Only null or empty object at max depth
        return draw(st.sampled_from(['null', '{}']))
    # 80% chance: null, 20%: nested record
    if draw(st.booleans()):
        return 'null'
    else:
        return draw(record_strategy(depth=depth-1))

# Main record strategy
def record_strategy(depth=1):
    @st.composite
    def _record(draw):
        # For each field, sometimes use valid, sometimes boundary/invalid
        id_val = draw(id_strategy())
        amount_val = draw(amount_strategy())
        name_val = draw(name_strategy())
        status_val = draw(st.sampled_from(status_values))
        tags_val = json_string_array(draw)
        child_val = child_strategy(draw, depth)
        # Randomize field order to provoke order-sensitivity bugs
        fields = [
            ('"id"', id_val),
            ('"amount"', amount_val),
            ('"name"', name_val),
            ('"status"', status_val),
            ('"tags"', tags_val),
            ('"child"', child_val),
        ]
        # Sometimes drop a field (provoke missing-field bugs)
        if draw(st.booleans()):
            drop_idx = draw(st.integers(min_value=0, max_value=5))
            fields = [f for i, f in enumerate(fields) if i != drop_idx]
        # Shuffle order
        draw(st.permutations(fields))
        # Compose object
        obj = '{' + ', '.join(f'{k}: {v}' for k, v in fields) + '}'
        return obj
    return _record()

@st.composite
def generated_json(draw):
    # Top-level record, depth=1 or 2
    obj = draw(record_strategy(depth=draw(st.integers(min_value=1, max_value=2))))
    # Ensure bytes output
    return obj.encode('utf-8')