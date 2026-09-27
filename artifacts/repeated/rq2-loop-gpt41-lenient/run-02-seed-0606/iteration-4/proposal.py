from hypothesis import strategies as st

# Helper strategies for field values
status_values = st.sampled_from(['active', 'inactive', 'unknown'])

# Some edge cases for amount (string field)
amount_edge_cases = st.sampled_from([
    "0", "-0", "00", "1e10", "-1e10", "NaN", "Infinity", "-Infinity", "", " ", "1.0", "1.00", "1,000", "1_000"
])

# Some edge cases for name (string or null)
name_edge_cases = st.one_of(
    st.none(),
    st.just(""),
    st.just(" "),
    st.just("null"),
    st.just("None"),
    st.text(min_size=1, max_size=10)
)

# Some edge cases for tags (array of strings)
tags_edge_cases = st.one_of(
    st.lists(st.text(min_size=0, max_size=5), min_size=0, max_size=0),  # empty list
    st.lists(st.text(min_size=0, max_size=5), min_size=1, max_size=3),
    st.just([""]),
    st.just([" ", ""]),
    st.just(["null"]),
    st.just(["None"]),
    st.just(["a", "a", "a"]),  # repeated
    st.just(["a", "b", "c"]),
)

# Some edge cases for id (integer)
id_edge_cases = st.one_of(
    st.integers(min_value=0, max_value=2),
    st.integers(min_value=-1, max_value=-1),
    st.integers(min_value=2**31-2, max_value=2**31-1),
    st.just(0),
    st.just(-1),
    st.just(1),
)

# Helper to maybe make a field "wrong" in a subtle way
def maybe_wrong(draw, correct, wrongs):
    # 80% correct, 20% wrong
    if draw(st.integers(0, 4)) == 0:
        return draw(wrongs)
    return draw(correct)

# Recursion for child field
@st.composite
def record(draw, depth=0):
    # id: integer (sometimes as string)
    id_val = maybe_wrong(
        draw,
        correct=id_edge_cases,
        wrongs=st.one_of(
            st.text(min_size=1, max_size=5).filter(lambda s: not s.isdigit()),  # string instead of int
            st.floats(allow_nan=False, allow_infinity=False).map(lambda f: str(f)),  # float as string
        )
    )

    # amount: string (sometimes as number)
    amount_val = maybe_wrong(
        draw,
        correct=amount_edge_cases,
        wrongs=st.one_of(
            st.integers(min_value=-10, max_value=10).map(str),  # integer as string (could be ambiguous)
            st.integers(min_value=-10, max_value=10),  # as number, not string
            st.floats(allow_nan=True, allow_infinity=True),  # as float, not string
        )
    )

    # name: string or null (sometimes as number or bool)
    name_val = maybe_wrong(
        draw,
        correct=name_edge_cases,
        wrongs=st.one_of(
            st.integers(min_value=-10, max_value=10),
            st.booleans(),
            st.just([]),
        )
    )

    # status: correct or wrong value
    status_val = maybe_wrong(
        draw,
        correct=status_values,
        wrongs=st.one_of(
            st.just(""), st.just("ACTIVE"), st.just("inactive "), st.just("unknownn"), st.just(None), st.just(1)
        )
    )

    # tags: array of strings (sometimes as string, null, or array of non-strings)
    tags_val = maybe_wrong(
        draw,
        correct=tags_edge_cases,
        wrongs=st.one_of(
            st.just(None),
            st.text(min_size=0, max_size=10),  # string instead of array
            st.lists(st.integers(min_value=0, max_value=10), min_size=1, max_size=3),  # array of ints
            st.lists(st.just(None), min_size=1, max_size=2),  # array of nulls
        )
    )

    # child: Record or null (sometimes as wrong type)
    if depth < 1:
        child_val = maybe_wrong(
            draw,
            correct=st.one_of(st.none(), record(depth=depth+1)),
            wrongs=st.one_of(
                st.just(1),
                st.just("child"),
                st.just([]),
                st.just({}),
            )
        )
    else:
        child_val = maybe_wrong(
            draw,
            correct=st.just(None),
            wrongs=st.one_of(
                st.just(1),
                st.just("child"),
                st.just([]),
                st.just({}),
            )
        )

    # Build JSON string for this record
    def json_escape(s):
        return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

    def to_json(val):
        if val is None:
            return "null"
        elif isinstance(val, str):
            return json_escape(val)
        elif isinstance(val, bool):
            return "true" if val else "false"
        elif isinstance(val, int) or isinstance(val, float):
            return str(val)
        elif isinstance(val, list):
            return "[" + ",".join(to_json(x) for x in val) + "]"
        elif isinstance(val, dict):
            # Should not occur, but handle just in case
            return "{" + ",".join(json_escape(str(k)) + ":" + to_json(v) for k, v in val.items()) + "}"
        else:
            # fallback
            return json_escape(str(val))

    # Compose the JSON object
    fields = [
        '"id":' + to_json(id_val),
        '"amount":' + to_json(amount_val),
        '"name":' + to_json(name_val),
        '"status":' + to_json(status_val),
        '"tags":' + to_json(tags_val),
        '"child":' + to_json(child_val),
    ]
    json_obj = "{" + ",".join(fields) + "}"
    return json_obj.encode("utf-8")

@st.composite
def generated_json(draw):
    return draw(record())