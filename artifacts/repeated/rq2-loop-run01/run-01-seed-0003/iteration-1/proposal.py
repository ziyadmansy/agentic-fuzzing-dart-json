from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for the "status" enum
    statuses = ["active", "inactive", "unknown"]

    # Helper to produce a JSON string literal with proper escaping of quotes and backslashes
    def json_string(s: str) -> str:
        # Escape backslash and double quote for JSON string
        s = s.replace("\\", "\\\\").replace('"', '\\"')
        # Also escape control characters minimally (e.g. newline, tab)
        s = s.replace("\b", "\\b").replace("\f", "\\f").replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
        return f'"{s}"'

    # Compose a JSON array of strings (tags)
    def json_array_of_strings(lst):
        # lst is list of strings
        return "[" + ",".join(json_string(x) for x in lst) + "]"

    # Compose a JSON object from a dict of fieldname->jsonvalue strings
    def json_object(d):
        # d: dict[str, str], values are JSON text for the field values
        # Output fields in fixed order for determinism
        fields_order = ["id", "amount", "name", "status", "tags", "child"]
        parts = []
        for f in fields_order:
            parts.append(json_string(f) + ":" + d[f])
        return "{" + ",".join(parts) + "}"

    # Strategy for "id" field: integer normally, but sometimes a stringified int or float to cause divergence
    # We produce a string representing the JSON value (e.g. "123" or 123)
    id_value = draw(
        st.one_of(
            st.integers(min_value=0, max_value=1_000_000).map(str),  # normal int as JSON number
            st.integers(min_value=0, max_value=1_000_000).map(lambda i: json_string(str(i))),  # int as JSON string
            st.floats(min_value=0, max_value=1_000_000, allow_nan=False, allow_infinity=False).map(lambda f: str(f)),  # float number
        )
    )

    # Strategy for "amount" field: string normally, but sometimes a number or null to cause divergence
    # amount is a string in schema, but we try to break that by sometimes emitting a number or null
    amount_value = draw(
        st.one_of(
            st.text(min_size=1, max_size=20).map(json_string),
            st.integers(min_value=0, max_value=1_000_000).map(str),
            st.just("null"),
        )
    )

    # Strategy for "name" field: string or null normally, but sometimes a number or boolean to cause divergence
    name_value = draw(
        st.one_of(
            st.none().map(lambda _: "null"),
            st.text(min_size=0, max_size=20).map(json_string),
            st.integers(min_value=-1000, max_value=1000).map(str),
            st.booleans().map(lambda b: "true" if b else "false"),
        )
    )

    # Strategy for "status" field: one of the three strings normally, but sometimes null or a wrong string
    status_value = draw(
        st.one_of(
            st.sampled_from(statuses).map(json_string),
            st.none().map(lambda _: "null"),
            st.text(min_size=1, max_size=10).filter(lambda s: s not in statuses).map(json_string),
        )
    )

    # Strategy for "tags" field: array of strings normally, but sometimes null, or array with non-string elements
    # We produce JSON text for the array or null
    def tags_array():
        # array of strings normally
        normal = st.lists(st.text(min_size=0, max_size=10), min_size=0, max_size=5).map(json_array_of_strings)
        # array with some non-string elements (numbers, null, booleans)
        mixed = st.lists(
            st.one_of(
                st.text(min_size=0, max_size=10).map(json_string),
                st.integers(min_value=-1000, max_value=1000).map(str),
                st.just("null"),
                st.booleans().map(lambda b: "true" if b else "false"),
            ),
            min_size=0,
            max_size=5,
        ).map(lambda lst: "[" + ",".join(lst) + "]")
        # null
        null = st.just("null")
        return st.one_of(normal, mixed, null)

    tags_value = draw(tags_array())

    # Recursive "child" field: either null or a nested record (one level only)
    # To avoid deep recursion, only one level of nesting allowed
    # Compose the child record JSON text or "null"
    # We reuse the same field strategies but restrict recursion depth to 0 here

    # For the child record, we do not recurse further (child.child is always null)
    def child_record():
        # id for child: integer only (to reduce complexity)
        child_id = draw(st.integers(min_value=0, max_value=1_000_000).map(str))
        # amount string only (valid)
        child_amount = draw(st.text(min_size=1, max_size=20).map(json_string))
        # name string or null
        child_name = draw(st.one_of(st.none(), st.text(min_size=0, max_size=20)).map(lambda v: "null" if v is None else json_string(v)))
        # status one of three strings only
        child_status = draw(st.sampled_from(statuses).map(json_string))
        # tags array of strings only
        child_tags = draw(st.lists(st.text(min_size=0, max_size=10), min_size=0, max_size=5).map(json_array_of_strings))
        # child.child is always null
        child_child = "null"
        d = {
            "id": child_id,
            "amount": child_amount,
            "name": child_name,
            "status": child_status,
            "tags": child_tags,
            "child": child_child,
        }
        return json_object(d)

    child_value = draw(st.one_of(child_record(), st.just("null")))

    # Compose top-level record JSON object
    top = {
        "id": id_value,
        "amount": amount_value,
        "name": name_value,
        "status": status_value,
        "tags": tags_value,
        "child": child_value,
    }

    json_text = json_object(top)
    return json_text.encode("utf-8")