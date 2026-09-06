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

# To maximize divergence, we produce mostly well-formed documents but
# occasionally tweak one or two fields to be subtly off:
# - "id" as int normally, but sometimes as string or float
# - "amount" as string normally, but sometimes as number or null
# - "name" as string or null normally, but sometimes as empty array or int
# - "status" as one of the three strings normally, but sometimes as uppercase or misspelled string
# - "tags" as array of strings normally, but sometimes as array with non-string elements or empty string elements
# - "child" as null or nested record normally, but sometimes as empty object or wrong type

# We keep the structure mostly valid JSON objects, no missing fields,
# but with subtle type or value deviations.

# We limit recursion depth to 1 (child can have child=null only).

@st.composite
def generated_json(draw) -> bytes:
    # Helper to generate a valid or subtly invalid "id"
    def id_strategy():
        # 80% int, 10% stringified int, 10% float
        return st.one_of(
            st.integers(min_value=0, max_value=10**9).map(int),
            st.integers(min_value=0, max_value=10**9).map(lambda x: str(x)),
            st.floats(min_value=0, max_value=10**9, allow_nan=False, allow_infinity=False),
        )

    # Helper to generate "amount" as string normally, sometimes number or null
    def amount_strategy():
        # 85% string of digits with optional decimal, 10% float, 5% null
        str_amount = st.text(min_size=1, max_size=10).filter(lambda s: all(c in "0123456789." for c in s) and s.count('.') <= 1)
        return st.one_of(
            str_amount,
            st.floats(min_value=0, max_value=10**9, allow_nan=False, allow_infinity=False),
            st.none(),
        )

    # Helper for "name": string or null normally, sometimes int or empty array
    def name_strategy():
        return st.one_of(
            st.none(),
            st.text(min_size=0, max_size=20),
            st.integers(min_value=0, max_value=1000),
            st.just([]),
        )

    # Helper for "status": mostly correct strings, sometimes uppercase or misspelled
    def status_strategy():
        correct = st.sampled_from(["active", "inactive", "unknown"])
        uppercase = st.sampled_from(["ACTIVE", "INACTIVE", "UNKNOWN"])
        misspelled = st.sampled_from(["actve", "inactiv", "unknwn"])
        return st.one_of(correct, uppercase, misspelled)

    # Helper for "tags": array of strings normally, sometimes with non-string or empty string
    def tags_strategy():
        # normal string tags: nonempty ascii words
        normal_tags = st.lists(st.text(min_size=1, max_size=10), min_size=0, max_size=5)
        # tags with some non-string elements or empty string
        mixed_tags = st.lists(
            st.one_of(
                st.text(min_size=0, max_size=10),
                st.integers(min_value=0, max_value=100),
                st.none(),
                st.lists(st.integers(), max_size=1),
            ),
            min_size=0,
            max_size=5,
        )
        return st.one_of(normal_tags, mixed_tags)

    # Recursive record strategy with depth control
    def record_strategy(depth=0):
        # child is null or record if depth==0, else null only
        if depth == 0:
            child_strat = st.one_of(
                st.none(),
                record_strategy(depth=1),
                # subtle invalid: empty object or wrong type
                st.just({}),
                st.integers(min_value=0, max_value=100),
            )
        else:
            child_strat = st.none()

        return st.fixed_dictionaries({
            "id": id_strategy(),
            "amount": amount_strategy(),
            "name": name_strategy(),
            "status": status_strategy(),
            "tags": tags_strategy(),
            "child": child_strat,
        })

    # Draw one record at depth 0
    record = draw(record_strategy(depth=0))

    # Serialize to JSON bytes
    # Use separators to minimize whitespace but keep valid JSON
    json_bytes = json.dumps(record, separators=(',', ':')).encode('utf-8')
    return json_bytes