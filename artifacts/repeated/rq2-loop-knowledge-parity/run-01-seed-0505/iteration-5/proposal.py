from hypothesis import strategies as st

# Helper: JSON string escaping for a limited safe subset (no control chars, no quotes inside)
# We'll generate simple ASCII strings without quotes or backslashes to avoid escaping complexity.
json_string_safe = st.text(
    alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs'),
        blacklist_characters='"\\'
    ),
    min_size=0,
    max_size=10,
)

# JSON string with explicit "null" literal or string or omitted (for nullable fields)
nullable_string = st.one_of(st.just("null"), json_string_safe.map(lambda s: f'"{s}"'))

# JSON array of strings (tags)
json_array_of_strings = st.lists(json_string_safe, min_size=0, max_size=5).map(
    lambda lst: "[" + ",".join(f'"{s}"' for s in lst) + "]"
)

# JSON enum for status
status_values = ["\"active\"", "\"inactive\"", "\"unknown\""]

# JSON number as integer literal or as double literal (to trigger int/double differences)
# We want to produce integers in range and also out-of-range to trigger built_value vs others
# Also produce doubles that represent integers (e.g. 1.0) to trigger toInt() acceptance in some.
# Use strings for numbers to avoid importing json or formatting floats with repr.
def json_number(draw):
    # Choose one of:
    # - int in int64 range (safe)
    # - int outside int64 range (large)
    # - double representing int (e.g. 1.0)
    # - double non-integer (e.g. 1.5)
    choice = draw(st.integers(min_value=0, max_value=3))
    if choice == 0:
        # int in int64 range
        v = draw(st.integers(min_value=-(2**63), max_value=2**63 - 1))
        return str(v)
    elif choice == 1:
        # int outside int64 range (large positive or negative)
        v = draw(st.one_of(
            st.integers(min_value=2**63, max_value=2**63 + 1000),
            st.integers(min_value=-(2**63) - 1000, max_value=-(2**63) - 1),
        ))
        return str(v)
    elif choice == 2:
        # double representing int (e.g. 42.0)
        v = draw(st.integers(min_value=-(2**63), max_value=2**63 - 1))
        return f"{v}.0"
    else:
        # double non-integer (e.g. 1.5)
        whole = draw(st.integers(min_value=-1000, max_value=1000))
        frac = draw(st.integers(min_value=1, max_value=9))
        return f"{whole}.{frac}"

# JSON null literal or object or omitted for nullable child
# We'll produce either null or a nested record (one level recursion)
# To avoid infinite recursion, limit depth to 1
@st.composite
def json_record(draw, allow_missing_tags=False, depth=0):
    # id: integer or double (to trigger divergence)
    id_val = draw(json_number())
    # amount: string (always present)
    amount_val = draw(json_string_safe).replace('"', '')  # no quotes inside
    amount_val = f'"{amount_val}"'
    # name: nullable string or null literal or omitted (nullable)
    # We always include name field (never omit) to keep close to well-formed
    name_val = draw(st.one_of(
        st.just("null"),
        json_string_safe.map(lambda s: f'"{s}"')
    ))
    # status: one of the three strings or an invalid string to test rejection
    # But invalid status rejected by all, so no divergence there.
    # We'll produce only valid status here.
    status_val = draw(st.sampled_from(status_values))
    # tags: array of strings or missing (only built_value accepts missing)
    # To maximize divergence, sometimes omit tags
    omit_tags = False
    if allow_missing_tags:
        omit_tags = draw(st.booleans())
    if omit_tags:
        tags_val = None
    else:
        tags_val = draw(json_array_of_strings)
    # child: null or nested record (depth limited)
    if depth == 0:
        child_val = draw(st.one_of(
            st.just("null"),
            json_record(allow_missing_tags=True, depth=1).map(lambda s: s)
        ))
    else:
        child_val = draw(st.one_of(
            st.just("null"),
        ))

    # Compose JSON object fields as strings
    fields = []
    fields.append(f'"id":{id_val}')
    fields.append(f'"amount":{amount_val}')
    fields.append(f'"name":{name_val}')
    fields.append(f'"status":{status_val}')
    if tags_val is not None:
        fields.append(f'"tags":{tags_val}')
    # else omit tags field to trigger built_value acceptance divergence
    fields.append(f'"child":{child_val}')

    json_obj = "{" + ",".join(fields) + "}"
    return json_obj

@st.composite
def generated_json(draw) -> bytes:
    # Generate a top-level record with allow_missing_tags=True to get divergence on tags missing
    s = draw(json_record(allow_missing_tags=True))
    return s.encode("utf-8")