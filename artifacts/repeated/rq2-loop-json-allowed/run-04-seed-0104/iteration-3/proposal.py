from hypothesis import strategies as st
import json

# Allowed status values
STATUS_VALUES = ["active", "inactive", "unknown"]

@st.composite
def generated_json(draw) -> bytes:
    # To avoid infinite recursion, limit depth to 1 level of child
    # We'll define an inner function to generate a record dict with optional recursion
    
    def record_strategy(depth=0):
        # Base record fields with mostly correct types
        base = {
            "id": st.integers(min_value=-(2**31), max_value=2**31-1),
            "amount": st.text(min_size=0, max_size=20),
            "name": st.one_of(st.none(), st.text(min_size=0, max_size=20)),
            "status": st.sampled_from(STATUS_VALUES),
            "tags": st.lists(st.text(min_size=0, max_size=10), max_size=5),
        }
        
        # To induce divergence, we will sometimes:
        # - Replace a field with a wrong type (e.g. "id" as string)
        # - Omit a field (though spec says always present, but some impls may differ)
        # - Put null where string expected or vice versa
        # - Use boundary values (empty strings, empty arrays)
        # - For child, either null or a nested record (depth limited)
        
        # Strategy for fields with possible type deviations
        def field_with_type_variants(field_name, correct_strategy, wrong_strategy):
            # 80% chance correct type, 20% chance wrong type variant
            return st.one_of(
                correct_strategy,
                wrong_strategy,
            )
        
        # id: normally int, sometimes stringified int or float or null (wrong types)
        id_strat = st.one_of(
            base["id"],
            st.text(min_size=1, max_size=10).filter(lambda s: not s.isdigit()),  # non-digit string
            st.floats(allow_nan=False, allow_infinity=False),
            st.none(),
        )
        
        # amount: normally string, sometimes int or null
        amount_strat = st.one_of(
            base["amount"],
            st.integers(min_value=-1000, max_value=1000),
            st.none(),
        )
        
        # name: string or null normally, sometimes int or empty list
        name_strat = st.one_of(
            base["name"],
            st.integers(min_value=-1000, max_value=1000),
            st.lists(st.text(min_size=1, max_size=5), max_size=3),
        )
        
        # status: normally one of allowed strings, sometimes a wrong string or null or int
        status_strat = st.one_of(
            base["status"],
            st.text(min_size=1, max_size=10).filter(lambda s: s not in STATUS_VALUES),
            st.none(),
            st.integers(min_value=0, max_value=10),
        )
        
        # tags: normally list of strings, sometimes null, sometimes list of ints or mixed
        tags_strat = st.one_of(
            base["tags"],
            st.none(),
            st.lists(st.integers(min_value=0, max_value=10), max_size=5),
            st.lists(st.one_of(st.text(min_size=1, max_size=5), st.integers()), max_size=5),
        )
        
        # child: null or nested record (depth limited)
        if depth >= 1:
            # no further recursion, only null or empty dict (invalid but present)
            child_strat = st.one_of(
                st.none(),
                st.just({}),  # empty dict, missing fields
            )
        else:
            # 70% null, 30% nested record
            child_strat = st.one_of(
                st.none(),
                record_strategy(depth=depth+1),
            )
        
        # Compose the record dict from drawn values
        def build_record(id_v, amount_v, name_v, status_v, tags_v, child_v):
            d = {
                "id": id_v,
                "amount": amount_v,
                "name": name_v,
                "status": status_v,
                "tags": tags_v,
                "child": child_v,
            }
            return d
        
        return st.tuples(id_strat, amount_strat, name_strat, status_strat, tags_strat, child_strat).map(
            lambda t: build_record(*t)
        )
    
    record = draw(record_strategy())
    # Serialize to JSON bytes
    json_bytes = json.dumps(record, separators=(",", ":")).encode("utf-8")
    return json_bytes