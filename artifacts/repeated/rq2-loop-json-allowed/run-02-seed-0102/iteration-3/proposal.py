from hypothesis import strategies as st
import json

# Constants for the enum 'status'
STATUS_VALUES = ["active", "inactive", "unknown"]

# Base valid record strategy (no recursion)
base_record = st.fixed_dictionaries({
    "id": st.integers(min_value=0, max_value=2**31 - 1),
    "amount": st.text(min_size=1, max_size=20),  # string, nonempty
    "name": st.one_of(st.none(), st.text(min_size=0, max_size=20)),
    "status": st.sampled_from(STATUS_VALUES),
    "tags": st.lists(st.text(min_size=0, max_size=10), max_size=5),
    "child": st.none(),
})

# Recursive record with one level of recursion max
@st.composite
def record_with_child(draw, allow_invalid_field=False):
    # Draw a base record first
    base = draw(base_record)

    # Possibly replace 'child' with a nested record (one level only)
    # To keep recursion bounded, child.child is always None
    child_record = draw(base_record)
    child_record = dict(child_record)
    child_record["child"] = None

    # Decide if child is null or nested record
    child_val = draw(st.one_of(st.just(None), st.just(child_record)))
    base["child"] = child_val

    # Now, optionally introduce exactly one subtle divergence:
    # - Change one field's type to a close but invalid type
    # - Omit a field (remove it)
    # - Use a borderline value (empty string for amount, empty tags, null name vs "")
    # - Use a wrong enum value (e.g. "Active" instead of "active")
    # - Use a number as string or string as number in id or amount
    # - Use an array with one wrong element type in tags
    # - Use a nested child with a subtle error

    # We do this with low probability to keep mostly valid but subtly off
    if allow_invalid_field:
        # Choose one field to corrupt
        field_to_corrupt = draw(st.sampled_from(["id", "amount", "name", "status", "tags", "child"]))

        if field_to_corrupt == "id":
            # id should be int, try string or float
            corrupt_id = draw(st.one_of(
                st.text(min_size=1, max_size=10),
                st.floats(allow_nan=False, allow_infinity=False),
                st.integers(min_value=-1000, max_value=-1),  # negative int (if original only nonneg)
            ))
            base["id"] = corrupt_id

        elif field_to_corrupt == "amount":
            # amount should be string, try int, null, empty string, or number string with spaces
            corrupt_amount = draw(st.one_of(
                st.integers(min_value=0, max_value=10000),
                st.none(),
                st.just(""),  # empty string borderline
                st.just(" 123 "),  # string with spaces
                st.floats(allow_nan=False, allow_infinity=False),
            ))
            base["amount"] = corrupt_amount

        elif field_to_corrupt == "name":
            # name is string or null, try int, bool, missing field, or empty string
            corrupt_name = draw(st.one_of(
                st.integers(min_value=0, max_value=100),
                st.booleans(),
                st.none(),
                st.just(""),
            ))
            # Also try omitting the field entirely sometimes
            omit = draw(st.booleans())
            if omit:
                base.pop("name")
            else:
                base["name"] = corrupt_name

        elif field_to_corrupt == "status":
            # status is enum, try wrong casing, wrong string, null, int
            corrupt_status = draw(st.one_of(
                st.text(min_size=1, max_size=10).filter(lambda s: s.lower() not in STATUS_VALUES),
                st.just("Active"),  # wrong case
                st.none(),
                st.integers(min_value=0, max_value=10),
            ))
            base["status"] = corrupt_status

        elif field_to_corrupt == "tags":
            # tags is array of strings, try array with ints, null, empty array, or string instead of array
            corrupt_tags = draw(st.one_of(
                st.lists(st.integers(min_value=0, max_value=10), max_size=5),
                st.none(),
                st.just([]),
                st.text(min_size=1, max_size=10),
            ))
            base["tags"] = corrupt_tags

        elif field_to_corrupt == "child":
            # child is null or record, try wrong type, or nested record with one field corrupted
            corrupt_child = draw(st.one_of(
                st.text(min_size=1, max_size=10),
                st.integers(min_value=0, max_value=100),
                st.none(),
                # nested record with corrupted field inside
                st.fixed_dictionaries({
                    "id": st.integers(min_value=0, max_value=100),
                    "amount": st.text(min_size=1, max_size=10),
                    "name": st.one_of(st.none(), st.text(min_size=0, max_size=10)),
                    "status": st.sampled_from(STATUS_VALUES),
                    "tags": st.lists(st.text(min_size=0, max_size=10), max_size=3),
                    "child": st.none(),
                }).map(lambda d: {**d, "id": "not_an_int"}),  # corrupt id inside child
            ))
            base["child"] = corrupt_child

    return json.dumps(base).encode("utf-8")


@st.composite
def generated_json(draw) -> bytes:
    # Mostly generate valid or near-valid records
    # With ~40% chance, introduce one subtle corruption to trigger divergence
    allow_invalid = draw(st.booleans())
    return draw(record_with_child(allow_invalid_field=allow_invalid))