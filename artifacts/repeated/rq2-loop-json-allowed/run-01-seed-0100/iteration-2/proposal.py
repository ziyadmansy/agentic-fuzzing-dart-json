from hypothesis import strategies as st
import json

# Allowed status values
STATUS_VALUES = ["active", "inactive", "unknown"]

# Base record fields except child
base_record_fields = {
    "id": st.integers(min_value=-(2**31), max_value=2**31-1),
    "amount": st.text(min_size=0, max_size=20),
    "name": st.one_of(st.none(), st.text(min_size=0, max_size=20)),
    "status": st.sampled_from(STATUS_VALUES),
    "tags": st.lists(st.text(min_size=0, max_size=10), max_size=5),
}

# To produce "almost valid" but with one or two fields off, we define a helper
# that for each field can produce either a valid value or a "nearby" invalid value.
# We will pick exactly one or two fields to be "off" per record.

# For each field, define a strategy of "valid or near-invalid" values:
def id_near_invalid():
    # valid int or stringified int or float or null (invalid)
    return st.one_of(
        st.integers(min_value=-(2**31), max_value=2**31-1),
        st.text(min_size=1, max_size=10).filter(lambda s: not s.isdigit()),  # string non-digit
        st.floats(allow_nan=False, allow_infinity=False),
        st.none(),
    )

def amount_near_invalid():
    # valid string or int or empty list or null
    return st.one_of(
        st.text(min_size=0, max_size=20),
        st.integers(),
        st.lists(st.integers(), max_size=3),
        st.none(),
    )

def name_near_invalid():
    # valid string or null or int or bool
    return st.one_of(
        st.none(),
        st.text(min_size=0, max_size=20),
        st.integers(),
        st.booleans(),
    )

def status_near_invalid():
    # valid status or uppercase or misspelled or int or null
    return st.one_of(
        st.sampled_from(STATUS_VALUES),
        st.sampled_from([s.upper() for s in STATUS_VALUES]),
        st.sampled_from(["activ", "inactiv", "unknwn"]),
        st.integers(),
        st.none(),
    )

def tags_near_invalid():
    # valid list of strings or list of ints or string or null
    return st.one_of(
        st.lists(st.text(min_size=0, max_size=10), max_size=5),
        st.lists(st.integers(), max_size=5),
        st.text(min_size=0, max_size=10),
        st.none(),
    )

# For child, we allow null or a nested record with one level recursion.
# We will limit recursion depth to 1.
# For child, we produce either:
# - None (valid)
# - valid nested record (all fields valid)
# - nested record with one field off (like top-level)

# We'll define a helper to produce a valid record dict (no off fields)
def valid_record():
    return st.fixed_dictionaries({
        "id": base_record_fields["id"],
        "amount": base_record_fields["amount"],
        "name": base_record_fields["name"],
        "status": base_record_fields["status"],
        "tags": base_record_fields["tags"],
        "child": st.none(),
    })

# Helper to produce a record with exactly one field off (except child)
def record_one_field_off():
    # Pick one field to be off (id, amount, name, status, tags)
    off_field = st.sampled_from(["id", "amount", "name", "status", "tags"])
    # For each field, choose near_invalid or valid depending on off_field
    def fields_strategy(off):
        fields = {}
        for f in ["id", "amount", "name", "status", "tags"]:
            if f == off:
                if f == "id":
                    fields[f] = id_near_invalid()
                elif f == "amount":
                    fields[f] = amount_near_invalid()
                elif f == "name":
                    fields[f] = name_near_invalid()
                elif f == "status":
                    fields[f] = status_near_invalid()
                elif f == "tags":
                    fields[f] = tags_near_invalid()
            else:
                fields[f] = base_record_fields[f]
        # child is always None here for simplicity
        fields["child"] = st.none()
        return st.fixed_dictionaries(fields)
    return off_field.flatmap(fields_strategy)

# For child field, we produce either None or a nested record with zero or one field off
def child_strategy():
    # 70% None, 15% valid nested, 15% nested with one field off
    return st.one_of(
        st.none(),
        valid_record(),
        record_one_field_off(),
    )

@st.composite
def generated_json(draw) -> bytes:
    # We produce a top-level record with:
    # - either fully valid
    # - or exactly one or two fields off (including child)
    # We want to maximize chance of divergence by varying one or two fields only.

    # Decide how many fields off: 0 (valid), 1, or 2
    off_count = draw(st.sampled_from([0, 1, 2]))

    # All fields including child
    all_fields = ["id", "amount", "name", "status", "tags", "child"]

    # Pick which fields are off if off_count > 0
    off_fields = draw(st.lists(st.sampled_from(all_fields), min_size=off_count, max_size=off_count, unique=True)) if off_count > 0 else []

    fields = {}

    # For each field, decide value depending on if it's off or not
    for f in all_fields:
        if f in off_fields:
            # Off field: produce near_invalid or nested off for child
            if f == "id":
                fields[f] = draw(id_near_invalid())
            elif f == "amount":
                fields[f] = draw(amount_near_invalid())
            elif f == "name":
                fields[f] = draw(name_near_invalid())
            elif f == "status":
                fields[f] = draw(status_near_invalid())
            elif f == "tags":
                fields[f] = draw(tags_near_invalid())
            elif f == "child":
                # child off: nested record with one field off or invalid types
                # 50% chance nested with one field off, 50% chance invalid type (int, string, bool)
                child_val = draw(st.one_of(
                    record_one_field_off(),
                    st.integers(),
                    st.text(min_size=1, max_size=10),
                    st.booleans(),
                    st.none(),
                ))
                fields[f] = child_val
        else:
            # Valid field
            if f == "child":
                # child valid: None or valid nested record (70% None, 30% valid nested)
                fields[f] = draw(st.one_of(st.none(), valid_record()))
            else:
                fields[f] = draw(base_record_fields[f])

    # Compose dict and serialize to JSON bytes
    json_text = json.dumps(fields, ensure_ascii=False)
    return json_text.encode("utf-8")