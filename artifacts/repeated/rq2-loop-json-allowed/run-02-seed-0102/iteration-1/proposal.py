from hypothesis import strategies as st
import json

# We define a recursive strategy for the "child" field, bounded to one level of recursion.
# The record fields are:
# "id": integer
# "amount": string
# "name": string or null
# "status": one of "active", "inactive", "unknown"
# "tags": array of strings
# "child": Record or null (one level recursion)

# To maximize chances of divergence:
# - We vary types subtly: e.g. amount as string but sometimes numeric-looking strings,
#   or strings with unicode escapes.
# - name: sometimes null, sometimes string, sometimes empty string.
# - status: only the three allowed strings.
# - tags: empty list, list with empty string, list with unicode strings.
# - child: null or a record with the same schema, but no further recursion.

# We also introduce subtle variations that might cause some implementations to fail or decode differently:
# - amount: numeric strings, strings with leading zeros, strings with spaces, strings with unicode escapes.
# - tags: empty strings, strings with spaces, strings with unicode escapes.
# - name: null, empty string, string with spaces, string with unicode escapes.
# - id: integers, including zero and negative numbers (if allowed by the schema, but schema says integer, no range specified)
#   We keep id as integer but include zero and negative to test boundaries.
# - child: null or a record with the same schema but no further recursion.

@st.composite
def generated_json(draw) -> bytes:
    # Define the base record strategy without recursion first
    def record_strategy():
        # id: integer, include zero and negative to test boundaries
        id_val = st.integers(min_value=-1000, max_value=1000)
        # amount: string, but with variations that might confuse parsers
        # Examples: "0", "000123", " 123", "12\u0033", "12\n3"
        amount_str = st.one_of(
            st.text(min_size=1, max_size=10),  # arbitrary string
            st.integers(min_value=0, max_value=100000).map(str),  # numeric strings
            st.just("000123"),
            st.just(" 123"),
            st.just("12\u0033"),
            st.just("12\n3"),
        )
        # name: string or null, with empty string and unicode escapes
        name_str = st.one_of(
            st.none(),
            st.just(""),
            st.text(min_size=1, max_size=10),
            st.just("na\u00EFve"),
            st.just("null"),  # string "null" to test confusion with null
        )
        # status: one of "active", "inactive", "unknown"
        status_val = st.sampled_from(["active", "inactive", "unknown"])
        # tags: array of strings, including empty strings, unicode, spaces
        tag_str = st.one_of(
            st.just(""),
            st.text(min_size=1, max_size=10),
            st.just("tag\u00E9"),
            st.just(" "),
        )
        tags_arr = st.lists(tag_str, min_size=0, max_size=5)
        # child: null or record (one level recursion)
        # We'll define child later to avoid recursion issues

        return st.fixed_dictionaries({
            "id": id_val,
            "amount": amount_str,
            "name": name_str,
            "status": status_val,
            "tags": tags_arr,
            # child to be filled later
        })

    # Now define the full record with child field
    # child is either null or a record without child (to avoid deep recursion)
    base_record = record_strategy()

    # child record without child field (child always null)
    child_record = record_strategy().map(lambda d: {**d, "child": None})

    # Now draw the top-level record
    top = draw(base_record)

    # Draw child: null or child_record
    child_val = draw(st.one_of(st.none(), child_record))

    top["child"] = child_val

    # Serialize to JSON bytes
    return json.dumps(top, ensure_ascii=False).encode("utf-8")