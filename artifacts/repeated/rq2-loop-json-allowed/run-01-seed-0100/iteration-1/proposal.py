from hypothesis import strategies as st
import json

# We define a strategy for the "status" field, which must be one of three strings.
status_strat = st.sampled_from(["active", "inactive", "unknown"])

# Strategy for "tags": array of strings, possibly empty, strings nonempty but can be empty too.
tags_strat = st.lists(st.text(min_size=0, max_size=10), max_size=5)

# Strategy for "name": string or null
name_strat = st.one_of(st.none(), st.text(min_size=0, max_size=20))

# Strategy for "amount": string, but we will also try to induce divergence by sometimes using numeric strings,
# empty strings, or strings with whitespace or unusual characters.
amount_strat = st.text(min_size=0, max_size=20)

# Strategy for "id": integer, but to induce divergence, sometimes use integers, sometimes strings that look like integers,
# or floats encoded as strings, or negative numbers, or zero.
id_int_strat = st.integers(min_value=0, max_value=2**31-1)
id_str_strat = st.text(min_size=1, max_size=10)
id_strict_int = st.integers(min_value=0, max_value=2**31-1)
# We'll mix integers and strings for id to induce divergence.
id_strat = st.one_of(
    id_int_strat,
    st.text(min_size=1, max_size=10),
)

# To induce divergence, we will sometimes omit fields or replace them with wrong types.
# But the prompt says all six fields are always present in a well-formed document.
# We want to produce syntactically valid JSON objects with all six fields present,
# but with one or two fields off-type or off-value to induce divergence.

# To keep recursion bounded, we limit child to either None or a record with no child.
# We'll allow child to be None or a record with child=None (one level recursion).

@st.composite
def record(draw, allow_wrong_types=False, depth=0):
    # allow_wrong_types: if True, we may produce fields with wrong types or borderline values.
    # depth: recursion depth, max 1.

    # id field: mostly int, sometimes string, sometimes negative int, sometimes float string
    if allow_wrong_types:
        id_val = draw(st.one_of(
            st.integers(min_value=-100, max_value=2**31-1),
            st.text(min_size=1, max_size=10),
            st.floats(allow_nan=False, allow_infinity=False).map(lambda f: str(f)),
        ))
    else:
        id_val = draw(id_int_strat)

    # amount field: string, but sometimes empty, sometimes numeric string, sometimes whitespace
    if allow_wrong_types:
        amount_val = draw(st.one_of(
            st.text(min_size=0, max_size=20),
            st.integers(min_value=-1000, max_value=1000).map(str),
            st.just(""),
            st.just(" "),
            st.just("\n"),
        ))
    else:
        amount_val = draw(amount_strat)

    # name field: string or null, sometimes empty string, sometimes whitespace string
    if allow_wrong_types:
        name_val = draw(st.one_of(
            st.none(),
            st.text(min_size=0, max_size=20),
            st.just(""),
            st.just(" "),
            st.just("\n"),
        ))
    else:
        name_val = draw(name_strat)

    # status field: one of three strings, sometimes wrong string or null
    if allow_wrong_types:
        status_val = draw(st.one_of(
            status_strat,
            st.text(min_size=1, max_size=10).filter(lambda s: s not in {"active", "inactive", "unknown"}),
            st.none(),
            st.integers(min_value=0, max_value=10).map(str),
        ))
    else:
        status_val = draw(status_strat)

    # tags field: array of strings, sometimes array of ints or mixed types or empty
    if allow_wrong_types:
        tags_val = draw(st.one_of(
            tags_strat,
            st.lists(st.integers(min_value=0, max_value=100).map(str), max_size=5),
            st.lists(st.one_of(st.text(min_size=0, max_size=10), st.integers(min_value=0, max_value=100).map(str)), max_size=5),
            st.lists(st.integers(min_value=0, max_value=100), max_size=5),
            st.just([]),
        ))
    else:
        tags_val = draw(tags_strat)

    # child field: null or record with child null (one level recursion)
    if depth == 0:
        if allow_wrong_types:
            # sometimes child is null, sometimes a record with allow_wrong_types=False, sometimes wrong type
            child_val = draw(st.one_of(
                st.none(),
                record(allow_wrong_types=False, depth=1),
                st.text(min_size=1, max_size=10),  # wrong type
                st.integers(min_value=0, max_value=100),  # wrong type
            ))
        else:
            child_val = draw(st.one_of(
                st.none(),
                record(allow_wrong_types=False, depth=1),
            ))
    else:
        # depth 1: child must be null to avoid deeper recursion
        child_val = None

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
def generated_json(draw):
    # We produce mostly well-formed records, but sometimes with one or two fields off-type or borderline
    # to induce divergence.

    # 70% well-formed, 30% with one or two fields off
    allow_wrong = draw(st.booleans())

    rec = draw(record(allow_wrong_types=allow_wrong, depth=0))

    # Serialize to JSON bytes
    js = json.dumps(rec, separators=(",", ":"))
    return js.encode("utf-8")