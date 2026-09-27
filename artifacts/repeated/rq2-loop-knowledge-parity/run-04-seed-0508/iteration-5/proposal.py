from hypothesis import strategies as st

# Constants for the "status" field
STATUS_VALUES = ["active", "inactive", "unknown"]

# Helper to produce a JSON string literal from a Python string (with minimal escaping)
def json_string_literal(s: str) -> str:
    # Escape backslash and double quote, and control chars minimally
    # Hypothesis strings won't have control chars by default, so minimal escaping:
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    return '"' + s + '"'

@st.composite
def generated_json(draw) -> bytes:
    """
    Generate syntactically valid JSON objects as bytes, matching the record schema,
    with subtle variations to provoke divergence among four Dart JSON deserializers.
    """

    # --- Primitive fields ---

    # id: integer or double that looks like int (to trigger json_serializable/freezed accepting double)
    # We generate either:
    # - a true int in 64-bit range (safe)
    # - a float that is an integer value (e.g. 1.0), to test json_serializable/freezed acceptance
    # - a float outside 64-bit int range, to test saturation behavior
    id_choice = draw(st.integers(min_value=-(2**63), max_value=2**63 - 1).map(lambda x: ("int", x)) |
                     st.floats(min_value=-(2**63)*2, max_value=(2**63)*2, allow_infinity=False, allow_nan=False)
                     .filter(lambda f: f.is_integer())
                     .map(lambda f: ("float_int", f)) |
                     st.floats(min_value=-(2**63)*10, max_value=(2**63)*10, allow_infinity=False, allow_nan=False)
                     .filter(lambda f: not f.is_integer())
                     .map(lambda f: ("float_nonint", f))
                     )

    # amount: string, always present, non-null
    # Use strings that look numeric or arbitrary text, to test no divergence on amount
    amount_str = draw(st.text(min_size=1, max_size=10))

    # name: nullable string or null
    # Use None or string
    name_val = draw(st.one_of(st.none(), st.text(min_size=0, max_size=10)))

    # status: one of the known strings, or an unknown string to test rejection (but unknown rejected by all)
    # To maximize divergence, only use known values here (unknown rejected by all)
    status_val = draw(st.sampled_from(STATUS_VALUES))

    # tags: array of strings, or missing (to test built_value accepting missing tags)
    # To provoke divergence, sometimes omit tags, sometimes present empty or non-empty list
    tags_present = draw(st.booleans())
    if tags_present:
        # tags array: empty or non-empty list of strings
        tags_list = draw(st.lists(st.text(min_size=0, max_size=10), max_size=3))
    else:
        tags_list = None  # missing

    # child: nullable record or null
    # To keep recursion bounded, child is either null or a shallow record with no child
    child_present = draw(st.booleans())
    if child_present:
        # child record with no child field (null)
        # We generate a minimal valid record with child=null
        # Use simple values to avoid complexity in recursion
        child_id = draw(st.integers(min_value=0, max_value=100))
        child_amount = draw(st.text(min_size=1, max_size=5))
        child_name = draw(st.one_of(st.none(), st.text(min_size=0, max_size=5)))
        child_status = draw(st.sampled_from(STATUS_VALUES))
        child_tags_present = draw(st.booleans())
        if child_tags_present:
            child_tags = draw(st.lists(st.text(min_size=0, max_size=5), max_size=2))
        else:
            child_tags = None
        # child.child is always null to avoid deeper recursion
        child_child = None
    else:
        child_id = child_amount = child_name = child_status = child_tags = child_child = None

    # --- Build JSON text parts ---

    # id field JSON text
    if id_choice[0] == "int":
        id_json = str(id_choice[1])
    elif id_choice[0] == "float_int":
        # Represent as float with ".0" to distinguish from int
        id_json = str(float(id_choice[1]))
        if '.' not in id_json:
            id_json += ".0"
    else:
        # float_nonint
        # Represent with decimal point
        id_json = str(id_choice[1])
        if '.' not in id_json:
            id_json += ".5"  # force decimal

    # amount field JSON text (string)
    amount_json = json_string_literal(amount_str)

    # name field JSON text (nullable string)
    if name_val is None:
        name_json = "null"
    else:
        name_json = json_string_literal(name_val)

    # status field JSON text (string)
    status_json = json_string_literal(status_val)

    # tags field JSON text or missing
    if tags_list is None:
        tags_json = None
    else:
        # JSON array of strings
        tags_json = "[" + ",".join(json_string_literal(t) for t in tags_list) + "]"

    # child field JSON text (nullable record)
    if child_present:
        # Build child JSON object text
        # child.child is null
        child_id_json = str(child_id)
        child_amount_json = json_string_literal(child_amount)
        if child_name is None:
            child_name_json = "null"
        else:
            child_name_json = json_string_literal(child_name)
        child_status_json = json_string_literal(child_status)
        if child_tags is None:
            child_tags_json = None
        else:
            child_tags_json = "[" + ",".join(json_string_literal(t) for t in child_tags) + "]"
        child_child_json = "null"

        # Compose child object fields, omitting tags sometimes to provoke divergence
        child_fields = [
            '"id":' + child_id_json,
            '"amount":' + child_amount_json,
            '"name":' + child_name_json,
            '"status":' + child_status_json,
        ]
        if child_tags_json is not None:
            child_fields.append('"tags":' + child_tags_json)
        # Always include child: null in child record
        child_fields.append('"child":' + child_child_json)

        child_json = "{" + ",".join(child_fields) + "}"
    else:
        child_json = "null"

    # Compose top-level fields list, omitting tags sometimes to provoke divergence
    top_fields = [
        '"id":' + id_json,
        '"amount":' + amount_json,
        '"name":' + name_json,
        '"status":' + status_json,
    ]
    if tags_json is not None:
        top_fields.append('"tags":' + tags_json)
    top_fields.append('"child":' + child_json)

    # Compose top-level JSON object text
    json_text = "{" + ",".join(top_fields) + "}"

    return json_text.encode("utf-8")