from hypothesis import strategies as st

# Helper: JSON-escape a string (minimal, covers common cases)
def _json_escape(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"').replace('\b', '\\b').replace('\f', '\\f').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t') + '"'

# Helper: generate a valid status value, or a near-miss (e.g. wrong case, extra whitespace, etc.)
_status_values = [
    '"active"', '"inactive"', '"unknown"',
    '"Active"', '"INACTIVE"', '"unknown "', '" active"', '"inactive\n"', '"unknown\t"',
    '42', 'null', 'true', 'false', '""'
]

# Helper: generate a string or a near-miss (number, bool, null, empty array, etc.)
def _maybe_string():
    return st.one_of(
        st.text(min_size=0, max_size=16).map(_json_escape),
        st.integers(-10, 10).map(str),
        st.booleans().map(lambda b: "true" if b else "false"),
        st.just("null"),
        st.just("[]"),
        st.just("{}"),
    )

# Helper: generate a string array, or a near-miss (array of numbers, nulls, mixed types, etc.)
def _maybe_string_array():
    # Mostly valid arrays, sometimes with a twist
    valid = st.lists(st.text(min_size=0, max_size=8).map(_json_escape), min_size=0, max_size=4)
    # Some arrays with wrong types
    near_miss = st.one_of(
        st.lists(st.integers(-5, 5).map(str), min_size=1, max_size=3),
        st.lists(st.just("null"), min_size=1, max_size=2),
        st.lists(st.just("true"), min_size=1, max_size=2),
        st.lists(st.text(min_size=0, max_size=8).map(_json_escape) | st.integers(-5, 5).map(str), min_size=1, max_size=3),
        st.just("null"),
        st.just("42"),
        st.just("true"),
        st.just("false"),
        st.just("{}"),
        st.just(""),
    )
    return st.one_of(
        valid.map(lambda items: "[" + ", ".join(items) + "]"),
        near_miss,
    )

# Helper: generate a child record or null, or a near-miss (wrong type, empty object, etc.)
def _maybe_child(rec):
    return st.one_of(
        rec,
        st.just("null"),
        st.just("42"),
        st.just("true"),
        st.just("false"),
        st.just("[]"),
        st.just("{}"),
        st.just("\"not an object\""),
    )

@st.composite
def generated_json(draw, max_depth=1):
    # Recursion: only one level of child allowed
    def record(depth):
        # id: integer, or a near-miss (string, float, null, bool)
        id_field = draw(st.one_of(
            st.integers(-100, 100).map(str),
            st.text(min_size=0, max_size=8).map(_json_escape),
            st.floats(allow_nan=False, allow_infinity=False, width=32).map(str),
            st.just("null"),
            st.just("true"),
            st.just("false"),
        ))

        # amount: string, or a near-miss (number, null, bool, empty array/object)
        amount_field = draw(_maybe_string())

        # name: string or null, or a near-miss (number, bool, array, object)
        name_field = draw(st.one_of(
            st.text(min_size=0, max_size=12).map(_json_escape),
            st.just("null"),
            st.integers(-10, 10).map(str),
            st.just("true"),
            st.just("false"),
            st.just("[]"),
            st.just("{}"),
        ))

        # status: valid or near-miss
        status_field = draw(st.sampled_from(_status_values))

        # tags: array of strings, or a near-miss
        tags_field = draw(_maybe_string_array())

        # child: another record or null or near-miss
        if depth < max_depth:
            child_field = draw(_maybe_child(st.deferred(lambda: record(depth + 1))))
        else:
            child_field = draw(st.sampled_from(["null", "42", "true", "false", "[]", "{}", "\"not an object\""]))

        # Compose the JSON object
        fields = [
            f'"id": {id_field}',
            f'"amount": {amount_field}',
            f'"name": {name_field}',
            f'"status": {status_field}',
            f'"tags": {tags_field}',
            f'"child": {child_field}',
        ]
        return "{" + ", ".join(fields) + "}"

    # Top-level record
    json_str = record(0)
    return json_str.encode("utf-8")