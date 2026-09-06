from hypothesis import strategies as st
import json

# Allowed status values
_status_values = st.sampled_from(["active", "inactive", "unknown"])

# Base record fields except child
_base_record_fields = st.fixed_dictionaries({
    "id": st.integers(min_value=-(2**31), max_value=2**31-1),
    "amount": st.text(min_size=1, max_size=10),
    "name": st.one_of(st.none(), st.text(min_size=0, max_size=20)),
    "status": _status_values,
    "tags": st.lists(st.text(min_size=0, max_size=10), max_size=5),
})

# To induce divergences, we create a strategy that sometimes:
# - uses correct types
# - or replaces a single field with a wrong type or missing field
# - or uses null where not expected
# - or uses boundary values (empty string, empty list, null name)
# - or uses a child record or null child
# We limit recursion depth to 1 for child.

@st.composite
def record(draw, *, allow_wrong_type=False, allow_missing_field=False, depth=0):
    # Start from a valid base dict
    base = draw(_base_record_fields)

    # Possibly mutate one field to cause divergence
    # We pick one field to mutate or omit if allow_wrong_type or allow_missing_field
    mutate_field = None
    if allow_wrong_type or allow_missing_field:
        mutate_field = draw(st.one_of(
            st.just("id"),
            st.just("amount"),
            st.just("name"),
            st.just("status"),
            st.just("tags"),
            st.just("child"),
            st.none(),
        ))

    # Mutate or omit one field if requested
    if mutate_field is not None:
        if allow_missing_field and draw(st.booleans()):
            # Remove the field entirely (simulate missing field)
            if mutate_field in base:
                del base[mutate_field]
        else:
            # Replace field with wrong type or borderline value
            if mutate_field == "id":
                # id should be int, replace with string or float or null
                base["id"] = draw(st.one_of(
                    st.text(min_size=1, max_size=5),
                    st.floats(allow_nan=False, allow_infinity=False),
                    st.none(),
                ))
            elif mutate_field == "amount":
                # amount should be string, replace with int, list, null
                base["amount"] = draw(st.one_of(
                    st.integers(),
                    st.lists(st.text(), max_size=2),
                    st.none(),
                ))
            elif mutate_field == "name":
                # name is string or null, replace with int, list, bool
                base["name"] = draw(st.one_of(
                    st.integers(),
                    st.lists(st.text(), max_size=2),
                    st.booleans(),
                ))
            elif mutate_field == "status":
                # status is enum string, replace with wrong string, int, null
                base["status"] = draw(st.one_of(
                    st.text(min_size=1, max_size=10).filter(lambda s: s not in ["active","inactive","unknown"]),
                    st.integers(),
                    st.none(),
                ))
            elif mutate_field == "tags":
                # tags is list of strings, replace with string, int, list of ints, null
                base["tags"] = draw(st.one_of(
                    st.text(min_size=1, max_size=10),
                    st.integers(),
                    st.lists(st.integers(), max_size=3),
                    st.none(),
                ))
            elif mutate_field == "child":
                # child is record or null, replace with wrong types or malformed record
                if depth == 0:
                    # At depth 0, we can recurse with allow_wrong_type=True to induce subtle errors
                    base["child"] = draw(st.one_of(
                        record(allow_wrong_type=True, allow_missing_field=True, depth=1),
                        st.text(min_size=1, max_size=10),
                        st.integers(),
                        st.none(),
                    ))
                else:
                    # At depth 1, no further recursion, just wrong types or null
                    base["child"] = draw(st.one_of(
                        st.text(min_size=1, max_size=10),
                        st.integers(),
                        st.none(),
                    ))
            else:
                # mutate_field is None or unknown, do nothing
                pass

    else:
        # No mutation requested, but still add child field properly
        if depth == 0:
            # child is either null or a valid record at depth 1 (no further recursion)
            base["child"] = draw(st.one_of(
                st.none(),
                record(allow_wrong_type=False, allow_missing_field=False, depth=1),
            ))
        else:
            # depth 1, child must be null (no further recursion)
            base["child"] = None

    return base

@st.composite
def generated_json(draw) -> bytes:
    # We generate mostly valid records, but with about half the time a single subtle mutation
    allow_wrong_type = draw(st.booleans())
    allow_missing_field = False
    # To keep "almost well-formed" documents, only allow missing field if no wrong type mutation
    if not allow_wrong_type:
        allow_missing_field = draw(st.booleans())

    rec = draw(record(allow_wrong_type=allow_wrong_type, allow_missing_field=allow_missing_field, depth=0))
    # Serialize to JSON bytes
    return json.dumps(rec).encode("utf-8")