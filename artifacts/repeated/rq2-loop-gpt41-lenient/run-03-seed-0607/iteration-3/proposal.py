from hypothesis import strategies as st

# Helper strategies for fields
def json_string():
    # Strings with possible edge cases: empty, whitespace, unicode, escape sequences
    edge_cases = [
        "", " ", "\n", "\r", "\t", "\"", "\\", "\\n", "\\u1234", "0", "null", "NaN", "Infinity"
    ]
    base = st.text(
        alphabet=st.characters(blacklist_categories=["Cs", "Cc"]),
        min_size=0, max_size=32
    )
    return st.one_of(st.sampled_from(edge_cases), base)

def json_number_string():
    # Strings that look like numbers, including edge cases
    edge_cases = [
        "0", "-0", "1", "-1", "1.0", "-1.0", "1e10", "-1e10", "NaN", "Infinity", "-Infinity", "00", "01", "1.", ".1"
    ]
    base = st.text(
        alphabet="0123456789.eE+-", min_size=1, max_size=16
    )
    return st.one_of(st.sampled_from(edge_cases), base)

def json_nullable_string():
    # Sometimes null, sometimes string, sometimes edge-case string
    return st.one_of(st.none(), json_string())

def json_status():
    # Valid and invalid enum values
    return st.one_of(
        st.sampled_from(["active", "inactive", "unknown"]),
        json_string().filter(lambda s: s not in {"active", "inactive", "unknown"})
    )

def json_tags():
    # Array of strings, sometimes empty, sometimes with edge-case strings, sometimes with wrong types
    tag_string = json_string()
    wrong_type = st.one_of(
        st.integers(), st.floats(allow_nan=True, allow_infinity=True), st.none(), st.booleans()
    )
    # Sometimes a valid array, sometimes with a wrong-type element
    valid_array = st.lists(tag_string, min_size=0, max_size=5)
    edge_array = st.lists(
        st.one_of(tag_string, wrong_type),
        min_size=1, max_size=5
    )
    return st.one_of(valid_array, edge_array)

def json_id():
    # Usually integer, sometimes float, string, or null
    return st.one_of(
        st.integers(min_value=-2**31, max_value=2**31-1),
        st.floats(allow_nan=True, allow_infinity=True),
        json_string(),
        st.none()
    )

# Recursion for "child" field
def record_strategy(max_depth):
    @st.composite
    def _record(draw):
        # At depth limit, child is always null
        if max_depth <= 0:
            child = "null"
        else:
            # Sometimes null, sometimes another record
            child = draw(
                st.one_of(
                    st.just("null"),
                    record_strategy(max_depth - 1)
                )
            )
        # Each field: sometimes valid, sometimes with a single type error
        # For divergence, randomly pick one field to "perturb"
        fields = ["id", "amount", "name", "status", "tags", "child"]
        perturb_field = draw(st.sampled_from(fields + [None]))  # Sometimes no perturbation

        # id
        if perturb_field == "id":
            id_val = draw(st.one_of(
                st.floats(allow_nan=True, allow_infinity=True),
                json_string(),
                st.none()
            ))
        else:
            id_val = draw(st.integers(min_value=-2**31, max_value=2**31-1))

        # amount
        if perturb_field == "amount":
            amount_val = draw(st.one_of(
                st.integers(), st.floats(allow_nan=True, allow_infinity=True), st.none()
            ))
        else:
            amount_val = draw(json_number_string())

        # name
        if perturb_field == "name":
            name_val = draw(st.one_of(
                st.integers(), st.floats(allow_nan=True, allow_infinity=True), st.lists(st.integers()), st.just({})
            ))
        else:
            name_val = draw(json_nullable_string())

        # status
        if perturb_field == "status":
            status_val = draw(json_string())
        else:
            status_val = draw(json_status())

        # tags
        if perturb_field == "tags":
            tags_val = draw(st.one_of(
                st.lists(st.integers(), min_size=1, max_size=3),
                st.just("null"),
                st.just({})
            ))
        else:
            tags_val = draw(json_tags())

        # child (already handled above)

        # JSON encode fields
        def encode(val):
            if isinstance(val, str):
                # Escape backslashes and quotes
                return '"' + val.replace("\\", "\\\\").replace('"', '\\"') + '"'
            elif val is None:
                return "null"
            elif isinstance(val, bool):
                return "true" if val else "false"
            elif isinstance(val, (int, float)):
                # JSON numbers
                if isinstance(val, float):
                    if val != val:
                        return '"NaN"'
                    if val == float("inf"):
                        return '"Infinity"'
                    if val == float("-inf"):
                        return '"-Infinity"'
                return str(val)
            elif isinstance(val, list):
                return "[" + ",".join(encode(x) for x in val) + "]"
            elif isinstance(val, dict):
                # For rare cases where a dict is injected
                items = []
                for k, v in val.items():
                    items.append(encode(str(k)) + ":" + encode(v))
                return "{" + ",".join(items) + "}"
            else:
                return "null"

        json_obj = (
            "{"
            f"\"id\":{encode(id_val)},"
            f"\"amount\":{encode(amount_val)},"
            f"\"name\":{encode(name_val)},"
            f"\"status\":{encode(status_val)},"
            f"\"tags\":{encode(tags_val)},"
            f"\"child\":{child}"
            "}"
        )
        return json_obj
    return _record()

@st.composite
def generated_json(draw):
    # Limit recursion to 1 or 2 levels
    max_depth = draw(st.integers(min_value=0, max_value=1))
    json_text = draw(record_strategy(max_depth))
    # Return as bytes
    return json_text.encode("utf-8")