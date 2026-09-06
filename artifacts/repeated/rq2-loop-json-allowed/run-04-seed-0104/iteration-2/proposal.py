from hypothesis import strategies as st
import json

# We define a recursive strategy for the "child" field with bounded depth.
# The record schema:
# {
#   "id": <integer>,
#   "amount": <string>,
#   "name": <string or null>,
#   "status": <one of "active", "inactive", "unknown">,
#   "tags": <array of strings>,
#   "child": <Record or null, one level of recursion normally>
# }
#
# We will produce mostly well-formed documents but introduce subtle type
# divergences or boundary cases in one or two fields at a time.
#
# Examples of subtle divergences to try:
# - "id" as integer or as a stringified integer (some accept, some reject)
# - "amount" as string normally, but sometimes a number or null (some reject)
# - "name" as string or null normally, but sometimes a number or empty string
# - "status" as one of the three strings normally, but sometimes uppercase,
#   or a number, or null
# - "tags" as array of strings normally, but sometimes empty array, or array
#   with null or numbers, or a single string (not array)
# - "child" as null or a nested record, but sometimes a wrong type (string,
#   number), or missing (should always be present, but test missing)
#
# We vary one or two fields per document to maximize divergence.

# Base valid values for fields:
valid_status = st.sampled_from(["active", "inactive", "unknown"])
valid_id = st.integers(min_value=0, max_value=2**31-1)
valid_amount = st.text(min_size=1, max_size=20)
valid_name = st.one_of(st.none(), st.text(min_size=0, max_size=20))
valid_tags = st.lists(st.text(min_size=0, max_size=10), max_size=5)
# We'll limit recursion depth to 2
MAX_DEPTH = 2

def record_strategy(depth=0):
    # Base valid record
    base = st.fixed_dictionaries({
        "id": valid_id,
        "amount": valid_amount,
        "name": valid_name,
        "status": valid_status,
        "tags": valid_tags,
        "child": st.none() if depth >= MAX_DEPTH else st.deferred(lambda: record_strategy(depth+1)).or_else(st.none())
    })

    # Now create subtle variants for each field, one or two at a time.
    # We'll build a list of strategies that produce dicts with one or two fields altered.

    # Variants for "id":
    id_variants = st.one_of(
        valid_id,
        # id as stringified integer (should be rejected by some)
        valid_id.map(lambda i: str(i)),
        # id as float (should be rejected)
        valid_id.map(lambda i: float(i) + 0.5),
    )

    # Variants for "amount":
    amount_variants = st.one_of(
        valid_amount,
        # amount as number (should be rejected)
        st.integers(min_value=0, max_value=100000).map(str),  # keep as string but numeric string
        st.integers(min_value=0, max_value=100000),  # number type
        st.none(),
        st.just(""),  # empty string
    )

    # Variants for "name":
    name_variants = st.one_of(
        valid_name,
        st.integers(min_value=0, max_value=1000),  # number instead of string/null
        st.just(""),  # empty string
    )

    # Variants for "status":
    status_variants = st.one_of(
        valid_status,
        st.sampled_from(["ACTIVE", "INACTIVE", "UNKNOWN"]),  # uppercase variants
        st.integers(min_value=0, max_value=2),  # number instead of string
        st.none(),
    )

    # Variants for "tags":
    tags_variants = st.one_of(
        valid_tags,
        st.lists(st.one_of(st.text(min_size=0, max_size=10), st.integers(), st.none()), max_size=5),
        st.text(min_size=0, max_size=10),  # string instead of array
        st.none(),
        st.just([]),  # empty list
    )

    # Variants for "child":
    if depth >= MAX_DEPTH:
        child_variants = st.none()
    else:
        child_variants = st.one_of(
            st.none(),
            record_strategy(depth+1),
            st.text(min_size=0, max_size=10),  # wrong type
            st.integers(min_value=0, max_value=1000),  # wrong type
        )

    # Now build a strategy that picks one or two fields to replace with variant values,
    # rest are valid.

    fields = ["id", "amount", "name", "status", "tags", "child"]
    variant_map = {
        "id": id_variants,
        "amount": amount_variants,
        "name": name_variants,
        "status": status_variants,
        "tags": tags_variants,
        "child": child_variants,
    }

    # Strategy to pick 1 or 2 distinct fields to vary
    num_fields_to_vary = st.integers(min_value=1, max_value=2)

    @st.composite
    def variant_record(draw):
        base_record = draw(base)
        n = draw(num_fields_to_vary)
        fields_to_vary = draw(st.lists(st.sampled_from(fields), min_size=n, max_size=n, unique=True))
        for f in fields_to_vary:
            base_record[f] = draw(variant_map[f])
        return base_record

    return variant_record()

@st.composite
def generated_json(draw) -> bytes:
    record = draw(record_strategy())
    # Serialize to JSON bytes
    s = json.dumps(record, separators=(',', ':'))
    return s.encode("utf-8")