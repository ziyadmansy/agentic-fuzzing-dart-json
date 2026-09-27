from hypothesis import strategies as st

# Constants for schema
STATUSES = ["active", "inactive", "unknown"]

def json_escape(s):
    # Minimal JSON string escape (no control chars, quotes, or backslashes in test data)
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

@st.composite
def generated_json(draw, depth=0):
    # Helper to sometimes produce "almost right" but subtly wrong values
    def almost_right_int():
        return st.one_of(
            st.integers(min_value=-(2**31), max_value=2**31-1),  # correct
            st.floats(allow_nan=False, allow_infinity=False).filter(lambda f: not f.is_integer()),  # float instead of int
            st.text(min_size=1, max_size=10).filter(lambda s: not s.isdigit()),  # string instead of int
            st.just("null"),  # string "null"
        )

    def almost_right_amount():
        return st.one_of(
            st.text(min_size=1, max_size=12),  # correct
            st.integers(min_value=-999999, max_value=999999).map(str),  # int as string
            st.just(""),  # empty string
            st.just(" "),  # whitespace string
            st.just("null"),  # string "null"
        )

    def almost_right_name():
        return st.one_of(
            st.text(min_size=0, max_size=10),  # correct
            st.none(),  # null
            st.integers(min_value=-100, max_value=100).map(str),  # int as string
            st.just("null"),  # string "null"
        )

    def almost_right_status():
        return st.one_of(
            st.sampled_from(STATUSES),  # correct
            st.text(min_size=0, max_size=8).filter(lambda s: s not in STATUSES),  # wrong string
            st.integers(min_value=0, max_value=2).map(str),  # "0", "1", "2"
            st.just("null"),  # string "null"
            st.none(),  # null
        )

    def almost_right_tags():
        # Sometimes correct, sometimes wrong type, sometimes wrong element type
        return st.one_of(
            st.lists(st.text(min_size=0, max_size=8), min_size=0, max_size=4),  # correct
            st.lists(st.integers(min_value=0, max_value=100), min_size=1, max_size=3),  # ints instead of strings
            st.text(min_size=0, max_size=12),  # string instead of array
            st.none(),  # null instead of array
            st.just([]),  # empty array
        )

    def almost_right_child():
        # At depth 0, allow recursion; at depth 1, only null or omit
        if depth == 0:
            return st.one_of(
                generated_json(depth=1).map(lambda b: b.decode()),  # valid child
                st.none(),  # null
                st.just("null"),  # string "null"
            )
        else:
            return st.one_of(
                st.none(),
                st.just("null"),
            )

    # Choose which field(s) to perturb
    fields = ["id", "amount", "name", "status", "tags", "child"]
    # With high probability, all fields correct; with some, one or two fields "almost right"
    perturb = draw(st.booleans())
    if perturb:
        # Pick 1 or 2 fields to perturb
        n_perturb = draw(st.integers(min_value=1, max_value=2))
        perturb_fields = draw(st.lists(st.sampled_from(fields), min_size=n_perturb, max_size=n_perturb, unique=True))
    else:
        perturb_fields = []

    # Build each field
    if "id" in perturb_fields:
        id_val = draw(almost_right_int())
        if isinstance(id_val, int):
            id_json = str(id_val)
        else:
            id_json = json_escape(str(id_val))
    else:
        id_json = str(draw(st.integers(min_value=-(2**31), max_value=2**31-1)))

    if "amount" in perturb_fields:
        amount_val = draw(almost_right_amount())
        amount_json = json_escape(str(amount_val))
    else:
        amount_json = json_escape(draw(st.text(min_size=1, max_size=12)))

    if "name" in perturb_fields:
        name_val = draw(almost_right_name())
        if name_val is None:
            name_json = "null"
        else:
            name_json = json_escape(str(name_val))
    else:
        name = draw(st.text(min_size=0, max_size=10))
        name_json = json_escape(name) if name != "" else "null"

    if "status" in perturb_fields:
        status_val = draw(almost_right_status())
        if status_val is None:
            status_json = "null"
        else:
            status_json = json_escape(str(status_val))
    else:
        status_json = json_escape(draw(st.sampled_from(STATUSES)))

    if "tags" in perturb_fields:
        tags_val = draw(almost_right_tags())
        if isinstance(tags_val, list):
            if all(isinstance(t, str) for t in tags_val):
                tags_json = "[" + ",".join(json_escape(t) for t in tags_val) + "]"
            else:
                tags_json = "[" + ",".join(str(t) for t in tags_val) + "]"
        elif tags_val is None:
            tags_json = "null"
        else:
            tags_json = json_escape(str(tags_val))
    else:
        tags = draw(st.lists(st.text(min_size=0, max_size=8), min_size=0, max_size=4))
        tags_json = "[" + ",".join(json_escape(t) for t in tags) + "]"

    if "child" in perturb_fields:
        child_val = draw(almost_right_child())
        if child_val is None:
            child_json = "null"
        elif child_val == "null":
            child_json = json_escape("null")
        else:
            child_json = child_val
    else:
        if depth == 0:
            child = draw(st.one_of(generated_json(depth=1).map(lambda b: b.decode()), st.none()))
            child_json = child if child is not None else "null"
        else:
            child_json = "null"

    # Compose JSON object
    json_obj = (
        '{'
        f'"id": {id_json}, '
        f'"amount": {amount_json}, '
        f'"name": {name_json}, '
        f'"status": {status_json}, '
        f'"tags": {tags_json}, '
        f'"child": {child_json}'
        '}'
    )
    return json_obj.encode("utf-8")