from hypothesis import strategies as st

# Allowed status values
_status_values = st.sampled_from(['"active"', '"inactive"', '"unknown"'])

# Helper to produce a JSON string literal with quotes, allowing null as well
_string_or_null = st.one_of(
    st.text(min_size=0, max_size=20).map(lambda s: '"' + s.replace('"', '\\"') + '"'),
    st.just("null"),
)

# Helper to produce a JSON array of strings (possibly empty)
_tags_array = st.lists(
    st.text(min_size=0, max_size=10).map(lambda s: '"' + s.replace('"', '\\"') + '"'),
    min_size=0,
    max_size=5,
).map(lambda lst: "[" + ",".join(lst) + "]")

# To avoid infinite recursion, limit depth to 1 for child
# We'll define a recursive strategy with max depth 1

@st.composite
def record(draw, depth=0):
    # id: integer as JSON number (no quotes)
    # amount: string (quoted)
    # name: string or null
    # status: one of the three strings (quoted)
    # tags: array of strings
    # child: either null or a record (only if depth == 0)
    id_val = draw(st.integers(min_value=-2**31, max_value=2**31-1))
    amount_val = draw(_string_or_null)  # amount is string, but allow null to induce divergence
    # We allow amount to be null sometimes to test divergence (amount should be string)
    # But per schema, amount is always string, so null is "almost" well-formed but off by one type

    # For name, allow null or string (per schema)
    name_val = draw(_string_or_null)

    # status must be one of the three strings, but we can also try to inject a wrong type sometimes
    # To induce divergence, sometimes produce a string, sometimes a number, sometimes null
    # But mostly keep it correct to avoid universal rejection
    status_val = draw(
        st.one_of(
            _status_values,
            st.integers(min_value=-10, max_value=10).map(str),  # number as string, invalid type
            st.just("null"),
        )
    )

    tags_val = draw(_tags_array)

    if depth == 0:
        # child: null or record(depth=1)
        child_null = st.just("null")
        child_record = record(depth=1)
        child_val = draw(st.one_of(child_null, child_record))
    else:
        # max depth reached, child must be null
        child_val = "null"

    # Compose JSON object text:
    # We deliberately vary field order sometimes to test parser robustness
    fields = [
        ('"id"', str(id_val)),
        ('"amount"', amount_val),
        ('"name"', name_val),
        ('"status"', status_val),
        ('"tags"', tags_val),
        ('"child"', child_val),
    ]

    # Shuffle fields order sometimes to induce divergence in parsers sensitive to order
    # But Hypothesis st.lists(...).map(...) is simpler than shuffle, so just keep fixed order

    json_obj = "{" + ",".join(f"{k}:{v}" for k, v in fields) + "}"
    return json_obj

@st.composite
def generated_json(draw) -> bytes:
    # Draw one record at top level
    json_text = draw(record(depth=0))
    return json_text.encode("utf-8")