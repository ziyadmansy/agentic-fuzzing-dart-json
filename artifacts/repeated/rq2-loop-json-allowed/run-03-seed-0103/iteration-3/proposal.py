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

# Strategy hint: produce mostly well-formed records but vary one or two fields subtly:
# - sometimes use wrong types (e.g. number instead of string for amount)
# - sometimes omit fields (but spec says all six fields always present in well-formed docs,
#   so omit only rarely or replace with null or wrong type)
# - vary null vs string for name and child
# - vary enum status with correct and incorrect strings
# - tags as array of strings, but sometimes empty, sometimes with non-string elements
# - child: either null or a nested record (one level only)
# 
# We will produce a record dict, then json.dumps it to bytes.
# We'll limit recursion depth to 1 (child can be null or a record with child=null).
# We'll vary one or two fields per example to maximize divergence chances.

@st.composite
def generated_json(draw) -> bytes:
    # Base fields with mostly valid values
    id_val = draw(st.integers(min_value=0, max_value=2**31-1))
    
    # amount: mostly string, but sometimes number or null or empty string
    amount_valid = st.text(min_size=1, max_size=20)
    amount_invalid = st.one_of(st.integers(), st.floats(allow_nan=False, allow_infinity=False), st.none(), st.just(""))
    amount = draw(st.one_of(amount_valid, amount_invalid))
    
    # name: string or null, but sometimes number or boolean to cause divergence
    name_valid = st.one_of(st.none(), st.text(min_size=0, max_size=30))
    name_invalid = st.one_of(st.integers(), st.booleans())
    name = draw(st.one_of(name_valid, name_invalid))
    
    # status: mostly valid enum, sometimes invalid string or null or number
    status_valid = st.sampled_from(["active", "inactive", "unknown"])
    status_invalid = st.one_of(st.text(min_size=1, max_size=10).filter(lambda s: s not in {"active","inactive","unknown"}),
                               st.none(),
                               st.integers())
    status = draw(st.one_of(status_valid, status_invalid))
    
    # tags: array of strings, sometimes empty, sometimes with non-string elements
    tag_str = st.text(min_size=1, max_size=10)
    tag_invalid = st.one_of(st.integers(), st.none(), st.booleans(), st.floats(allow_nan=False, allow_infinity=False))
    tags_valid = st.lists(tag_str, min_size=0, max_size=5)
    tags_invalid = st.lists(st.one_of(tag_str, tag_invalid), min_size=0, max_size=5)
    tags = draw(st.one_of(tags_valid, tags_invalid))
    
    # child: null or a nested record with child=null (one level recursion)
    # For the nested record, we produce a valid or slightly invalid record but child=null to avoid deep recursion.
    def nested_record():
        nid = draw(st.integers(min_value=0, max_value=2**31-1))
        namount = draw(st.text(min_size=1, max_size=20))
        nname = draw(st.one_of(st.none(), st.text(min_size=0, max_size=30)))
        nstatus = draw(st.sampled_from(["active", "inactive", "unknown"]))
        ntags = draw(st.lists(st.text(min_size=1, max_size=10), min_size=0, max_size=3))
        return {
            "id": nid,
            "amount": namount,
            "name": nname,
            "status": nstatus,
            "tags": ntags,
            "child": None
        }
    
    # child can be null or nested_record or sometimes invalid (e.g. wrong type)
    child_valid = st.one_of(st.none(), st.just(nested_record()))
    child_invalid = st.one_of(st.integers(), st.text(min_size=1, max_size=10), st.booleans())
    child_choice = draw(st.one_of(child_valid, child_invalid))
    if callable(child_choice):
        child_val = child_choice()
    else:
        child_val = child_choice
    
    record = {
        "id": id_val,
        "amount": amount,
        "name": name,
        "status": status,
        "tags": tags,
        "child": child_val
    }
    
    # Serialize to JSON bytes
    return json.dumps(record).encode("utf-8")