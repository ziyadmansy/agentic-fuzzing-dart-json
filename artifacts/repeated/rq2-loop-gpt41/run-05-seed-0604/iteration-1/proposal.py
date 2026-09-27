from hypothesis import strategies as st

# Constants for valid values
VALID_STATUSES = ["active", "inactive", "unknown"]

# Helper: JSON-escape a string (minimal, covers most cases for this schema)
def escape_json_string(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

# Helper: Generate a valid or slightly-off integer representation
def int_or_edge(draw):
    # Sometimes emit a valid integer, sometimes a float, string, or null
    kind = draw(st.integers(0, 9))
    if kind < 6:
        return str(draw(st.integers(-2**31, 2**31-1)))
    elif kind == 6:
        # float instead of int
        return str(draw(st.floats(-1e6, 1e6, allow_nan=False, allow_infinity=False)))
    elif kind == 7:
        # stringified int
        return escape_json_string(str(draw(st.integers(-2**31, 2**31-1))))
    elif kind == 8:
        # null
        return "null"
    else:
        # boolean
        return "true" if draw(st.booleans()) else "false"

# Helper: Generate a valid or slightly-off string for amount
def amount_or_edge(draw):
    kind = draw(st.integers(0, 7))
    if kind < 5:
        # Valid string
        s = draw(st.text(min_size=0, max_size=12))
        return escape_json_string(s)
    elif kind == 5:
        # Numeric value instead of string
        return str(draw(st.integers(-1000, 1000)))
    elif kind == 6:
        # null
        return "null"
    else:
        # boolean
        return "true" if draw(st.booleans()) else "false"

# Helper: Generate a valid, null, or edge-case string for name
def name_or_edge(draw):
    kind = draw(st.integers(0, 6))
    if kind < 4:
        # Valid string
        s = draw(st.text(min_size=0, max_size=10))
        return escape_json_string(s)
    elif kind == 4:
        # null
        return "null"
    elif kind == 5:
        # integer
        return str(draw(st.integers(-100, 100)))
    else:
        # boolean
        return "true" if draw(st.booleans()) else "false"

# Helper: Generate a valid or edge-case status
def status_or_edge(draw):
    kind = draw(st.integers(0, 7))
    if kind < 5:
        return escape_json_string(draw(st.sampled_from(VALID_STATUSES)))
    elif kind == 5:
        # Invalid string
        return escape_json_string(draw(st.text(min_size=1, max_size=8).filter(lambda x: x not in VALID_STATUSES)))
    elif kind == 6:
        # null
        return "null"
    else:
        # integer
        return str(draw(st.integers(-10, 10)))

# Helper: Generate a valid or edge-case tags array
def tags_or_edge(draw):
    kind = draw(st.integers(0, 7))
    if kind < 5:
        # Valid array of strings
        arr = [escape_json_string(draw(st.text(min_size=0, max_size=8))) for _ in range(draw(st.integers(0, 4)))]
        return "[" + ", ".join(arr) + "]"
    elif kind == 5:
        # Array with a non-string element
        arr = [escape_json_string(draw(st.text(min_size=0, max_size=8))) for _ in range(draw(st.integers(0, 2)))]
        arr.append(str(draw(st.integers(-10, 10))))
        return "[" + ", ".join(arr) + "]"
    elif kind == 6:
        # null
        return "null"
    else:
        # Not an array
        return escape_json_string(draw(st.text(min_size=0, max_size=8)))

# Helper: Generate a valid or edge-case child (recursion bounded)
def child_or_edge(draw, depth):
    kind = draw(st.integers(0, 6))
    if kind < 4 and depth < 1:
        # Valid child record (one level recursion)
        return generated_record(draw, depth=depth+1)
    elif kind == 4:
        # null
        return "null"
    elif kind == 5:
        # integer
        return str(draw(st.integers(-100, 100)))
    else:
        # string
        return escape_json_string(draw(st.text(min_size=0, max_size=8)))

# Helper: Generate a record as JSON string
def generated_record(draw, depth=0):
    # Randomize field order to stress implementations
    fields = [
        ('"id"', int_or_edge(draw)),
        ('"amount"', amount_or_edge(draw)),
        ('"name"', name_or_edge(draw)),
        ('"status"', status_or_edge(draw)),
        ('"tags"', tags_or_edge(draw)),
        ('"child"', child_or_edge(draw, depth)),
    ]
    draw(st.randoms())  # Advance RNG for field order
    draw(st.just(None))  # NOP, but helps with randomness
    order = draw(st.permutations(fields))
    return "{" + ", ".join(f"{k}: {v}" for k, v in order) + "}"

@st.composite
def generated_json(draw):
    # Top-level record
    json_str = generated_record(draw, depth=0)
    # Return as bytes
    return json_str.encode("utf-8")