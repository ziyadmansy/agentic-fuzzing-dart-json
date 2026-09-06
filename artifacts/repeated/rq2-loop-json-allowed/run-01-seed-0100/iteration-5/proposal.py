from hypothesis import strategies as st
import json

# Base valid values for fields
id_valid = st.integers(min_value=0, max_value=2**31-1)
amount_valid = st.text(min_size=1).filter(lambda s: all(c.isdigit() or c == '.' for c in s))
name_valid = st.one_of(st.none(), st.text(min_size=1))
status_valid = st.sampled_from(["active", "inactive", "unknown"])
tags_valid = st.lists(st.text(min_size=1), max_size=3)
# We'll limit recursion depth to 1 for child

# To induce divergences, we create "almost valid" variants for each field:
# - id: sometimes string instead of int
# - amount: sometimes number instead of string, or empty string
# - name: sometimes number instead of string/null
# - status: sometimes invalid string or null
# - tags: sometimes null, or array with non-string elements
# - child: sometimes missing, null, or malformed record (one field wrong type)

# Helper: generate a record dict with controlled "offness" in one field at most
@st.composite
def record(draw, *, allow_off_field=None, depth=0):
    # allow_off_field: None or one of the keys to inject a type or value error
    # depth: recursion depth, max 1

    # id field
    if allow_off_field == "id":
        # id as string (should be int)
        id_val = draw(st.one_of(id_valid.map(str), st.integers(min_value=-1000, max_value=-1)))
    else:
        id_val = draw(id_valid)

    # amount field
    if allow_off_field == "amount":
        # amount as number or empty string or string with invalid chars
        amount_val = draw(st.one_of(
            st.floats(allow_nan=False, allow_infinity=False).map(lambda f: str(f)),
            st.just(""),
            st.text(min_size=1).filter(lambda s: any(c.isalpha() for c in s))
        ))
    else:
        amount_val = draw(amount_valid)

    # name field
    if allow_off_field == "name":
        # name as number or boolean instead of string/null
        name_val = draw(st.one_of(st.integers(), st.booleans()))
    else:
        name_val = draw(name_valid)

    # status field
    if allow_off_field == "status":
        # invalid string or null instead of one of three strings
        status_val = draw(st.one_of(st.just(None), st.text(min_size=1).filter(lambda s: s not in ["active", "inactive", "unknown"])))
    else:
        status_val = draw(status_valid)

    # tags field
    if allow_off_field == "tags":
        # null or array with non-string elements
        tags_val = draw(st.one_of(
            st.none(),
            st.lists(st.one_of(st.integers(), st.booleans()), max_size=3)
        ))
    else:
        tags_val = draw(tags_valid)

    # child field
    if depth >= 1:
        # no recursion deeper than 1
        child_val = None
    else:
        if allow_off_field == "child":
            # child is malformed record: one field wrong type or missing
            # pick one field to corrupt in child
            child_off_field = draw(st.sampled_from(["id", "amount", "name", "status", "tags"]))
            child_val = draw(record(allow_off_field=child_off_field, depth=depth+1))
            # Also sometimes null or missing child to mix
            if draw(st.booleans()):
                child_val = None
        else:
            # child is either None or valid record with no offness
            child_val = draw(st.one_of(st.none(), record(allow_off_field=None, depth=depth+1)))

    # Build dict, always include all keys (no missing keys)
    rec = {
        "id": id_val,
        "amount": amount_val,
        "name": name_val,
        "status": status_val,
        "tags": tags_val,
        "child": child_val,
    }
    return rec

@st.composite
def generated_json(draw) -> bytes:
    # Pick zero or one field to corrupt per record to maximize divergence
    off_field = draw(st.one_of(st.none(), st.sampled_from(["id", "amount", "name", "status", "tags", "child"])))
    rec = draw(record(allow_off_field=off_field, depth=0))
    # Serialize to JSON bytes
    return json.dumps(rec, separators=(',', ':')).encode('utf-8')