from hypothesis import strategies as st

# Constants for fixed enums and limits
STATUS_VALUES = ["active", "inactive", "unknown"]
MAX_RECURSION_DEPTH = 1

# Helper to produce a JSON string literal from a Python string (minimal escaping)
def json_string_literal(s: str) -> str:
    # Escape backslash and double quote and control chars minimally
    # Hypothesis strings won't contain control chars by default, so minimal escaping:
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    return '"' + s + '"'

@st.composite
def generated_json(draw) -> bytes:
    """
    Generate syntactically valid JSON objects as bytes, with schema:
    {
      "id": <integer or double (for json_serializable/freezed divergence)>,
      "amount": <string>,
      "name": <string or null or missing>,
      "status": <one of "active", "inactive", "unknown">,
      "tags": <array of strings or missing (to trigger built_value vs others)>,
      "child": <nested record or null or missing>
    }
    """

    # Recursive generator for the record, with depth control
    def gen_record(depth: int):
        # id field: sometimes int, sometimes double (to trigger divergence)
        # Manual and built_value require int; json_serializable/freezed accept double.toInt()
        # We produce either an int or a double representing an int, or a double outside int64 range
        id_type = draw(st.sampled_from(["int", "double_int", "double_out_of_range"]))

        if id_type == "int":
            # Produce a JSON integer literal within 64-bit range
            # Use 32-bit range to be safe
            id_val = draw(st.integers(min_value=-(2**31), max_value=2**31 - 1))
            id_json = str(id_val)
        elif id_type == "double_int":
            # Produce a JSON number with decimal point but integral value
            int_val = draw(st.integers(min_value=-(2**31), max_value=2**31 - 1))
            # Represent as float with .0 to force double
            id_json = str(float(int_val))
        else:
            # Produce a double outside int64 range to test saturation behavior
            # Use a large double literal (e.g. 1e20)
            # jsonDecode will parse as double
            large_double = draw(st.sampled_from([1e20, -1e20, 1e19, -1e19]))
            id_json = repr(large_double)  # repr to get e notation

        # amount: always string, non-empty, ASCII printable without quotes or control chars
        amount_str = draw(st.text(min_size=1, max_size=10, alphabet=st.characters(blacklist_characters='"\\')))
        amount_json = json_string_literal(amount_str)

        # name: nullable string or null or missing (missing accepted by all)
        name_option = draw(st.sampled_from(["string", "null", "missing"]))
        if name_option == "string":
            name_str = draw(st.text(min_size=0, max_size=10, alphabet=st.characters(blacklist_characters='"\\')))
            name_json = json_string_literal(name_str)
        elif name_option == "null":
            name_json = "null"
        else:
            name_json = None  # missing

        # status: one of the three valid strings, or invalid string to trigger rejection (but all reject invalid)
        # To maximize disagreement, only produce valid status here
        status_str = draw(st.sampled_from(STATUS_VALUES))
        status_json = json_string_literal(status_str)

        # tags: array of strings, or missing (to trigger built_value acceptance vs others rejection)
        # To maximize disagreement, sometimes omit tags
        tags_option = draw(st.sampled_from(["present", "missing"]))
        if tags_option == "present":
            # array of 0 to 3 strings
            tags_len = draw(st.integers(min_value=0, max_value=3))
            tags_elems = []
            for _ in range(tags_len):
                tag_str = draw(st.text(min_size=1, max_size=10, alphabet=st.characters(blacklist_characters='"\\')))
                tags_elems.append(json_string_literal(tag_str))
            tags_json = "[" + ",".join(tags_elems) + "]"
        else:
            tags_json = None  # missing

        # child: null, missing, or nested record (one level recursion max)
        child_option = draw(st.sampled_from(["null", "missing", "record"]))
        if child_option == "record" and depth < MAX_RECURSION_DEPTH:
            child_json = gen_record(depth + 1)
        elif child_option == "null":
            child_json = "null"
        else:
            child_json = None  # missing

        # Compose fields in random order, omitting missing fields
        fields = []

        fields.append('"id":' + id_json)
        fields.append('"amount":' + amount_json)
        if name_json is not None:
            fields.append('"name":' + name_json)
        fields.append('"status":' + status_json)
        if tags_json is not None:
            fields.append('"tags":' + tags_json)
        if child_json is not None:
            fields.append('"child":' + child_json)

        # Shuffle fields order to avoid positional bias
        from random import shuffle
        shuffle(fields)

        return "{" + ",".join(fields) + "}"

    # Generate top-level record
    json_text = gen_record(0)
    return json_text.encode("utf-8")