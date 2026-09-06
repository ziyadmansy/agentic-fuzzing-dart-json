from hypothesis import strategies as st
import json

# Constants for the "status" field allowed values
STATUS_VALUES = ["active", "inactive", "unknown"]

# Base valid record strategy, no recursion yet
@st.composite
def base_record(draw):
    # id: integer
    id_val = draw(st.integers(min_value=0, max_value=2**31-1))
    # amount: string (representing a number, but we keep it as string)
    # To induce subtle divergences, sometimes use numeric strings, sometimes weird strings
    amount_val = draw(
        st.one_of(
            st.text(min_size=1, max_size=10).filter(lambda s: s != ""),  # arbitrary nonempty string
            st.just("0"),
            st.just("123.45"),
            st.just("-0.01"),
            st.just("1e10"),
        )
    )
    # name: string or null
    name_val = draw(st.one_of(st.none(), st.text(min_size=0, max_size=20)))
    # status: one of the three strings
    status_val = draw(st.sampled_from(STATUS_VALUES))
    # tags: array of strings (empty or nonempty)
    tags_val = draw(st.lists(st.text(min_size=0, max_size=10), max_size=5))
    # child: null or base_record (recursion handled later)
    # For base_record, child is always None (to avoid infinite recursion here)
    child_val = None

    return {
        "id": id_val,
        "amount": amount_val,
        "name": name_val,
        "status": status_val,
        "tags": tags_val,
        "child": child_val,
    }

# Recursive record with bounded depth
@st.composite
def record(draw, max_depth=1):
    # At max depth, child must be null
    if max_depth <= 0:
        base = draw(base_record())
        base["child"] = None
        return base

    # Otherwise, child can be null or another record with max_depth-1
    base = draw(base_record())
    child_val = draw(st.one_of(st.none(), record(max_depth=max_depth - 1)))
    base["child"] = child_val
    return base

# Strategy to produce "almost" well-formed records with one or two subtle deviations
@st.composite
def generated_json(draw):
    # Start from a valid record with max_depth=1 (one level recursion)
    rec = draw(record(max_depth=1))

    # Introduce zero, one, or two subtle deviations to induce divergence
    # Possible deviations:
    # - Change type of a field (e.g. id as string instead of int)
    # - Omit a field (remove it)
    # - Replace a field with null when not expected
    # - Put an unexpected value in enum field (e.g. status)
    # - Put a non-string in tags array
    # - Put a non-object or invalid child (e.g. number instead of object/null)
    # - Put empty string in amount or weird string
    # We limit to 1 or 2 deviations to keep close to valid

    # Collect fields keys
    keys = list(rec.keys())

    # Number of deviations: 0, 1 or 2 (favor 1 or 2)
    deviation_count = draw(st.integers(min_value=1, max_value=2))

    # To track which fields we already modified
    modified_fields = set()

    for _ in range(deviation_count):
        # Pick a field to modify that is not modified yet
        possible_fields = [k for k in keys if k not in modified_fields]
        if not possible_fields:
            break
        field = draw(st.sampled_from(possible_fields))
        modified_fields.add(field)

        if field == "id":
            # id normally int, try string or float or null
            choice = draw(st.sampled_from(["string", "float", "null", "missing"]))
            if choice == "string":
                rec["id"] = draw(st.text(min_size=1, max_size=5))
            elif choice == "float":
                rec["id"] = draw(st.floats(allow_nan=False, allow_infinity=False))
            elif choice == "null":
                rec["id"] = None
            elif choice == "missing":
                del rec["id"]

        elif field == "amount":
            # amount normally string, try int, null, empty string, or missing
            choice = draw(st.sampled_from(["int", "null", "empty", "missing", "array"]))
            if choice == "int":
                rec["amount"] = draw(st.integers(min_value=0, max_value=1000))
            elif choice == "null":
                rec["amount"] = None
            elif choice == "empty":
                rec["amount"] = ""
            elif choice == "missing":
                del rec["amount"]
            elif choice == "array":
                rec["amount"] = draw(st.lists(st.text(min_size=1, max_size=3), max_size=3))

        elif field == "name":
            # name normally string or null, try int, bool, missing
            choice = draw(st.sampled_from(["int", "bool", "missing"]))
            if choice == "int":
                rec["name"] = draw(st.integers(min_value=0, max_value=100))
            elif choice == "bool":
                rec["name"] = draw(st.booleans())
            elif choice == "missing":
                del rec["name"]

        elif field == "status":
            # status normally one of three strings, try invalid string, null, missing
            choice = draw(st.sampled_from(["invalid_string", "null", "missing"]))
            if choice == "invalid_string":
                # string not in allowed enum
                rec["status"] = draw(st.text(min_size=1, max_size=10).filter(lambda s: s not in STATUS_VALUES))
            elif choice == "null":
                rec["status"] = None
            elif choice == "missing":
                del rec["status"]

        elif field == "tags":
            # tags normally array of strings, try array with non-string, null, missing, string instead of array
            choice = draw(st.sampled_from(["non_string_in_array", "null", "missing", "string"]))
            if choice == "non_string_in_array":
                # mix strings and ints or bools
                arr = draw(
                    st.lists(
                        st.one_of(
                            st.text(min_size=1, max_size=5),
                            st.integers(min_value=0, max_value=10),
                            st.booleans(),
                        ),
                        min_size=1,
                        max_size=5,
                    )
                )
                rec["tags"] = arr
            elif choice == "null":
                rec["tags"] = None
            elif choice == "missing":
                del rec["tags"]
            elif choice == "string":
                rec["tags"] = draw(st.text(min_size=1, max_size=10))

        elif field == "child":
            # child normally null or record object, try number, string, array, missing
            choice = draw(st.sampled_from(["number", "string", "array", "missing"]))
            if choice == "number":
                rec["child"] = draw(st.integers(min_value=0, max_value=100))
            elif choice == "string":
                rec["child"] = draw(st.text(min_size=1, max_size=10))
            elif choice == "array":
                rec["child"] = draw(st.lists(st.integers(min_value=0, max_value=10), max_size=3))
            elif choice == "missing":
                del rec["child"]

    # Serialize to JSON bytes
    # The document must be a JSON object (dict)
    # All keys present except those deliberately deleted above
    # The JSON must be syntactically valid, so json.dumps is safe
    json_bytes = json.dumps(rec, separators=(",", ":")).encode("utf-8")
    return json_bytes