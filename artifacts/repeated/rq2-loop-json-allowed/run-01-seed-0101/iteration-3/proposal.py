from hypothesis import strategies as st
import json

# Base valid values for fields
id_base = st.integers(min_value=0, max_value=2**31 - 1)
amount_base = st.text(min_size=1, max_size=10).filter(lambda s: all(32 <= ord(c) <= 126 for c in s))
name_base = st.one_of(st.none(), st.text(min_size=0, max_size=20))
status_base = st.sampled_from(["active", "inactive", "unknown"])
tags_base = st.lists(st.text(min_size=0, max_size=10), min_size=0, max_size=5)

# To create subtle divergences, we will:
# - sometimes replace a field with a wrong type (e.g. int instead of string)
# - sometimes omit a field (but since all fields are always present in well-formed docs,
#   we will instead put null or wrong type)
# - sometimes put enum field with a wrong string (e.g. "Active" vs "active")
# - sometimes put tags as a list of mixed types or empty string instead of list
# - sometimes put child as null or a nested record, but with one field subtly wrong
# We will vary only one or two fields per document to maximize chance of divergence.

# Recursive strategy for child record, bounded to depth 1
@st.composite
def record(draw, depth=0):
    # Base fields mostly valid
    id_val = draw(id_base)
    # amount usually string, sometimes int or null
    amount_val = draw(st.one_of(
        amount_base,
        st.integers(min_value=0, max_value=1000),
        st.none(),
    ))
    # name string or null or int (wrong type)
    name_val = draw(st.one_of(
        name_base,
        st.integers(min_value=0, max_value=1000),
    ))
    # status usually valid enum, sometimes wrong case or invalid string
    status_val = draw(st.one_of(
        status_base,
        st.text(min_size=1, max_size=10).filter(lambda s: s.lower() not in ["active", "inactive", "unknown"]),
        st.sampled_from(["Active", "Inactive", "Unknown"]),  # wrong case
    ))
    # tags usually list of strings, sometimes list with ints or empty string or null
    tags_val = draw(st.one_of(
        tags_base,
        st.lists(st.one_of(st.text(min_size=0, max_size=10), st.integers(min_value=0, max_value=10)), min_size=0, max_size=5),
        st.text(min_size=0, max_size=5),
        st.none(),
    ))
    # child is null or nested record (depth limited to 1)
    if depth == 0:
        child_val = draw(st.one_of(
            st.none(),
            record(depth=1),
            # child with one field subtly wrong: e.g. id as string instead of int
            st.fixed_dictionaries({
                "id": st.one_of(id_base, st.text(min_size=1, max_size=5)),
                "amount": amount_base,
                "name": name_base,
                "status": status_base,
                "tags": tags_base,
                "child": st.none(),
            })
        ))
    else:
        child_val = None

    # Compose dict with all fields present
    d = {
        "id": id_val,
        "amount": amount_val,
        "name": name_val,
        "status": status_val,
        "tags": tags_val,
        "child": child_val,
    }
    return d

@st.composite
def generated_json(draw) -> bytes:
    d = draw(record())
    # Serialize to JSON bytes
    j = json.dumps(d, separators=(",", ":"))
    return j.encode("utf-8")