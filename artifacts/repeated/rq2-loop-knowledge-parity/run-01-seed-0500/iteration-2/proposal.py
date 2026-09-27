```python
from hypothesis import strategies as st

# Constants for status field
STATUS_VALUES = ['"active"', '"inactive"', '"unknown"']

# Helper to produce a JSON string literal with proper escaping for Hypothesis-generated strings
def json_string_literal(s: str) -> str:
    # Escape backslash and double quote for JSON string literal
    # Also escape control characters minimally
    # Hypothesis strings are unicode, so we must escape properly
    # We'll do a minimal escape here for control chars and quotes/backslash
    def escape_char(c):
        o = ord(c)
        if c == '"':
            return '\\"'
        elif c == '\\':
            return '\\\\'
        elif o <= 0x1F:
            # Control characters escaped as \u00XX
            return '\\u%04x' % o
        else:
            return c
    return '"' + ''.join(escape_char(c) for c in s) + '"'

# Strategy for id field:
# To exploit the known difference:
# manual and built_value require true int (jsonDecode produces int for integer literals in range)
# json_serializable and freezed accept double and convert to int via toInt()
# jsonDecode turns integer literals outside 64-bit range into double
# toInt() saturates to int64 min/max instead of throwing
# So produce either:
# - a JSON integer literal in 64-bit range (accepted by all)
# - a JSON number literal outside 64-bit range (encoded as JSON number with decimal point to force double)
#   which manual and built_value reject, but json_serializable and freezed accept (with saturation)
# We'll produce either an integer literal or a floating point literal outside int64 range.
# int64 range: -2**63 to 2**63-1
INT64_MIN = -2**63
INT64_MAX = 2**63 - 1

# We'll produce either:
# - integer literal in [-2**53, 2**53] (safe JSON integer range)
# - floating point literal outside int64 range (e.g. 2**63 + 1.0)
# We must produce JSON text, so for floating point we must produce a number with decimal point or exponent.

# Strategy for id field JSON text:
id_int64_safe = st.integers(min_value=-(2**53), max_value=2**53).map(str)
# Floating point outside int64 range, e.g. 2**63 + 1.0 or -2**63 - 1.0
# We'll produce a float literal string with decimal point or exponent to force double
def float_outside_int64():
    # Pick sign
    sign = st.sampled_from(['', '-'])
    # Pick magnitude > 2**63
    # Use decimal notation with .0 to force double
    # We'll pick from [2**63 + 1, 2**64] range
    mag = st.integers(min_value=2**63 + 1, max_value=2**64)
    return st.tuples(sign, mag).map(lambda t: t[0] + str(t[1]) + '.0')
id_float_outside_int64 = float_outside_int64()

id_json_text = st.one_of(id_int64_safe, id_float_outside_int64)

# amount: string, always present, non-null
# We'll produce a non-empty string, possibly numeric-looking or arbitrary
amount_str = st.text(min_size=1).map(json_string_literal)

# name: nullable string or null
name_str = st.one_of(st.none(), st.text()).map(
    lambda v: "null" if v is None else json_string_literal(v)
)

# status: one of "active", "inactive", "unknown"
status_str = st.sampled_from(STATUS_VALUES)

# tags: array of strings, always present (but can be empty)
# Each string can be empty or non-empty
tags_array = st.lists(st.text()).map(
    lambda lst: '[' + ','.join(json_string_literal(s) for s in lst) + ']'
)

# child: nullable Record or null, one level of recursion normally
# We'll limit recursion depth to 1 (child can be null or a record with child=null)
# To avoid infinite recursion, we define a helper function with depth param

def record_json(depth: int) -> st.SearchStrategy[str]:
    # At depth 0, child must be null
    if depth <= 0:
        child_strat = st.just("null")
    else:
        # child can be null or a record with depth-1
        child_strat = st.one_of(
            st.just("null"),
            record_json(depth - 1)
        )
    # Compose fields except id separately to allow id_json_text
    # We'll produce a dict of fields as strings, then join
    # We want to produce "almost" well-formed documents with one or two fields off
    # But per instructions, vary one or two things at a time; here we produce a valid record,
    # the top-level strategy will vary fields for divergence

    # Compose fields as strategies
    fields = st.tuples(
        id_json_text,
        amount_str,
        name_str,
        status_str,
        tags_array,
        child_strat
    ).map(lambda t: {
        "id": t[0],
        "amount": t[1],
        "name": t[2],
        "status": t[3],
        "tags": t[4],
        "child": t[5]
    })

    # Map dict to JSON object text
    def dict_to_json(d):
        # Compose JSON object text with keys in fixed order
        # keys: id, amount, name, status, tags, child
        parts = []
        parts.append('"id":' + d["id"])
        parts.append('"amount":' + d["amount"])
        parts.append('"name":' + d["name"])
        parts.append('"status":' + d["status"])
        parts.append('"tags":' + d["tags"])
        parts.append('"child":' + d["child"])
        return '{' + ','.join(parts) + '}'

    return fields.map(dict_to_json)

# Now the top-level strategy generated_json(draw) -> bytes
# We want to produce syntactically valid JSON objects only
# We want to vary one or two things about an otherwise valid document at a time,
# to maximize disagreement.

# Known divergences:
# - tags missing: built_value accepts, others reject
# - id as double outside int64 range: manual and built_value reject, others accept
# - name or child missing: all accept
# - unknown extra keys: all accept
# - wrong type or null for non-nullable: all reject with different exceptions (no divergence)
# - unrecognized status string: all reject

# So we can produce:
# - valid record with all fields present and correct types (baseline)
# - record missing tags field (to trigger built_value accept, others reject)
# - record with id as double outside int64 range (to trigger manual/built_value reject, others accept)
# - record with tags present but wrong type (e.g. string instead of array) (all reject, no divergence)
# - record with extra unknown key (all accept, no divergence)
# - record with name or child missing (all accept, no divergence)
# - record with null for non-nullable (all reject, no divergence)
# - record with status invalid string (all reject, no divergence)

# We'll produce a mixture of:
# - baseline valid record (all fields present, correct types)
# - record missing tags field (to get divergence)
# - record with id as double outside int64 range (to get divergence)

# To produce missing tags field, we must produce JSON object text without "tags" key.
# To produce id as double outside int64 range, produce id field as float_outside_int64.

# We'll produce a top-level strategy that picks one of these three variants with weighted probabilities.

@st.composite
def generated_json(draw) -> bytes:
    variant = draw(st.sampled_from(["valid", "missing_tags", "id_double_out_of_range"]))

    # Base record with all fields present and valid
    base_record = draw(record_json(depth=1))

    if variant == "valid":
        # Just produce base_record as bytes
        return base_record.encode("utf-8")

    elif variant == "missing_tags":
        # Remove "tags" field from base_record JSON text
        # base_record is JSON object text with keys in fixed order:
        # {"id":..., "amount":..., "name":..., "status":..., "tags":..., "child":...}
        # We can parse by splitting on commas at top level (safe because values are JSON literals without commas except in arrays)
        # But tags value is an array which may contain commas, so splitting on commas is unsafe.
        # Instead, reconstruct the object with all fields except tags.

        # We'll parse base_record string manually to extract fields by key:
        # The keys are fixed and in order, so we can find the positions of keys and values by searching.

        # A simpler approach: regenerate a record with tags missing, but other fields same as base_record.

        # To do that, parse base_record string to extract field values by key:
        # We'll use a helper to extract JSON value for a given key from base_record string.

        def extract_field(json_text, key):
            # key is string like "id"
            # find '"key":' then parse value until next comma or closing brace at top level
            # values can be:
            # - number (digits, decimal point)
            # - string (quoted)
            # - null
            # - array (bracketed)
            # - object (braced)
            # We'll find start of value after '"key":'
            prefix = f'"{key}":'
            start = json_text.find(prefix)
            if start == -1:
                return None
            start += len(prefix)
            # parse value from start
            # skip whitespace
            while start < len(json_text) and json_text[start] in ' \t\n\r':
                start += 1
            # parse JSON value text from start
            # We'll parse a JSON value by counting brackets or quotes
            c = json_text[start]
            if c == '"':
                # string literal
                end = start + 1
                while end < len(json_text):
                    if json_text[end] == '"' and json_text[end - 1] != '\\':
                        break
                    end += 1
                return json_text[start:end+1]
            elif c == 'n':
                # null literal
                if json_text.startswith("null", start):
                    return "null"
                else:
                    return None
            elif c == '[':
                # array, find matching closing bracket
                depth = 1
                end = start + 1
                while end < len(json_text) and depth > 0:
                    if json_text[end] == '[':
                        depth += 1
                    elif json_text[end] == ']':
                        depth -= 1
                    end += 1
                return json_text[start:end]
            elif c == '{':
                # object, find matching closing brace
                depth = 1
                end = start + 1
                while end < len(json_text) and depth > 0:
                    if json_text[end] == '{':
                        depth += 1
                    elif json_text[end] == '}':
                        depth -= 1
                    end += 1
                return json_text[start:end]
            else:
                # number or boolean (not boolean in schema), parse until comma or }
                end = start
                while end < len(json_text) and json_text[end] not in