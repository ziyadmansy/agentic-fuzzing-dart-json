from hypothesis import strategies as st
import json

# We produce syntactically valid JSON objects matching the schema,
# but vary one or two fields at a time to be slightly off:
# - fields with wrong types (e.g. "id" as string, "amount" as number)
# - fields missing (omitted) or null where not expected
# - enum "status" with invalid strings
# - "tags" as non-array or array with non-string elements
# - "child" as null, valid record, or invalid type
#
# We keep the structure mostly valid, with bounded recursion (depth 1 child only).
# This should maximize chances of behavioral divergence between the four deserializers.

# Base valid values for fields
valid_id = st.integers(min_value=0, max_value=2**31-1)
valid_amount = st.text(min_size=1, max_size=20)
valid_name = st.one_of(st.none(), st.text(min_size=0, max_size=20))
valid_status = st.sampled_from(["active", "inactive", "unknown"])
valid_tags = st.lists(st.text(min_size=0, max_size=10), min_size=0, max_size=5)

# To create "almost valid" but slightly off values, define variants per field:

# id variants: valid int, or stringified int, or float, or null (invalid)
id_variants = st.one_of(
    valid_id,
    st.text(min_size=1, max_size=10).filter(lambda s: not s.isdigit()),  # non-digit string
    st.floats(allow_infinity=False, allow_nan=False),
    st.none(),
)

# amount variants: valid string, or number, or null
amount_variants = st.one_of(
    valid_amount,
    valid_id,  # number instead of string
    st.none(),
)

# name variants: valid string or null, or number (invalid)
name_variants = st.one_of(
    valid_name,
    valid_id,
)

# status variants: valid enum, or invalid string, or null
status_variants = st.one_of(
    valid_status,
    st.text(min_size=1, max_size=10).filter(lambda s: s not in ["active", "inactive", "unknown"]),
    st.none(),
)

# tags variants: valid list of strings, or list with non-string elements, or string, or null
tags_variants = st.one_of(
    valid_tags,
    st.lists(st.one_of(st.integers(), st.booleans(), st.none()), min_size=1, max_size=3),
    st.text(min_size=1, max_size=10),
    st.none(),
)

# child variants: null, valid record (depth 1), or invalid types (string, number, bool)
# We'll define a helper for valid record without child to avoid deep recursion
def valid_record_no_child():
    return st.fixed_dictionaries({
        "id": valid_id,
        "amount": valid_amount,
        "name": valid_name,
        "status": valid_status,
        "tags": valid_tags,
        "child": st.none(),
    })

child_variants = st.one_of(
    st.none(),
    valid_record_no_child(),
    st.text(min_size=1, max_size=10),
    valid_id,
    st.booleans(),
)

# Compose the full record with one or two fields replaced by variants to induce divergence
@st.composite
def generated_json(draw) -> bytes:
    # Start from a valid record
    base = {
        "id": draw(valid_id),
        "amount": draw(valid_amount),
        "name": draw(valid_name),
        "status": draw(valid_status),
        "tags": draw(valid_tags),
        "child": draw(child_variants),
    }

    # Choose 0, 1 or 2 fields to replace with variant (possibly invalid) values
    fields = ["id", "amount", "name", "status", "tags", "child"]
    n_variants = draw(st.integers(min_value=0, max_value=2))
    fields_to_modify = draw(st.sampled_from(fields).flatmap(
        lambda f: st.lists(st.just(f), min_size=n_variants, max_size=n_variants)
    )) if n_variants > 0 else []

    # Replace chosen fields with variant values
    for f in fields_to_modify:
        if f == "id":
            base[f] = draw(id_variants)
        elif f == "amount":
            base[f] = draw(amount_variants)
        elif f == "name":
            base[f] = draw(name_variants)
        elif f == "status":
            base[f] = draw(status_variants)
        elif f == "tags":
            base[f] = draw(tags_variants)
        elif f == "child":
            base[f] = draw(child_variants)

    # Serialize to JSON bytes
    return json.dumps(base).encode("utf-8")