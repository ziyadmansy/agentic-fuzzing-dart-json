from hypothesis import strategies as st

# Helper strategies for edge-case values
status_values = st.sampled_from(["active", "inactive", "unknown"])
amount_edge_cases = st.one_of(
    st.just(""),  # empty string
    st.just("0"),  # zero as string
    st.just("-0"),  # negative zero
    st.just("0.0"),  # float zero
    st.just("1e10"),  # scientific notation
    st.just("NaN"),  # not a number
    st.just("Infinity"),  # infinity
    st.just("-Infinity"),  # negative infinity
    st.text(min_size=1, max_size=10),  # random short string
)
name_edge_cases = st.one_of(
    st.none(),
    st.just(""),  # empty string
    st.just("null"),  # string "null"
    st.text(min_size=1, max_size=10),
)
tags_edge_cases = st.one_of(
    st.lists(st.text(min_size=0, max_size=10), min_size=0, max_size=3),
    st.just([]),  # empty list
    st.just([""]),  # list with empty string
    st.just(["null"]),  # list with string "null"
    st.just([None]),  # list with None (will be rendered as null)
)

# Helper to maybe make a field "wrong" type
def maybe_wrong_type(draw, correct, wrongs):
    if draw(st.booleans()):
        return draw(wrongs)
    return draw(correct)

@st.composite
def generated_json(draw, max_depth=1):
    # id: usually int, sometimes wrong type
    id_val = maybe_wrong_type(
        draw,
        correct=st.integers(-2**31, 2**31-1),
        wrongs=st.one_of(
            st.text(min_size=1, max_size=8),
            st.floats(allow_nan=False, allow_infinity=False),
            st.just(None),
        ),
    )
    # amount: usually string, sometimes wrong type
    amount_val = maybe_wrong_type(
        draw,
        correct=amount_edge_cases,
        wrongs=st.one_of(
            st.integers(-1000, 1000),
            st.floats(allow_nan=True, allow_infinity=True),
            st.just(None),
        ),
    )
    # name: usually string or null, sometimes wrong type
    name_val = maybe_wrong_type(
        draw,
        correct=name_edge_cases,
        wrongs=st.one_of(
            st.integers(-1000, 1000),
            st.just([]),
        ),
    )
    # status: usually valid, sometimes wrong type or value
    status_val = maybe_wrong_type(
        draw,
        correct=status_values,
        wrongs=st.one_of(
            st.text(min_size=1, max_size=8).filter(lambda s: s not in {"active", "inactive", "unknown"}),
            st.integers(-10, 10),
            st.just(None),
        ),
    )
    # tags: usually list of strings, sometimes wrong type or element
    tags_val = maybe_wrong_type(
        draw,
        correct=tags_edge_cases,
        wrongs=st.one_of(
            st.just(None),
            st.text(min_size=1, max_size=10),
            st.lists(st.integers(-10, 10), min_size=1, max_size=3),
        ),
    )
    # child: usually null or another record, sometimes wrong type
    if max_depth > 0 and draw(st.booleans()):
        child_val = draw(generated_json(max_depth=max_depth-1)).decode("utf-8")
    else:
        child_val = maybe_wrong_type(
            draw,
            correct=st.none(),
            wrongs=st.one_of(
                st.just(123),
                st.just("not a record"),
                st.just([]),
            ),
        )

    # Helper to render a value as JSON
    def render_json(val):
        if val is None:
            return "null"
        elif isinstance(val, str):
            # Escape backslashes and quotes
            return '"' + val.replace('\\', '\\\\').replace('"', '\\"') + '"'
        elif isinstance(val, bool):
            return "true" if val else "false"
        elif isinstance(val, (int, float)):
            # For floats, handle special values
            if isinstance(val, float):
                if val != val:
                    return '"NaN"'
                if val == float("inf"):
                    return '"Infinity"'
                if val == float("-inf"):
                    return '"-Infinity"'
            return str(val)
        elif isinstance(val, list):
            return "[" + ",".join(render_json(x) for x in val) + "]"
        elif isinstance(val, dict):
            return "{" + ",".join(
                render_json(k) + ":" + render_json(v) for k, v in val.items()
            ) + "}"
        else:
            # Fallback: string representation
            return '"' + str(val) + '"'

    # Compose the JSON object as a string
    fields = [
        '"id":' + render_json(id_val),
        '"amount":' + render_json(amount_val),
        '"name":' + render_json(name_val),
        '"status":' + render_json(status_val),
        '"tags":' + render_json(tags_val),
        '"child":' + (child_val if isinstance(child_val, str) and child_val.startswith("{") else render_json(child_val)),
    ]
    json_str = "{" + ",".join(fields) + "}"
    return json_str.encode("utf-8")