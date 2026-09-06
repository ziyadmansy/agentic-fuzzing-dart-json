from hypothesis import strategies as st
import json

# We define a recursive strategy for the "child" field with bounded depth.
# The record fields are mostly fixed types, but we inject subtle type variations
# or boundary cases in one or two fields at a time to trigger divergences.

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for fields:
    # id: normally integer, but sometimes string or float to cause type confusion
    id_base = st.integers(min_value=0, max_value=2**31-1)
    id_alt = st.one_of(
        st.integers(min_value=0, max_value=2**31-1),
        st.floats(allow_nan=False, allow_infinity=False),
        st.text(min_size=1, max_size=5),  # string instead of int
    )
    # amount: normally string, but sometimes number or null
    amount_base = st.text(min_size=1, max_size=10)
    amount_alt = st.one_of(
        st.text(min_size=1, max_size=10),
        st.integers(min_value=0, max_value=1000000),
        st.none(),
    )
    # name: string or null, but sometimes number or boolean
    name_base = st.one_of(st.text(min_size=0, max_size=20), st.none())
    name_alt = st.one_of(
        st.text(min_size=0, max_size=20),
        st.none(),
        st.integers(min_value=0, max_value=100),
        st.booleans(),
    )
    # status: one of "active", "inactive", "unknown"
    # but sometimes a wrong string or null or number
    status_base = st.sampled_from(["active", "inactive", "unknown"])
    status_alt = st.one_of(
        st.sampled_from(["active", "inactive", "unknown"]),
        st.text(min_size=1, max_size=10).filter(lambda s: s not in {"active","inactive","unknown"}),
        st.none(),
        st.integers(min_value=0, max_value=10),
    )
    # tags: array of strings, but sometimes array of mixed types or empty array
    tags_base = st.lists(st.text(min_size=1, max_size=10), min_size=0, max_size=5)
    tags_alt = st.one_of(
        st.lists(st.text(min_size=1, max_size=10), min_size=0, max_size=5),
        st.lists(st.one_of(st.text(min_size=1, max_size=10), st.integers(), st.none()), min_size=0, max_size=5),
        st.none(),
    )
    
    # Recursive child: either null or a nested record with bounded depth
    # We'll limit recursion depth to 1 (child.child is always null)
    def record_strategy(depth=0):
        if depth > 1:
            # At max depth, child is always null
            return st.just(None)
        else:
            # For child record, we use mostly base fields but inject one or two alt fields
            # to cause subtle divergences.
            # We'll randomly pick 0-2 fields to replace with alt variants.
            # This simulates "almost well-formed" with one or two fields off.
            fields = {
                "id": id_base,
                "amount": amount_base,
                "name": name_base,
                "status": status_base,
                "tags": tags_base,
                "child": st.none(),  # placeholder, replaced below
            }
            # Replace child with recursive call
            fields["child"] = record_strategy(depth + 1)
            
            # Draw which fields to replace with alt
            keys = list(fields.keys())
            n_alt = draw(st.integers(min_value=0, max_value=2))
            alt_keys = draw(st.sampled_from(keys).flatmap(
                lambda k: st.lists(st.just(k), min_size=n_alt, max_size=n_alt, unique=True)
            )) if n_alt > 0 else []
            
            # Build final field strategies with alt replacements
            final_fields = {}
            for k in keys:
                if k in alt_keys:
                    if k == "id":
                        final_fields[k] = id_alt
                    elif k == "amount":
                        final_fields[k] = amount_alt
                    elif k == "name":
                        final_fields[k] = name_alt
                    elif k == "status":
                        final_fields[k] = status_alt
                    elif k == "tags":
                        final_fields[k] = tags_alt
                    elif k == "child":
                        # For child, to keep recursion bounded, only allow None or base record
                        # but we can still inject alt fields inside child by recursion
                        final_fields[k] = record_strategy(depth + 1)
                else:
                    final_fields[k] = fields[k]
            
            return st.fixed_dictionaries(final_fields)
    
    # Top-level record: same approach, but only 1 alt field max to keep "almost well-formed"
    base_record = {
        "id": id_base,
        "amount": amount_base,
        "name": name_base,
        "status": status_base,
        "tags": tags_base,
        "child": record_strategy(0),
    }
    keys = list(base_record.keys())
    n_alt_top = draw(st.integers(min_value=0, max_value=1))
    alt_keys_top = draw(st.sampled_from(keys).flatmap(
        lambda k: st.lists(st.just(k), min_size=n_alt_top, max_size=n_alt_top, unique=True)
    )) if n_alt_top > 0 else []
    
    final_top = {}
    for k in keys:
        if k in alt_keys_top:
            if k == "id":
                final_top[k] = id_alt
            elif k == "amount":
                final_top[k] = amount_alt
            elif k == "name":
                final_top[k] = name_alt
            elif k == "status":
                final_top[k] = status_alt
            elif k == "tags":
                final_top[k] = tags_alt
            elif k == "child":
                final_top[k] = record_strategy(0)
        else:
            final_top[k] = base_record[k]
    
    record = draw(st.fixed_dictionaries(final_top))
    # Serialize to JSON bytes
    return json.dumps(record).encode("utf-8")