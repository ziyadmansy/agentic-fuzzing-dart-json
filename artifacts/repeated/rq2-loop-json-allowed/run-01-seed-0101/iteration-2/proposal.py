from hypothesis import strategies as st
import json

# The record schema:
# {
#   "id": <integer>,
#   "amount": <string>,
#   "name": <string or null>,
#   "status": <one of "active", "inactive", "unknown">,
#   "tags": <array of strings>,
#   "child": <Record or null, one level of recursion normally>
# }

# Strategy hint: produce mostly well-formed documents, but vary one or two fields subtly:
# - sometimes use a string for "id" (should be int)
# - sometimes use a number for "amount" (should be string)
# - sometimes omit "name" (should always be present, but null allowed)
# - sometimes use an invalid "status" string (not in enum)
# - sometimes use non-string elements in "tags"
# - sometimes use "child" null, or a valid record, or a record with one subtle error
# - keep recursion depth bounded to 1 level of child

# We produce a dict, then json.dumps it to bytes.

# To maximize divergence, we produce mostly valid documents but with one subtle error or variation.

@st.composite
def generated_json(draw) -> bytes:
    # Base valid fields
    # id: int normally, but sometimes string
    id_val = draw(st.one_of(
        st.integers(min_value=0, max_value=2**31-1),
        st.text(min_size=1, max_size=5)  # invalid type for id
    ))

    # amount: string normally, sometimes number
    amount_val = draw(st.one_of(
        st.text(min_size=1, max_size=10),
        st.floats(allow_nan=False, allow_infinity=False).map(lambda f: str(f)),  # valid string float
        st.integers().map(str),
        st.floats(allow_nan=False, allow_infinity=False),  # invalid type: number not string
    ))

    # name: string or null normally, sometimes missing (omit field)
    name_present = draw(st.booleans())
    if name_present:
        name_val = draw(st.one_of(st.none(), st.text(min_size=0, max_size=20)))
    else:
        name_val = None  # will omit field

    # status: one of enum normally, sometimes invalid string
    status_val = draw(st.one_of(
        st.sampled_from(["active", "inactive", "unknown"]),
        st.text(min_size=1, max_size=10).filter(lambda s: s not in {"active", "inactive", "unknown"})
    ))

    # tags: array of strings normally, sometimes array with non-string elements or empty array
    tags_val = draw(st.one_of(
        st.lists(st.text(min_size=0, max_size=10), min_size=0, max_size=5),
        st.lists(st.one_of(st.text(min_size=0, max_size=10), st.integers(), st.none()), min_size=0, max_size=5)
    ))

    # child: null or a record (one level recursion)
    # child record can be valid or have one subtle error (like id as string)
    child_present = draw(st.booleans())
    if child_present:
        # child record fields:
        child_id = draw(st.one_of(
            st.integers(min_value=0, max_value=2**31-1),
            st.text(min_size=1, max_size=5)  # invalid type for id
        ))
        child_amount = draw(st.one_of(
            st.text(min_size=1, max_size=10),
            st.floats(allow_nan=False, allow_infinity=False)  # invalid type: number not string
        ))
        child_name = draw(st.one_of(st.none(), st.text(min_size=0, max_size=20)))
        child_status = draw(st.one_of(
            st.sampled_from(["active", "inactive", "unknown"]),
            st.text(min_size=1, max_size=10).filter(lambda s: s not in {"active", "inactive", "unknown"})
        ))
        child_tags = draw(st.lists(st.text(min_size=0, max_size=10), min_size=0, max_size=5))
        child_child = None  # no deeper recursion

        child_obj = {
            "id": child_id,
            "amount": child_amount,
            "name": child_name,
            "status": child_status,
            "tags": child_tags,
            "child": child_child
        }
    else:
        child_obj = None

    obj = {
        "id": id_val,
        "amount": amount_val,
        "status": status_val,
        "tags": tags_val,
        "child": child_obj,
    }
    if name_present:
        obj["name"] = name_val

    # Serialize to JSON bytes
    return json.dumps(obj).encode("utf-8")