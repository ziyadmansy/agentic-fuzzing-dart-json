from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status field
    STATUS_VALUES = ["active", "inactive", "unknown"]

    # Base strategies for each field, producing JSON text fragments (strings)
    # id: produce either a valid int (in 64-bit range), or a double that looks like an int,
    # or a double outside 64-bit int range to trigger built_value vs others divergence.
    # Also produce id as a double with fractional part to cause rejection.
    def id_strategy():
        # 64-bit signed int range
        INT64_MIN = -2**63
        INT64_MAX = 2**63 - 1

        # Valid int as JSON integer literal
        valid_int = st.integers(min_value=INT64_MIN, max_value=INT64_MAX).map(str)

        # Double that is integral but out of int64 range (e.g. 2**63 as float)
        out_of_range_double = st.sampled_from([
            str(float(INT64_MAX) + 1.0),
            str(float(INT64_MIN) - 1.0)
        ])

        # Double with fractional part (e.g. 1.5)
        fractional_double = st.floats(allow_infinity=False, allow_nan=False, width=32).filter(
            lambda f: abs(f) < 1e10 and (f != int(f))
        ).map(lambda f: ('%.6f' % f).rstrip('0').rstrip('.'))

        # Compose weighted strategy to produce mostly valid ints but some doubles
        return st.one_of(
            valid_int,
            out_of_range_double,
            fractional_double,
        )

    # amount: always a JSON string, produce valid strings or empty string
    amount_strategy = st.text(min_size=1, max_size=10).map(lambda s: '"' + s.replace('"', '\\"') + '"')

    # name: nullable string or null
    name_strategy = st.one_of(
        st.none().map(lambda _: "null"),
        st.text(min_size=0, max_size=10).map(lambda s: '"' + s.replace('"', '\\"') + '"')
    )

    # status: one of allowed strings, or an unrecognized string to cause rejection
    # But mostly produce valid status to keep documents almost well-formed
    status_strategy = st.one_of(
        st.sampled_from(STATUS_VALUES).map(lambda s: '"' + s + '"'),
        # unrecognized status strings (rare)
        st.text(min_size=1, max_size=10).filter(lambda s: s not in STATUS_VALUES).map(lambda s: '"' + s.replace('"', '\\"') + '"')
    )

    # tags: array of strings, or missing (to trigger built_value silent default)
    # We want to vary presence and type:
    # - present with array of strings (possibly empty)
    # - missing entirely (to trigger divergence)
    # - present but wrong type (e.g. null or string) to cause rejection
    tags_present_array = st.lists(
        st.text(min_size=0, max_size=5).map(lambda s: '"' + s.replace('"', '\\"') + '"'),
        max_size=3
    ).map(lambda lst: '[' + ','.join(lst) + ']')

    tags_wrong_type = st.one_of(
        st.just("null"),
        st.text(min_size=0, max_size=5).map(lambda s: '"' + s.replace('"', '\\"') + '"'),
        st.integers().map(str)
    )

    # We want to produce mostly present with array, sometimes missing, sometimes wrong type
    tags_strategy = st.one_of(
        tags_present_array,
        st.just(None),  # missing
        tags_wrong_type
    )

    # child: nullable record or null or missing
    # To keep recursion bounded, child is either null or a record with no child (child=null)
    # or missing (accepted by all)
    # We produce child as:
    # - missing (omit field)
    # - null
    # - a record with child=null (one level recursion only)
    # We do not produce child with wrong type here to keep close to well-formed

    # Helper to produce a record JSON object string (no child or child=null)
    def record_no_child():
        # id
        id_val = draw(id_strategy())
        # amount
        amount_val = draw(amount_strategy)
        # name
        name_val = draw(name_strategy)
        # status
        status_val = draw(st.sampled_from(STATUS_VALUES)).map(lambda s: '"' + s + '"')
        status_val = draw(status_val)
        # tags (present with array)
        tags_val = draw(tags_present_array)
        # child=null
        child_val = "null"
        # Compose JSON object string
        return (
            '{'
            + '"id":' + id_val + ','
            + '"amount":' + amount_val + ','
            + '"name":' + name_val + ','
            + '"status":' + status_val + ','
            + '"tags":' + tags_val + ','
            + '"child":' + child_val
            + '}'
        )

    # Compose child field variants
    child_field = st.one_of(
        st.just(None),  # missing
        st.just("null"),
        record_no_child()
    )

    # Compose top-level fields, with possibility of missing tags or child
    # We vary presence of tags and child fields independently
    # id, amount, status always present (required)
    # name nullable, present always (nullable accepted missing but we keep present)
    # tags: present with array, missing, or wrong type
    # child: missing, null, or record_no_child

    # Draw required fields
    id_val = draw(id_strategy())
    amount_val = draw(amount_strategy)
    name_val = draw(name_strategy)
    status_val = draw(status_strategy)
    tags_val = draw(tags_strategy)
    child_val = draw(child_field)

    # Compose fields as list of (key, value) strings, omitting tags or child if None
    fields = [
        '"id":' + id_val,
        '"amount":' + amount_val,
        '"name":' + name_val,
        '"status":' + status_val,
    ]
    if tags_val is not None:
        fields.append('"tags":' + tags_val)
    # else tags missing

    if child_val is not None:
        fields.append('"child":' + child_val)
    # else child missing

    # Compose JSON object string
    json_str = '{' + ','.join(fields) + '}'

    # Return bytes
    return json_str.encode('utf-8')