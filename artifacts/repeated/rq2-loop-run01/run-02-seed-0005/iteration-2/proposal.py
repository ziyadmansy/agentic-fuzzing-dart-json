from hypothesis import strategies as st

# Helper: JSON string escaping for a limited safe subset (no control chars, no quotes inside)
# We'll generate strings from a safe charset to avoid escaping complexity.
_safe_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _-"

def json_string(s: str) -> str:
    # Wrap s in quotes, no escaping needed if s only contains _safe_chars
    return '"' + s + '"'

# Enum for status field
_status_values = ["active", "inactive", "unknown"]

@st.composite
def generated_json(draw) -> bytes:
    """
    Generate syntactically valid JSON objects matching the schema, but with
    1-2 subtle deviations to provoke behavioral divergence between four Dart JSON deserializers.
    """

    # Base valid fields generators:

    # id: integer normally, but sometimes string or float to provoke type divergence
    # We'll pick mostly int, but sometimes stringified int or float to provoke divergence.
    id_type = draw(st.sampled_from(["int", "string_int", "float", "missing"]))
    if id_type == "int":
        id_val = draw(st.integers(min_value=0, max_value=10**9))
        id_json = str(id_val)
    elif id_type == "string_int":
        id_val = draw(st.integers(min_value=0, max_value=10**9))
        id_json = json_string(str(id_val))
    elif id_type == "float":
        # float that looks like int or not
        id_val = draw(st.floats(min_value=0, max_value=10**9, allow_nan=False, allow_infinity=False))
        # JSON float serialization: use repr
        id_json = repr(id_val)
    else:  # missing
        id_json = None

    # amount: string normally, but sometimes number or null or missing
    amount_type = draw(st.sampled_from(["string", "number", "null", "missing"]))
    if amount_type == "string":
        # safe string with digits and dot, resembling a decimal number
        amount_val = draw(st.text(alphabet="0123456789.", min_size=1, max_size=10))
        # avoid empty or just dots
        if not any(c.isdigit() for c in amount_val):
            amount_val = "0.0"
        amount_json = json_string(amount_val)
    elif amount_type == "number":
        # float or int
        amount_val = draw(st.one_of(st.integers(min_value=0, max_value=10**9), st.floats(min_value=0, max_value=10**9, allow_nan=False, allow_infinity=False)))
        amount_json = repr(amount_val)
    elif amount_type == "null":
        amount_json = "null"
    else:  # missing
        amount_json = None

    # name: string or null or missing, sometimes empty string, sometimes a string "null"
    name_type = draw(st.sampled_from(["string", "null", "missing"]))
    if name_type == "string":
        # safe string, sometimes empty, sometimes "null"
        name_val = draw(st.one_of(
            st.just("null"),
            st.text(alphabet=_safe_chars, min_size=0, max_size=10)
        ))
        name_json = json_string(name_val)
    elif name_type == "null":
        name_json = "null"
    else:
        name_json = None

    # status: one of the three strings normally, but sometimes invalid string or null or missing
    status_type = draw(st.sampled_from(["valid", "invalid_string", "null", "missing"]))
    if status_type == "valid":
        status_val = draw(st.sampled_from(_status_values))
        status_json = json_string(status_val)
    elif status_type == "invalid_string":
        # string not in enum, e.g. "actve", "inactiv", "unknownn", or empty string
        status_val = draw(st.one_of(
            st.just("actve"),
            st.just("inactiv"),
            st.just("unknownn"),
            st.just(""),
            st.text(alphabet=_safe_chars, min_size=1, max_size=10).filter(lambda s: s not in _status_values)
        ))
        status_json = json_string(status_val)
    elif status_type == "null":
        status_json = "null"
    else:
        status_json = None

    # tags: array of strings normally, but sometimes null, empty array, array with null elements, or missing
    tags_type = draw(st.sampled_from(["valid", "null", "empty", "with_null", "missing"]))
    if tags_type == "valid":
        # array of 1-5 safe strings
        tags_list = draw(st.lists(st.text(alphabet=_safe_chars, min_size=1, max_size=10), min_size=1, max_size=5))
        tags_json = "[" + ",".join(json_string(t) for t in tags_list) + "]"
    elif tags_type == "null":
        tags_json = "null"
    elif tags_type == "empty":
        tags_json = "[]"
    elif tags_type == "with_null":
        # array with some strings and some nulls
        n = draw(st.integers(min_value=1, max_value=5))
        elems = []
        for _ in range(n):
            if draw(st.booleans()):
                elems.append(json_string(draw(st.text(alphabet=_safe_chars, min_size=1, max_size=10))))
            else:
                elems.append("null")
        tags_json = "[" + ",".join(elems) + "]"
    else:
        tags_json = None

    # child: either null, missing, or a nested record (one level only)
    # To keep recursion bounded, child record is always valid or with one subtle deviation.
    child_type = draw(st.sampled_from(["valid", "null", "missing", "invalid_type"]))
    if child_type == "null":
        child_json = "null"
    elif child_type == "missing":
        child_json = None
    elif child_type == "invalid_type":
        # child is a string or number instead of object
        child_json = draw(st.one_of(
            st.text(alphabet=_safe_chars, min_size=1, max_size=10).map(json_string),
            st.integers(min_value=0, max_value=100).map(str),
            st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False).map(repr)
        ))
    else:
        # valid or subtly invalid nested record: reuse this generator but force no further recursion
        # To avoid infinite recursion, generate a valid nested record with no child field or child=null only.
        # We'll generate a valid nested record with child=null always.
        # We do not recurse with deviations to keep complexity manageable.
        # Generate nested record fields with no missing fields, but allow subtle deviations on one field.

        # Nested id: always int
        nid_val = draw(st.integers(min_value=0, max_value=10**9))
        nid_json = str(nid_val)

        # Nested amount: string decimal
        namount_val = draw(st.text(alphabet="0123456789.", min_size=1, max_size=10))
        if not any(c.isdigit() for c in namount_val):
            namount_val = "0.0"
        namount_json = json_string(namount_val)

        # Nested name: string or null
        nname_val = draw(st.one_of(
            st.none(),
            st.text(alphabet=_safe_chars, min_size=0, max_size=10)
        ))
        if nname_val is None:
            nname_json = "null"
        else:
            nname_json = json_string(nname_val)

        # Nested status: valid enum only
        nstatus_val = draw(st.sampled_from(_status_values))
        nstatus_json = json_string(nstatus_val)

        # Nested tags: valid array of strings, 1-3 elements
        ntags_list = draw(st.lists(st.text(alphabet=_safe_chars, min_size=1, max_size=10), min_size=1, max_size=3))
        ntags_json = "[" + ",".join(json_string(t) for t in ntags_list) + "]"

        # Nested child: always null to avoid recursion
        nchild_json = "null"

        child_json = (
            "{" +
            f"\"id\":{nid_json}," +
            f"\"amount\":{namount_json}," +
            f"\"name\":{nname_json}," +
            f"\"status\":{nstatus_json}," +
            f"\"tags\":{ntags_json}," +
            f"\"child\":{nchild_json}" +
            "}"
        )

    # Compose top-level JSON object fields, omitting those with None (missing)
    fields = []
    if id_json is not None:
        fields.append(f"\"id\":{id_json}")
    if amount_json is not None:
        fields.append(f"\"amount\":{amount_json}")
    if name_json is not None:
        fields.append(f"\"name\":{name_json}")
    if status_json is not None:
        fields.append(f"\"status\":{status_json}")
    if tags_json is not None:
        fields.append(f"\"tags\":{tags_json}")
    if child_json is not None:
        fields.append(f"\"child\":{child_json}")

    json_text = "{" + ",".join(fields) + "}"

    return json_text.encode("utf-8")