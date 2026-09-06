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
#   "child": <Record or null>
# }
#
# To maximize chances of divergence:
# - We produce mostly valid fields, but vary one or two fields subtly:
#   * "id" as int normally, but sometimes as a stringified int or float to test type coercion.
#   * "amount" as string normally, but sometimes numeric or null or empty string.
#   * "name" as string or null, but sometimes empty string or number.
#   * "status" as one of the three strings normally, but sometimes uppercase or misspelled.
#   * "tags" as array of strings normally, but sometimes empty array, or array with non-string elements.
#   * "child" as null or nested record, but sometimes missing or wrong type.
#
# We keep the JSON syntactically valid and all fields present (except for "child" which can be null).
# We vary only one or two fields per example to isolate divergences.

# Helper to produce a valid "status" or a near miss:
status_values = st.sampled_from(["active", "inactive", "unknown"])
status_typo = st.sampled_from(["Active", "INACTIVE", "unknown ", "unkn0wn", ""])  # subtle typos

@st.composite
def id_field(draw):
    # Mostly int, sometimes stringified int, sometimes float (should be rejected)
    choice = draw(st.integers(min_value=0, max_value=1))
    if choice == 0:
        return draw(st.integers(min_value=0, max_value=10000))
    else:
        # stringified int or float string
        as_str = draw(st.one_of(
            st.integers(min_value=0, max_value=10000).map(str),
            st.floats(min_value=0, max_value=10000).map(lambda f: format(f, '.2f'))
        ))
        return as_str

@st.composite
def amount_field(draw):
    # Mostly string representing a decimal number, sometimes empty string, sometimes numeric (should be rejected)
    choice = draw(st.integers(min_value=0, max_value=2))
    if choice == 0:
        # valid decimal string
        return draw(st.decimals(min_value=0, max_value=10000, places=2)).to_eng_string()
    elif choice == 1:
        # empty string
        return ""
    else:
        # numeric type (int or float) instead of string
        return draw(st.one_of(st.integers(min_value=0, max_value=10000), st.floats(min_value=0, max_value=10000)))

@st.composite
def name_field(draw):
    # string or null normally, sometimes number or empty string
    choice = draw(st.integers(min_value=0, max_value=3))
    if choice == 0:
        return draw(st.one_of(st.none(), st.text(min_size=1, max_size=20)))
    elif choice == 1:
        return ""
    elif choice == 2:
        return None
    else:
        return draw(st.integers(min_value=0, max_value=1000))

@st.composite
def status_field(draw):
    # Mostly valid status, sometimes typo or uppercase
    choice = draw(st.integers(min_value=0, max_value=3))
    if choice == 0:
        return draw(status_values)
    else:
        return draw(status_typo)

@st.composite
def tags_field(draw):
    # Mostly array of strings, sometimes empty array, sometimes array with non-string elements
    choice = draw(st.integers(min_value=0, max_value=2))
    if choice == 0:
        # valid array of strings (1 to 5 elements)
        return draw(st.lists(st.text(min_size=1, max_size=10), min_size=1, max_size=5))
    elif choice == 1:
        # empty array
        return []
    else:
        # array with mixed types (strings and ints)
        length = draw(st.integers(min_value=1, max_value=5))
        elements = []
        for _ in range(length):
            elements.append(draw(st.one_of(st.text(min_size=1, max_size=10), st.integers(min_value=0, max_value=1000))))
        return elements

@st.composite
def child_field(draw, max_depth=1):
    # null or nested record if max_depth > 0
    if max_depth <= 0:
        return None
    choice = draw(st.integers(min_value=0, max_value=2))
    if choice == 0:
        return None
    elif choice == 1:
        # nested record with max_depth-1
        return draw(record_strategy(max_depth=max_depth-1))
    else:
        # invalid type for child (e.g. string or number)
        return draw(st.one_of(st.text(min_size=1, max_size=10), st.integers(min_value=0, max_value=1000), st.floats(min_value=0, max_value=1000)))

@st.composite
def record_strategy(draw, max_depth=1):
    # Compose a record dict with all fields present, varying one or two fields subtly.
    # To isolate divergences, we pick one or two fields to be "off" and others valid.
    # We pick which fields to "corrupt" here:
    fields = ["id", "amount", "name", "status", "tags", "child"]
    # Pick 0, 1 or 2 fields to corrupt
    corrupt_count = draw(st.integers(min_value=0, max_value=2))
    corrupt_fields = draw(st.lists(st.sampled_from(fields), min_size=corrupt_count, max_size=corrupt_count, unique=True))

    # Build each field, corrupted or valid
    def gen_field(field):
        if field == "id":
            if "id" in corrupt_fields:
                return draw(id_field())
            else:
                # valid int id
                return draw(st.integers(min_value=0, max_value=10000))
        elif field == "amount":
            if "amount" in corrupt_fields:
                return draw(amount_field())
            else:
                # valid decimal string
                return draw(st.decimals(min_value=0, max_value=10000, places=2)).to_eng_string()
        elif field == "name":
            if "name" in corrupt_fields:
                return draw(name_field())
            else:
                # valid string or null
                return draw(st.one_of(st.none(), st.text(min_size=1, max_size=20)))
        elif field == "status":
            if "status" in corrupt_fields:
                return draw(status_field())
            else:
                return draw(status_values)
        elif field == "tags":
            if "tags" in corrupt_fields:
                return draw(tags_field())
            else:
                # valid array of strings
                return draw(st.lists(st.text(min_size=1, max_size=10), min_size=1, max_size=5))
        elif field == "child":
            if "child" in corrupt_fields:
                return draw(child_field(max_depth=max_depth))
            else:
                # valid null or nested record
                return draw(st.one_of(st.none(), record_strategy(max_depth=max_depth-1) if max_depth > 0 else st.just(None)))
        else:
            # Should not happen
            return None

    record = {f: gen_field(f) for f in fields}
    return record

@st.composite
def generated_json(draw) -> bytes:
    # Generate one record with max_depth=1 for child recursion
    record = draw(record_strategy(max_depth=1))
    # Serialize to JSON bytes
    json_text = json.dumps(record, separators=(',', ':'))
    return json_text.encode('utf-8')