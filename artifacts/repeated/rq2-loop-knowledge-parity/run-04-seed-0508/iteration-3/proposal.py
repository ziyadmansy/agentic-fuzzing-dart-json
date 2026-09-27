from hypothesis import strategies as st

# Helper: JSON string escaping for double quotes and backslashes only,
# minimal escaping to keep output valid JSON strings.
def json_string_escape(s: str) -> str:
    # Escape backslash and double quote only, minimal for JSON validity.
    return s.replace('\\', '\\\\').replace('"', '\\"')

# Compose a JSON string literal from a Python string.
def json_string(s: str) -> str:
    return '"' + json_string_escape(s) + '"'

# Compose a JSON array of strings.
def json_array_of_strings(lst) -> str:
    return '[' + ','.join(json_string(s) for s in lst) + ']'

# Compose a JSON object from a dict of key->value strings (already JSON encoded).
def json_object(d: dict) -> str:
    # keys are always strings, encode keys as JSON strings
    items = []
    for k, v in d.items():
        items.append(json_string(k) + ':' + v)
    return '{' + ','.join(items) + '}'

@st.composite
def generated_json(draw) -> bytes:
    """
    Generate syntactically valid JSON objects as bytes, representing the described record schema,
    with controlled variations to induce behavioral divergence between four Dart JSON deserializers.

    Strategy:
    - Always produce an object with all six fields present (id, amount, name, status, tags, child),
      except sometimes omit 'tags' to trigger known divergence (built_value accepts missing tags).
    - Vary 'id' as int or double (to trigger manual/built_value vs json_serializable/freezed divergence).
    - Vary 'amount' as string (always string, but sometimes empty or unusual).
    - Vary 'name' as string or null.
    - Vary 'status' as one of the three valid strings, or sometimes an invalid string to cause rejection.
    - Vary 'tags' as array of strings, empty or non-empty, or sometimes omit it entirely.
    - Vary 'child' as null or a nested record (one level recursion only).
    - Introduce subtle type errors on one field at a time (e.g. number instead of string for amount),
      or null for non-nullable fields, or missing fields (except id, amount, status which must be present).
    - Use bounded recursion for child.
    """

    # Constants for status field
    valid_statuses = ["active", "inactive", "unknown"]
    invalid_statuses = ["invalid", "pending", ""]

    # Decide if we omit 'tags' field to trigger known divergence (built_value accepts missing tags)
    omit_tags = draw(st.booleans())

    # Decide if we produce a child record or null
    produce_child = draw(st.booleans())

    # To avoid infinite recursion, limit recursion depth by passing a parameter.
    # We'll implement a helper inner function with depth parameter.

    def gen_record(depth: int) -> str:
        # id: either int or double (to trigger divergence)
        # manual and built_value require int; json_serializable/freezed accept double and convert to int.
        # jsonDecode turns large int literals outside 64-bit range into double.
        id_type = draw(st.sampled_from(["int", "double", "large_int_as_double"]))
        if id_type == "int":
            # Normal int within 64-bit range
            id_val = draw(st.integers(min_value=-(2**63), max_value=2**63 - 1))
            id_json = str(id_val)
        elif id_type == "double":
            # Double with fractional part, should cause rejection by manual and built_value
            # but accepted by json_serializable/freezed (toInt truncates)
            # Use a double that is not integral
            id_val = draw(st.floats(min_value=-1e9, max_value=1e9, allow_nan=False, allow_infinity=False)).__round__(3)
            # Ensure fractional part is non-zero
            if id_val == int(id_val):
                id_val += 0.123
            id_json = repr(id_val)
        else:  # large_int_as_double
            # Large int outside 64-bit range, encoded as double by jsonDecode
            # Use a large integer literal > 2**63 - 1 or < -2**63
            large_int = draw(st.one_of(
                st.integers(min_value=2**63, max_value=2**65),
                st.integers(min_value=-(2**65), max_value=-(2**63 + 1)),
            ))
            # Represent as JSON number literal with .0 to force double
            id_json = str(float(large_int))

        # amount: string, but sometimes empty or unusual
        # Also try injecting a number (wrong type) rarely to trigger rejection
        amount_type = draw(st.sampled_from(["string", "number_wrong_type"]))
        if amount_type == "string":
            # string with ascii printable chars, length 0..20
            amount_str = draw(st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126), max_size=20))
            amount_json = json_string(amount_str)
        else:
            # wrong type: number (int or double)
            wrong_num = draw(st.one_of(
                st.integers(min_value=-1000, max_value=1000),
                st.floats(min_value=-1000, max_value=1000, allow_nan=False, allow_infinity=False)
            ))
            amount_json = repr(wrong_num)

        # name: nullable string or null
        # Also try wrong type rarely (number) to cause rejection
        name_type = draw(st.sampled_from(["string", "null", "number_wrong_type"]))
        if name_type == "string":
            name_str = draw(st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126), max_size=15))
            name_json = json_string(name_str)
        elif name_type == "null":
            name_json = "null"
        else:
            wrong_num = draw(st.one_of(
                st.integers(min_value=-1000, max_value=1000),
                st.floats(min_value=-1000, max_value=1000, allow_nan=False, allow_infinity=False)
            ))
            name_json = repr(wrong_num)

        # status: valid or invalid string
        status_type = draw(st.sampled_from(["valid", "invalid"]))
        if status_type == "valid":
            status_val = draw(st.sampled_from(valid_statuses))
        else:
            status_val = draw(st.sampled_from(invalid_statuses))
        status_json = json_string(status_val)

        # tags: array of strings, empty or non-empty, or omitted (omit_tags)
        # Also try wrong type rarely (string instead of array) to cause rejection
        if omit_tags:
            tags_json = None
        else:
            tags_type = draw(st.sampled_from(["array", "string_wrong_type"]))
            if tags_type == "array":
                # array of 0..5 strings, each string length 1..10 ascii printable
                tags_list = draw(st.lists(
                    st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126), min_size=1, max_size=10),
                    min_size=0, max_size=5
                ))
                tags_json = json_array_of_strings(tags_list)
            else:
                # wrong type: string
                wrong_str = draw(st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126), max_size=10))
                tags_json = json_string(wrong_str)

        # child: null or nested record (one level recursion only)
        # Also try wrong type rarely (number) to cause rejection
        if depth >= 1:
            # limit recursion depth to 1
            child_json = "null"
        else:
            child_type = draw(st.sampled_from(["null", "record", "number_wrong_type"]))
            if child_type == "null":
                child_json = "null"
            elif child_type == "record":
                child_json = gen_record(depth + 1)
            else:
                wrong_num = draw(st.one_of(
                    st.integers(min_value=-1000, max_value=1000),
                    st.floats(min_value=-1000, max_value=1000, allow_nan=False, allow_infinity=False)
                ))
                child_json = repr(wrong_num)

        # Compose fields dictionary, omit tags if omit_tags is True
        fields = {
            "id": id_json,
            "amount": amount_json,
            "name": name_json,
            "status": status_json,
            "child": child_json,
        }
        if tags_json is not None:
            fields["tags"] = tags_json

        return json_object(fields)

    # Generate top-level record with depth=0
    json_text = gen_record(0)

    # Return as bytes
    return json_text.encode("utf-8")