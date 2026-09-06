from hypothesis import strategies as st

# Helper to produce a JSON string literal with proper escaping of quotes and backslashes
def json_string_literal(s: str) -> str:
    # Escape backslash and double quote for JSON string literal
    s = s.replace('\\', '\\\\').replace('"', '\\"')
    return f'"{s}"'

# Helper to produce JSON array of strings
def json_array_of_strings(lst) -> str:
    return "[" + ",".join(json_string_literal(s) for s in lst) + "]"

# Helper to produce JSON enum string for status, including some invalid variants for bad_enum
valid_statuses = ["active", "inactive", "unknown"]
invalid_statuses = ["Active", "INACTIVE", "unkn0wn", "null", ""]

@st.composite
def json_status(draw) -> str:
    # Bias towards valid, but sometimes produce invalid enum strings
    use_invalid = draw(st.booleans())
    if use_invalid:
        s = draw(st.sampled_from(invalid_statuses))
    else:
        s = draw(st.sampled_from(valid_statuses))
    return json_string_literal(s)

# Helper to produce id near 53-bit boundary or normal int
@st.composite
def json_id(draw) -> str:
    # 53-bit safe integer max is 2**53 - 1 = 9007199254740991
    # We'll produce some near boundary, some normal small ints, some large ints
    choice = draw(st.integers(min_value=0, max_value=3))
    if choice == 0:
        # small int
        v = draw(st.integers(min_value=0, max_value=10000))
    elif choice == 1:
        # near 53-bit boundary
        v = draw(st.integers(min_value=9007199254740980, max_value=9007199254741000))
    elif choice == 2:
        # just above 53-bit boundary (unsafe for JS number)
        v = draw(st.integers(min_value=9007199254741001, max_value=9007199254741100))
    else:
        # very large int (64-bit boundary)
        v = draw(st.integers(min_value=2**63 - 10, max_value=2**63 + 10))
    return str(v)

# Helper to produce amount string, sometimes invalid numeric strings or null override
@st.composite
def json_amount(draw) -> str:
    # amount is string, normally numeric string, but sometimes invalid or null override
    choice = draw(st.integers(min_value=0, max_value=4))
    if choice == 0:
        # normal numeric string
        v = draw(st.floats(min_value=0, max_value=1e6, allow_nan=False, allow_infinity=False))
        s = f"{v:.2f}"
    elif choice == 1:
        # numeric string but with leading zeros or plus sign
        v = draw(st.integers(min_value=0, max_value=9999))
        s = f"+{v:05d}"
    elif choice == 2:
        # invalid numeric string (letters)
        s = draw(st.text(min_size=1, max_size=5, alphabet=st.characters(blacklist_characters='"\\')))
    elif choice == 3:
        # empty string
        s = ""
    else:
        # null override (normally required string but null override)
        # We'll encode null as literal null (not string)
        return "null"
    return json_string_literal(s)

# Helper to produce name field: string or null, sometimes empty string or unusual unicode
@st.composite
def json_name(draw) -> str:
    choice = draw(st.integers(min_value=0, max_value=3))
    if choice == 0:
        # null
        return "null"
    elif choice == 1:
        # normal ascii string
        s = draw(st.text(min_size=1, max_size=10, alphabet=st.characters(blacklist_characters='"\\')))
        return json_string_literal(s)
    elif choice == 2:
        # empty string
        return '""'
    else:
        # unicode string with some escapes
        s = draw(st.text(min_size=1, max_size=10))
        return json_string_literal(s)

# Helper to produce tags array: array of strings, sometimes empty, sometimes with empty string elements
@st.composite
def json_tags(draw) -> str:
    # array of strings, length 0 to 5
    length = draw(st.integers(min_value=0, max_value=5))
    tags = []
    for _ in range(length):
        choice = draw(st.integers(min_value=0, max_value=2))
        if choice == 0:
            # normal ascii string tag
            s = draw(st.text(min_size=1, max_size=8, alphabet=st.characters(blacklist_characters='"\\')))
            tags.append(json_string_literal(s))
        elif choice == 1:
            # empty string tag
            tags.append('""')
        else:
            # unicode string tag
            s = draw(st.text(min_size=1, max_size=8))
            tags.append(json_string_literal(s))
    return "[" + ",".join(tags) + "]"

# Recursive generator for child field, depth limited to 1 normally, sometimes null override
@st.composite
def json_child(draw, depth=0) -> str:
    # null override or nested record (one level max)
    if depth >= 1:
        # only null allowed at depth limit
        return "null"
    choice = draw(st.integers(min_value=0, max_value=3))
    if choice == 0:
        # null
        return "null"
    elif choice == 1:
        # nested record with normal fields, but with some null overrides or bad enums inside
        # We'll build a nested record with depth=1
        # Use all helpers but with some bias towards null_override or bad_enum
        id_val = draw(json_id())
        amount_val = draw(json_amount())
        name_val = draw(json_name())
        status_val = draw(json_status())
        tags_val = draw(json_tags())
        # child at depth=1 must be null
        child_val = "null"
        return (
            "{" +
            f'"id":{id_val},'
            f'"amount":{amount_val},'
            f'"name":{name_val},'
            f'"status":{status_val},'
            f'"tags":{tags_val},'
            f'"child":{child_val}'
            "}"
        )
    elif choice == 2:
        # nested record with missing fields (should not happen normally, but let's produce valid JSON with all fields)
        # We'll produce all fields but with some null_override or bad_enum to simulate missing or wrong type
        id_val = draw(json_id())
        amount_val = draw(json_amount())
        name_val = draw(json_name())
        status_val = draw(json_status())
        tags_val = draw(json_tags())
        child_val = "null"
        return (
            "{" +
            f'"id":{id_val},'
            f'"amount":{amount_val},'
            f'"name":{name_val},'
            f'"status":{status_val},'
            f'"tags":{tags_val},'
            f'"child":{child_val}'
            "}"
        )
    else:
        # null override
        return "null"

@st.composite
def generated_json(draw) -> bytes:
    # Compose top-level record with all six fields always present
    # Bias towards null_override and bad_enum and boundary_id to maximize divergence
    id_val = draw(json_id())
    amount_val = draw(json_amount())
    name_val = draw(json_name())
    status_val = draw(json_status())
    tags_val = draw(json_tags())
    child_val = draw(json_child(depth=0))

    # Compose JSON object string
    json_obj = (
        "{" +
        f'"id":{id_val},'
        f'"amount":{amount_val},'
        f'"name":{name_val},'
        f'"status":{status_val},'
        f'"tags":{tags_val},'
        f'"child":{child_val}'
        "}"
    )
    return json_obj.encode("utf-8")