from hypothesis import strategies as st

# Constants for the "status" enum strings
STATUS_VALUES = ["active", "inactive", "unknown"]

# Helper: JSON string escaper for Hypothesis-generated strings
def json_string(s: str) -> str:
    # Minimal escaping for JSON string (only backslash and quote)
    # Hypothesis strings won't contain control chars by default
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

@st.composite
def generated_json(draw) -> bytes:
    """
    Generate syntactically valid JSON objects as bytes, representing the Record schema,
    with subtle variations designed to trigger behavioral divergence between four Dart JSON deserializers.

    Strategy:
    - id: either a true int (within 64-bit range) or a double representing an int (to trigger toInt() differences)
    - amount: always a JSON string (nonempty)
    - name: either null or a JSON string (including empty string)
    - status: one of the three valid strings, or occasionally an invalid string to cause rejection
    - tags: either present as an array of strings (possibly empty), or missing (to trigger built_value acceptance vs others rejecting)
    - child: either null or a nested Record (one level deep max)
    - Introduce exactly one "off" thing per document to maximize disagreement:
      * missing tags field (built_value accepts, others reject)
      * id as double (manual and built_value require int, others accept)
      * status invalid string (all reject, no divergence)
      * tags present but wrong type (all reject, no divergence)
      * name missing (all accept, no divergence)
      * child missing (all accept, no divergence)
      * id missing (all reject, no divergence)
      * amount missing (all reject, no divergence)
      * status missing (all reject, no divergence)
    So focus on:
      - tags missing vs present
      - id as int vs id as double
      - tags present but empty array (valid)
      - name null vs string (both accepted)
      - child null vs nested record (both accepted)
    """

    # Generate a valid id number, either int or double representing int
    # 64-bit signed int range: -2**63 .. 2**63-1
    INT64_MIN = -(2**63)
    INT64_MAX = 2**63 - 1

    # Choose id as int or double (float) representing int
    id_is_double = draw(st.booleans())

    if id_is_double:
        # Generate an integer outside 64-bit range to force jsonDecode to produce double
        # But jsonDecode is outside our control, so simulate by producing a number with decimal point
        # We'll produce a number with decimal point but integer value (e.g. 1234.0)
        # This triggers manual and built_value to reject (expect int), others accept
        # Pick a 64-bit in-range int, then produce as float string with .0
        id_int = draw(st.integers(min_value=INT64_MIN, max_value=INT64_MAX))
        id_json = str(id_int) + ".0"
    else:
        # Produce a plain integer literal in range
        id_int = draw(st.integers(min_value=INT64_MIN, max_value=INT64_MAX))
        id_json = str(id_int)

    # amount: always a JSON string (nonempty)
    amount_str = draw(st.text(min_size=1, max_size=20))
    amount_json = json_string(amount_str)

    # name: nullable string or null
    name_is_null = draw(st.booleans())
    if name_is_null:
        name_json = "null"
    else:
        name_str = draw(st.text(max_size=20))
        name_json = json_string(name_str)

    # status: mostly valid, sometimes invalid to test rejection (no divergence)
    # To maximize divergence, mostly valid
    status_valid = draw(st.booleans())
    if status_valid:
        status_val = draw(st.sampled_from(STATUS_VALUES))
        status_json = json_string(status_val)
    else:
        # invalid status string (all reject, no divergence, but keep some for coverage)
        invalid_status = draw(st.text(min_size=1, max_size=10).filter(lambda s: s not in STATUS_VALUES))
        status_json = json_string(invalid_status)

    # tags: either present or missing (to trigger built_value acceptance vs others rejecting)
    tags_missing = draw(st.booleans())
    if not tags_missing:
        # tags present: array of strings (possibly empty)
        tags_len = draw(st.integers(min_value=0, max_value=5))
        tags_list = []
        for _ in range(tags_len):
            tag_str = draw(st.text(min_size=1, max_size=10))
            tags_list.append(json_string(tag_str))
        tags_json = "[" + ",".join(tags_list) + "]"
    else:
        tags_json = None  # missing

    # child: nullable record or null or missing (missing accepted by all)
    # To keep one-level recursion, child is either null or a nested record with no child
    child_is_null = draw(st.booleans())
    if child_is_null:
        child_json = "null"
    else:
        # nested record with no child (child=null)
        # id for child: always int (to avoid complexity)
        child_id = draw(st.integers(min_value=INT64_MIN, max_value=INT64_MAX))
        child_amount = draw(st.text(min_size=1, max_size=20))
        child_name_is_null = draw(st.booleans())
        if child_name_is_null:
            child_name_json = "null"
        else:
            child_name_json = json_string(draw(st.text(max_size=20)))
        child_status = draw(st.sampled_from(STATUS_VALUES))
        child_tags_len = draw(st.integers(min_value=0, max_value=3))
        child_tags_list = []
        for _ in range(child_tags_len):
            child_tags_list.append(json_string(draw(st.text(min_size=1, max_size=10))))
        child_tags_json = "[" + ",".join(child_tags_list) + "]"
        # child child is null
        child_json = (
            "{"
            + '"id":' + str(child_id) + ","
            + '"amount":' + json_string(child_amount) + ","
            + '"name":' + child_name_json + ","
            + '"status":' + json_string(child_status) + ","
            + '"tags":' + child_tags_json + ","
            + '"child":null'
            + "}"
        )

    # Compose top-level JSON object fields
    fields = [
        '"id":' + id_json,
        '"amount":' + amount_json,
        '"name":' + name_json,
        '"status":' + status_json,
    ]
    if tags_json is not None:
        fields.append('"tags":' + tags_json)
    # else omit tags field to test built_value acceptance vs others rejecting

    fields.append('"child":' + child_json)

    json_text = "{" + ",".join(fields) + "}"

    return json_text.encode("utf-8")