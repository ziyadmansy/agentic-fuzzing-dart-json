from hypothesis import strategies as st

# Constants for schema
STATUS_VALUES = ["active", "inactive", "unknown"]

# Helper: JSON string escaping for basic ASCII (no control chars, no unicode escapes)
def escape_json_string(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

# Helper: generate a JSON string or null
def json_string_or_null(draw, allow_null=True, min_len=0, max_len=20):
    if allow_null and draw(st.booleans()):
        return "null"
    # Try edge cases: empty, whitespace, special chars, numbers as string, etc.
    edge = draw(st.sampled_from([
        "", " ", "0", "-0", "NaN", "null", "true", "false", "1e10", "\"", "\\", "\n", "\r", "\t"
    ]))
    if draw(st.booleans()):
        return escape_json_string(edge)
    # Otherwise, random string
    s = draw(st.text(min_size=min_len, max_size=max_len))
    return escape_json_string(s)

# Helper: generate a JSON array of strings (possibly empty, possibly with edge cases)
def json_array_of_strings(draw, allow_empty=True, allow_nulls=False, max_len=5):
    arr = []
    n = draw(st.integers(min_value=0 if allow_empty else 1, max_value=max_len))
    for _ in range(n):
        if allow_nulls and draw(st.booleans()):
            arr.append("null")
        else:
            arr.append(json_string_or_null(draw, allow_null=False))
    return "[" + ", ".join(arr) + "]"

# Helper: generate a JSON integer (as a number, or as a string to provoke type confusion)
def json_id(draw):
    # Sometimes as integer, sometimes as string, sometimes as float
    kind = draw(st.integers(min_value=0, max_value=3))
    if kind == 0:
        # Normal integer
        return str(draw(st.integers(min_value=-2**31, max_value=2**31-1)))
    elif kind == 1:
        # As string
        return escape_json_string(str(draw(st.integers(min_value=-2**31, max_value=2**31-1))))
    elif kind == 2:
        # As float
        return str(draw(st.floats(allow_nan=False, allow_infinity=False, width=32)))
    else:
        # As string float
        return escape_json_string(str(draw(st.floats(allow_nan=False, allow_infinity=False, width=32))))

# Helper: generate a JSON value for "amount" (should be string, but try numbers, null, etc.)
def json_amount(draw):
    kind = draw(st.integers(min_value=0, max_value=3))
    if kind == 0:
        # Normal string
        return json_string_or_null(draw, allow_null=False)
    elif kind == 1:
        # As number
        return str(draw(st.floats(allow_nan=False, allow_infinity=False, width=32)))
    elif kind == 2:
        # As null
        return "null"
    else:
        # As boolean
        return "true" if draw(st.booleans()) else "false"

# Helper: generate a JSON value for "name" (string or null, but try numbers, bools, etc.)
def json_name(draw):
    kind = draw(st.integers(min_value=0, max_value=4))
    if kind == 0:
        return json_string_or_null(draw, allow_null=True)
    elif kind == 1:
        # As number
        return str(draw(st.integers(min_value=-100, max_value=100)))
    elif kind == 2:
        # As boolean
        return "true" if draw(st.booleans()) else "false"
    elif kind == 3:
        # As empty array
        return "[]"
    else:
        # As object
        return "{}"

# Helper: status field (should be one of three strings, but try null, number, etc.)
def json_status(draw):
    kind = draw(st.integers(min_value=0, max_value=3))
    if kind == 0:
        return escape_json_string(draw(st.sampled_from(STATUS_VALUES)))
    elif kind == 1:
        # As null
        return "null"
    elif kind == 2:
        # As number
        return str(draw(st.integers(min_value=0, max_value=10)))
    else:
        # As boolean
        return "true" if draw(st.booleans()) else "false"

# Helper: tags field (should be array of strings, but try null, array of numbers, etc.)
def json_tags(draw):
    kind = draw(st.integers(min_value=0, max_value=3))
    if kind == 0:
        return json_array_of_strings(draw, allow_empty=True, allow_nulls=True)
    elif kind == 1:
        # As null
        return "null"
    elif kind == 2:
        # As array of numbers
        arr = [str(draw(st.integers(min_value=-10, max_value=10))) for _ in range(draw(st.integers(0, 3)))]
        return "[" + ", ".join(arr) + "]"
    else:
        # As string
        return json_string_or_null(draw, allow_null=False)

# Helper: child field (should be null or a record, but try number, string, array, etc.)
def json_child(draw, depth):
    if depth <= 0:
        # Only null or object at max depth
        return "null" if draw(st.booleans()) else "{}"
    kind = draw(st.integers(min_value=0, max_value=4))
    if kind == 0:
        # Null
        return "null"
    elif kind == 1:
        # Valid record (recursive, but only one level)
        return draw(json_record(draw, depth=depth-1))
    elif kind == 2:
        # As number
        return str(draw(st.integers(min_value=-100, max_value=100)))
    elif kind == 3:
        # As string
        return json_string_or_null(draw, allow_null=False)
    else:
        # As array
        arr = [json_string_or_null(draw, allow_null=False) for _ in range(draw(st.integers(0, 2)))]
        return "[" + ", ".join(arr) + "]"

# Helper: randomly omit a field (to test missing fields vs. present-but-wrong)
def maybe_omit(draw, key, value, omit_chance=0.1):
    if draw(st.randoms()).random() < omit_chance:
        return None
    return f'"{key}": {value}'

# Main record generator
def json_record(draw, depth=1):
    # For each field, sometimes omit, sometimes present with wrong type
    fields = []
    # id
    v = json_id(draw)
    f = maybe_omit(draw, "id", v, omit_chance=0.05)
    if f is not None:
        fields.append(f)
    # amount
    v = json_amount(draw)
    f = maybe_omit(draw, "amount", v, omit_chance=0.05)
    if f is not None:
        fields.append(f)
    # name
    v = json_name(draw)
    f = maybe_omit(draw, "name", v, omit_chance=0.05)
    if f is not None:
        fields.append(f)
    # status
    v = json_status(draw)
    f = maybe_omit(draw, "status", v, omit_chance=0.05)
    if f is not None:
        fields.append(f)
    # tags
    v = json_tags(draw)
    f = maybe_omit(draw, "tags", v, omit_chance=0.05)
    if f is not None:
        fields.append(f)
    # child
    v = json_child(draw, depth)
    f = maybe_omit(draw, "child", v, omit_chance=0.05)
    if f is not None:
        fields.append(f)
    # Shuffle field order to provoke order sensitivity
    draw(st.randoms()).shuffle(fields)
    return "{" + ", ".join(fields) + "}"

@st.composite
def generated_json(draw) -> bytes:
    # Top-level record, depth=1 for child
    doc = draw(st.deferred(lambda: st.builds(lambda s: s.encode("utf-8"), st.just(draw(json_record(draw, depth=1))))))
    return doc