from hypothesis import strategies as st

# We produce JSON text for a single Record object, possibly with one level of recursion in "child".
# We carefully vary presence and types of fields to trigger divergences described.
# We produce syntactically valid JSON only, no invalid JSON syntax.
# We vary "id" around int vs double to exploit manual/built_value vs json_serializable/freezed difference.
# We vary presence of "tags" to exploit built_value accepting missing tags vs others rejecting.
# We vary "name" and "child" presence/nullability as allowed.
# We vary "status" among valid values only (invalid rejected by all).
# We do not produce unknown top-level keys (accepted by all, no divergence).
# We produce "amount" always as string (required).
# We produce "id" as int or double (toInt() difference).
# We produce "tags" as present array or missing (to trigger built_value acceptance difference).
# We produce "child" as null or nested record (one level only).
# We produce "name" as string or null or missing (missing accepted by all).
# We produce "tags" as empty array or non-empty array of strings.
# We produce "id" as int64 boundary values and out-of-range double to test saturation behavior.

# Helper: JSON string escape (minimal, only backslash and quote)
def json_string_escape(s: str) -> str:
    return s.replace('\\', '\\\\').replace('"', '\\"')

# Compose JSON string literal from Python string
def json_string(s: str) -> str:
    return '"' + json_string_escape(s) + '"'

# Compose JSON array of strings
def json_string_array(lst) -> str:
    return '[' + ','.join(json_string(s) for s in lst) + ']'

# Compose JSON null literal
json_null = "null"

# Compose JSON integer or double literal from Python int or float
def json_number(n) -> str:
    # For int, just str
    if isinstance(n, int):
        return str(n)
    # For float, format with decimal point or exponent
    # Use repr to preserve exact float value
    return repr(n)

# Compose JSON boolean literal
json_true = "true"
json_false = "false"

# Compose JSON object from dict of key->value strings (already JSON encoded)
def json_object(d: dict) -> str:
    # keys are strings, values are JSON text strings
    # keys must be JSON strings
    items = []
    for k, v in d.items():
        items.append(json_string(k) + ':' + v)
    return '{' + ','.join(items) + '}'

# Compose a record JSON text from components
def compose_record_json(
    id_json: str,
    amount_json: str,
    name_json: str or None,
    status_json: str,
    tags_json: str or None,
    child_json: str or None,
) -> str:
    d = {
        "id": id_json,
        "amount": amount_json,
        "status": status_json,
    }
    # name is nullable, missing allowed
    if name_json is not None:
        d["name"] = name_json
    # tags is array of strings, can be missing (to trigger built_value acceptance difference)
    if tags_json is not None:
        d["tags"] = tags_json
    # child is nullable record, missing allowed
    if child_json is not None:
        d["child"] = child_json
    return json_object(d)

# Compose status JSON string (one of "active", "inactive", "unknown")
status_values = ["active", "inactive", "unknown"]

# Compose amount JSON string (always string)
amount_examples = ["0", "123.45", "-987.65", "1e10", "0.0001"]

# Compose name JSON string or null or missing
# missing handled by None

# Compose tags JSON array of strings or missing
# missing handled by None

# Compose child JSON record or null or missing
# missing handled by None

# Compose id JSON number (int or double)
# We produce int64 boundary values and out-of-range double values to test divergence
# int64 range: -2**63 .. 2**63-1
INT64_MIN = -2**63
INT64_MAX = 2**63 - 1

@st.composite
def generated_json(draw) -> bytes:
    # Compose id as int or double near boundaries or out-of-range
    id_choice = draw(st.integers(min_value=0, max_value=9))
    if id_choice == 0:
        # normal int in safe range
        id_val = draw(st.integers(min_value=0, max_value=1000))
        id_json = json_number(id_val)
    elif id_choice == 1:
        # int64 max boundary
        id_val = INT64_MAX
        id_json = json_number(id_val)
    elif id_choice == 2:
        # int64 min boundary
        id_val = INT64_MIN
        id_json = json_number(id_val)
    elif id_choice == 3:
        # double representing int64 max + 1 (out of int64 range)
        # jsonDecode produces double, toInt() saturates
        id_val = float(INT64_MAX) + 1.0
        id_json = json_number(id_val)
    elif id_choice == 4:
        # double representing int64 min - 1 (out of int64 range)
        id_val = float(INT64_MIN) - 1.0
        id_json = json_number(id_val)
    elif id_choice == 5:
        # double non-integer (should be rejected by manual and built_value)
        id_val = draw(st.floats(min_value=0.1, max_value=1000.9, allow_nan=False, allow_infinity=False))
        id_json = json_number(id_val)
    else:
        # normal int small
        id_val = draw(st.integers(min_value=0, max_value=100))
        id_json = json_number(id_val)

    # amount always string, pick from examples or generate decimal string
    amount_val = draw(st.one_of(st.sampled_from(amount_examples), st.decimals(min_value=-1e6, max_value=1e6, places=4).map(lambda d: format(d, 'f'))))
    amount_json = json_string(amount_val)

    # status one of allowed strings
    status_val = draw(st.sampled_from(status_values))
    status_json = json_string(status_val)

    # name nullable string or missing
    name_present = draw(st.booleans())
    if name_present:
        # string or null
        name_null = draw(st.booleans())
        if name_null:
            name_json = json_null
        else:
            # simple string
            name_str = draw(st.text(min_size=0, max_size=10))
            name_json = json_string(name_str)
    else:
        name_json = None  # missing

    # tags array of strings or missing (to trigger built_value acceptance difference)
    tags_present = draw(st.booleans())
    if tags_present:
        # array of 0 to 3 strings
        tags_len = draw(st.integers(min_value=0, max_value=3))
        tags_list = []
        for _ in range(tags_len):
            s = draw(st.text(min_size=0, max_size=10))
            tags_list.append(s)
        tags_json = json_string_array(tags_list)
    else:
        tags_json = None  # missing

    # child nullable record or missing
    child_present = draw(st.booleans())
    if child_present:
        # child is null or nested record (one level only)
        child_null = draw(st.booleans())
        if child_null:
            child_json = json_null
        else:
            # nested record with no further recursion (child.child missing)
            # Compose nested record fields similarly but simpler (no further child)
            # id nested int in safe range
            child_id_val = draw(st.integers(min_value=0, max_value=1000))
            child_id_json = json_number(child_id_val)
            # amount nested string
            child_amount_val = draw(st.sampled_from(amount_examples))
            child_amount_json = json_string(child_amount_val)
            # status nested
            child_status_val = draw(st.sampled_from(status_values))
            child_status_json = json_string(child_status_val)
            # name nested nullable string or missing
            child_name_present = draw(st.booleans())
            if child_name_present:
                child_name_null = draw(st.booleans())
                if child_name_null:
                    child_name_json = json_null
                else:
                    child_name_str = draw(st.text(min_size=0, max_size=10))
                    child_name_json = json_string(child_name_str)
            else:
                child_name_json = None
            # tags nested present or missing
            child_tags_present = draw(st.booleans())
            if child_tags_present:
                child_tags_len = draw(st.integers(min_value=0, max_value=3))
                child_tags_list = []
                for _ in range(child_tags_len):
                    s = draw(st.text(min_size=0, max_size=10))
                    child_tags_list.append(s)
                child_tags_json = json_string_array(child_tags_list)
            else:
                child_tags_json = None
            # child.child missing (no recursion)
            child_child_json = None

            child_json = compose_record_json(
                id_json=child_id_json,
                amount_json=child_amount_json,
                name_json=child_name_json,
                status_json=child_status_json,
                tags_json=child_tags_json,
                child_json=child_child_json,
            )
    else:
        child_json = None  # missing

    # Compose top-level record JSON text
    top_json = compose_record_json(
        id_json=id_json,
        amount_json=amount_json,
        name_json=name_json,
        status_json=status_json,
        tags_json=tags_json,
        child_json=child_json,
    )

    # Return bytes (UTF-8)
    return top_json.encode("utf-8")