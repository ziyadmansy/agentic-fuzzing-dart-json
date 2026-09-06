from hypothesis import strategies as st
import json

# We define a recursive strategy for the "child" field with bounded depth.
# The record schema:
# {
#   "id": <integer>,
#   "amount": <string>,
#   "name": <string or null>,
#   "status": <one of "active", "inactive", "unknown">,
#   "tags": <array of strings>,
#   "child": <Record or null, one level of recursion normally>
# }

# To maximize chances of divergence:
# - We produce mostly well-formed documents, but vary one or two fields subtly.
# - For example, "amount" is always a string, but sometimes we put numeric strings,
#   sometimes empty strings, sometimes strings with whitespace or unusual chars.
# - For "name", we sometimes use null, sometimes strings, sometimes empty strings.
# - For "status", we sometimes use the exact allowed strings, sometimes a string close but invalid.
# - For "tags", we use arrays of strings, but sometimes empty arrays, sometimes arrays with empty strings.
# - For "child", we recurse with depth limit 1, sometimes null, sometimes a record with one field subtly off.
# - We also try subtle type violations on one field at a time (e.g. "id" as string instead of int)
#   but only one field per document to avoid broad malformation.

# This approach aligns with the hint: "almost well-formed with one specific thing off".

# We define a helper for a valid record, then a helper for a record with one field subtly off.

# Allowed statuses:
statuses = st.sampled_from(["active", "inactive", "unknown"])

# Valid string for amount: nonempty numeric strings, or empty, or whitespace variants
valid_amount_str = st.one_of(
    st.from_regex(r"^\d+(\.\d+)?$", fullmatch=True),  # numeric string
    st.just(""),  # empty string
    st.just("  "),  # whitespace only
    st.just("0"),  # zero
    st.just("123.00"),  # decimal with trailing zeros
)

# Valid name: string or null
valid_name = st.one_of(st.none(), st.text(min_size=0, max_size=20))

# Valid tags: list of strings (including empty strings), length 0 to 5
valid_tags = st.lists(st.text(min_size=0, max_size=10), min_size=0, max_size=5)

# Valid id: integer in a reasonable range
valid_id = st.integers(min_value=0, max_value=1000000)

# Valid child: either null or a record (depth 1)
# We'll define a recursive function below.

def valid_record(draw, depth=0):
    # depth limit 1
    if depth > 1:
        return None
    return {
        "id": draw(valid_id),
        "amount": draw(valid_amount_str),
        "name": draw(valid_name),
        "status": draw(statuses),
        "tags": draw(valid_tags),
        "child": draw(st.one_of(st.none(), st.deferred(lambda: valid_record(draw, depth + 1)))),
    }

# Now define a strategy for a record with exactly one subtle violation:
# We pick one field to "break" in a subtle way, others valid.

# Possible subtle violations per field:
# - id: string instead of int (e.g. numeric string), or float
# - amount: number instead of string, or boolean, or null
# - name: number instead of string/null, or boolean
# - status: invalid string close to allowed ones, or number
# - tags: array with non-string element, or null instead of array
# - child: invalid type (e.g. string), or a child record with one subtle violation recursively

# We'll implement a function that returns a dict with one field subtly broken.

@st.composite
def record_with_one_violation(draw, depth=0):
    # Start with a valid record
    base = yield st.just(None)  # placeholder to use draw
    base = {
        "id": draw(valid_id),
        "amount": draw(valid_amount_str),
        "name": draw(valid_name),
        "status": draw(statuses),
        "tags": draw(valid_tags),
        "child": draw(st.one_of(st.none(), st.deferred(lambda: record_with_one_violation(depth=depth+1) if depth < 1 else st.none()))),
    }

    # Choose one field to break
    field_to_break = draw(st.sampled_from(["id", "amount", "name", "status", "tags", "child"]))

    if field_to_break == "id":
        # id as string numeric or float
        broken_id = draw(st.one_of(
            st.from_regex(r"^\d+$", fullmatch=True),
            st.floats(allow_nan=False, allow_infinity=False).map(lambda f: str(f)),
        ))
        base["id"] = broken_id

    elif field_to_break == "amount":
        # amount as number, boolean, or null
        broken_amount = draw(st.one_of(
            st.integers(min_value=0, max_value=10000),
            st.floats(allow_nan=False, allow_infinity=False),
            st.booleans(),
            st.none(),
        ))
        base["amount"] = broken_amount

    elif field_to_break == "name":
        # name as number or boolean (instead of string or null)
        broken_name = draw(st.one_of(
            st.integers(min_value=0, max_value=10000),
            st.floats(allow_nan=False, allow_infinity=False),
            st.booleans(),
        ))
        base["name"] = broken_name

    elif field_to_break == "status":
        # status as invalid string close to allowed ones or number
        broken_status = draw(st.one_of(
            st.sampled_from(["activ", "inactiv", "unknwon", "active ", " inactive"]),
            st.integers(min_value=0, max_value=10),
            st.floats(allow_nan=False, allow_infinity=False),
        ))
        base["status"] = broken_status

    elif field_to_break == "tags":
        # tags as array with one non-string element or null
        choice = draw(st.booleans())
        if choice:
            # null instead of array
            base["tags"] = None
        else:
            # array with one non-string element
            good_strings = draw(st.lists(st.text(min_size=0, max_size=10), min_size=0, max_size=4))
            non_string = draw(st.one_of(
                st.integers(),
                st.floats(allow_nan=False, allow_infinity=False),
                st.booleans(),
                st.none(),
                st.dictionaries(keys=st.text(), values=st.integers()),
            ))
            # Insert non-string element at random position
            pos = draw(st.integers(min_value=0, max_value=len(good_strings)))
            tags = good_strings[:pos] + [non_string] + good_strings[pos:]
            base["tags"] = tags

    elif field_to_break == "child":
        # child as invalid type or child record with one violation (if depth < 1)
        choice = draw(st.integers(min_value=0, max_value=2))
        if choice == 0:
            # invalid type: string, number, boolean, or empty array
            base["child"] = draw(st.one_of(
                st.text(min_size=0, max_size=10),
                st.integers(),
                st.floats(allow_nan=False, allow_infinity=False),
                st.booleans(),
                st.lists(st.integers(), max_size=0),
            ))
        elif choice == 1 and depth < 1:
            # child record with one violation recursively
            base["child"] = yield record_with_one_violation(depth=depth+1)
        else:
            # null
            base["child"] = None

    return base

@st.composite
def generated_json(draw) -> bytes:
    # 50% chance to produce a valid record, 50% chance to produce record with one violation
    valid_or_broken = draw(st.booleans())
    if valid_or_broken:
        # valid record with bounded recursion depth 1
        rec = draw(valid_record)
    else:
        rec = draw(record_with_one_violation())

    # Serialize to JSON bytes
    return json.dumps(rec, separators=(',', ':')).encode("utf-8")