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

# To maximize divergence, we produce mostly well-formed records but vary one or two fields subtly:
# - sometimes "id" as a string instead of int
# - sometimes "amount" as a number instead of string
# - sometimes "name" missing (should always be present, but we keep it present to avoid all rejecting)
# - sometimes "name" as an integer or boolean instead of string/null
# - sometimes "status" as a string not in the enum or null
# - sometimes "tags" as array of strings, or array with non-string elements, or empty array
# - sometimes "child" null, or a nested record with one field subtly wrong
#
# We do not omit fields (all six fields always present) but vary types subtly to trigger divergence.
#
# We limit recursion depth to 1 (child can have child=null only).
#
# We produce syntactically valid JSON always.

@st.composite
def generated_json(draw) -> bytes:
    # Helper to produce a valid or subtly invalid "id"
    def id_strategy():
        # Mostly int, sometimes string (should be int)
        return st.one_of(
            st.integers(min_value=0, max_value=2**31-1),
            st.text(min_size=1, max_size=5).filter(lambda s: not s.isdigit()),  # non-digit string to cause type error
        )

    # Helper for amount: mostly string, sometimes number (should be string)
    def amount_strategy():
        return st.one_of(
            st.text(min_size=1, max_size=10),
            st.floats(allow_nan=False, allow_infinity=False).map(lambda f: str(f)),  # stringified float, valid string
            st.integers(min_value=0, max_value=100000).map(str),
            st.integers(min_value=0, max_value=100000),  # integer number instead of string
            st.floats(allow_nan=False, allow_infinity=False),  # float number instead of string
        )

    # Helper for name: string or null normally, sometimes int or bool
    def name_strategy():
        return st.one_of(
            st.none(),
            st.text(min_size=0, max_size=20),
            st.integers(min_value=-100, max_value=100),
            st.booleans(),
        )

    # Helper for status: mostly valid enum, sometimes invalid string or null
    def status_strategy():
        valid = st.sampled_from(["active", "inactive", "unknown"])
        invalid = st.one_of(
            st.text(min_size=1, max_size=10).filter(lambda s: s not in {"active", "inactive", "unknown"}),
            st.none(),
            st.integers(min_value=0, max_value=10),
        )
        # Bias towards valid but sometimes invalid
        return st.one_of(valid, invalid)

    # Helper for tags: array of strings normally, sometimes array with non-string elements
    def tags_strategy():
        str_elem = st.text(min_size=1, max_size=10)
        non_str_elem = st.one_of(
            st.integers(min_value=0, max_value=100),
            st.booleans(),
            st.none(),
            st.floats(allow_nan=False, allow_infinity=False),
        )
        # Mostly strings, sometimes mixed
        elems = st.lists(st.one_of(str_elem, non_str_elem), min_size=0, max_size=5)
        return elems

    # Recursive record strategy with max depth 1
    def record_strategy(depth=0):
        # If depth > 0, child must be null to avoid deep recursion
        child_strategy = st.none() if depth > 0 else record_strategy(depth=depth+1)

        return st.fixed_dictionaries({
            "id": id_strategy(),
            "amount": amount_strategy(),
            "name": name_strategy(),
            "status": status_strategy(),
            "tags": tags_strategy(),
            "child": st.one_of(child_strategy, st.none()),
        })

    # Draw a record
    record = draw(record_strategy())

    # Serialize to JSON bytes
    # Use separators to avoid trailing spaces (not necessary but cleaner)
    json_bytes = json.dumps(record, separators=(",", ":")).encode("utf-8")
    return json_bytes