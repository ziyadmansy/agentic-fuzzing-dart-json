from hypothesis import strategies as st

# Constants for fixed enums and limits
STATUS_VALUES = ['active', 'inactive', 'unknown']

# Helper to produce JSON string literals with proper escaping of quotes and backslashes
def json_string_literal(s: str) -> str:
    # Escape backslash and quote for JSON string literal
    # Hypothesis strings are unicode, but we keep it simple and escape only these two chars
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

# Helper to produce JSON arrays of strings
def json_array_of_strings(draw, min_size=0, max_size=5):
    strs = draw(st.lists(st.text(min_size=0, max_size=10), min_size=min_size, max_size=max_size))
    # Escape each string properly
    escaped = [json_string_literal(s) for s in strs]
    return '[' + ','.join(escaped) + ']'

# Helper to produce JSON null or a nested record (one level recursion)
# We'll limit recursion depth to 1 as per spec
@st.composite
def json_record(draw, allow_null=True, depth=0):
    # id: integer or double (to trigger divergence)
    # We want to produce either:
    # - a true int within 64-bit range (manual and built_value accept)
    # - a double that is integral (json_serializable and freezed accept)
    # - a double outside int64 range (to test saturation behavior)
    # - a double non-integral (should be rejected by all)
    # We'll produce a union of these cases with weighted probabilities.

    # Define int64 limits
    INT64_MIN = -2**63
    INT64_MAX = 2**63 - 1

    # id strategy: one of
    # 1) int in int64 range
    # 2) float integral in int64 range (e.g. 1.0, 42.0)
    # 3) float integral outside int64 range (e.g. 2**65 as float)
    # 4) float non-integral (e.g. 1.5)
    id_case = draw(st.integers(min_value=1, max_value=4))
    if id_case == 1:
        # int in int64 range
        id_val = draw(st.integers(min_value=INT64_MIN, max_value=INT64_MAX))
        id_json = str(id_val)
    elif id_case == 2:
        # float integral in int64 range
        val = draw(st.integers(min_value=INT64_MIN, max_value=INT64_MAX))
        id_json = str(float(val))
    elif id_case == 3:
        # float integral outside int64 range
        # Use a large float beyond int64 range, e.g. 2**65
        val = float(2**65)
        id_json = str(val)
    else:
        # float non-integral
        val = draw(st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False))
        # Ensure non-integral by adding 0.5 if integral
        if val == int(val):
            val = val + 0.5
        id_json = str(val)

    # amount: string (always present)
    # We'll produce normal strings, but also test empty string and numeric strings
    amount_str = draw(st.one_of(
        st.text(min_size=1, max_size=10),
        st.just("0"),
        st.just("123.45"),
        st.just(""),
    ))
    amount_json = json_string_literal(amount_str)

    # name: nullable string, optional missing accepted by all
    # We always produce it (always present), but sometimes null or string
    name_choice = draw(st.one_of(st.none(), st.text(min_size=0, max_size=10)))
    if name_choice is None:
        name_json = "null"
    else:
        name_json = json_string_literal(name_choice)

    # status: one of allowed strings, or invalid string to test rejection
    # We produce mostly valid, but sometimes invalid to test rejection
    status_choice = draw(st.one_of(
        st.sampled_from(STATUS_VALUES),
        st.text(min_size=1, max_size=10).filter(lambda s: s not in STATUS_VALUES)
    ))
    status_json = json_string_literal(status_choice)

    # tags: array of strings, or missing (to test built_value accepting missing)
    # We produce either present array or missing field (empty list implied by built_value)
    tags_present = draw(st.booleans())
    if tags_present:
        tags_json = json_array_of_strings(draw, min_size=0, max_size=3)
    else:
        tags_json = None  # missing field

    # child: nullable record or null
    # We allow one level recursion only
    if depth == 0:
        child_choice = draw(st.one_of(
            st.none(),
            json_record(allow_null=True, depth=depth+1)
        ))
    else:
        # At depth 1, only null or no child (no further recursion)
        child_choice = draw(st.one_of(st.none()))

    if child_choice is None:
        child_json = "null"
    else:
        child_json = child_choice

    # Compose fields as JSON key:value pairs
    # Fields order: id, amount, name, status, tags (optional), child
    fields = []
    fields.append('"id":' + id_json)
    fields.append('"amount":' + amount_json)
    fields.append('"name":' + name_json)
    fields.append('"status":' + status_json)
    if tags_json is not None:
        fields.append('"tags":' + tags_json)
    # else omit tags field to test built_value behavior
    fields.append('"child":' + child_json)

    json_obj = '{' + ','.join(fields) + '}'
    return json_obj

@st.composite
def generated_json(draw) -> bytes:
    # Generate a JSON document string from json_record root
    s = draw(json_record())
    # Return as bytes UTF-8 encoded
    return s.encode('utf-8')