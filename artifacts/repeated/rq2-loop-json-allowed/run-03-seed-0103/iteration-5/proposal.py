from hypothesis import strategies as st
import json

# We define a recursive strategy for the "child" field with bounded depth.
# The record fields:
# - id: integer
# - amount: string (normally numeric string, but we will vary)
# - name: string or null
# - status: one of "active", "inactive", "unknown"
# - tags: array of strings
# - child: either null or another record (one level recursion normally)

# To maximize divergence, we will:
# - Vary "amount" with numeric strings, non-numeric strings, empty string, and strings with whitespace.
# - Vary "name" with string, null, empty string, or numeric string (wrong type but still string)
# - Vary "status" with correct enum values, and sometimes a string close to enum but invalid (e.g. "Active", "inactive ").
# - Vary "tags" with empty list, list of strings, list with non-string elements (e.g. numbers as strings or numbers as numbers)
# - Vary "child" with null or a nested record (one level max)
# - Vary "id" with integers, sometimes negative or zero (if allowed)
#
# We will produce syntactically valid JSON objects only.
# We will produce documents that are almost valid but with one or two fields off type or value.

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for fields
    
    # id: integer, including zero and negative to test boundaries
    id_strategy = st.integers(min_value=-10, max_value=1000)
    
    # amount: mostly numeric strings, but also some non-numeric or borderline
    amount_numeric_str = st.integers(min_value=0, max_value=10**6).map(str)
    amount_non_numeric_str = st.sampled_from(["", " 123", "12.34.56", "NaN", "inf", "-123", "0x10", "one hundred"])
    amount_strategy = st.one_of(amount_numeric_str, amount_non_numeric_str)
    
    # name: string or null, also empty string, numeric string, or whitespace string
    name_str = st.one_of(
        st.none(),
        st.text(min_size=0, max_size=20),
        st.just(""),
        st.integers(min_value=0, max_value=1000).map(str),
        st.just("   "),
    )
    
    # status: mostly valid enum, sometimes invalid close strings
    valid_status = st.sampled_from(["active", "inactive", "unknown"])
    invalid_status = st.sampled_from(["Active", "inactive ", "unknown\n", "actve", "inactiv", ""])
    status_strategy = st.one_of(valid_status, invalid_status)
    
    # tags: array of strings, sometimes empty, sometimes with non-string elements as strings (to keep JSON valid)
    # We keep elements as strings but sometimes empty strings or whitespace strings
    tag_str = st.one_of(
        st.text(min_size=1, max_size=10),
        st.just(""),
        st.just(" "),
        st.integers(min_value=0, max_value=1000).map(str),
    )
    tags_strategy = st.lists(tag_str, min_size=0, max_size=5)
    
    # Recursive record for child, max depth 1
    # To avoid infinite recursion, we define a helper function
    
    def record_strategy(depth=0):
        # If depth > 1, child is always null
        if depth > 1:
            child_strategy = st.just(None)
        else:
            # child is either null or another record at depth+1
            child_strategy = st.one_of(st.just(None), record_strategy(depth + 1))
        
        return st.builds(
            lambda id_, amount, name, status, tags, child: {
                "id": id_,
                "amount": amount,
                "name": name,
                "status": status,
                "tags": tags,
                "child": child,
            },
            id_strategy,
            amount_strategy,
            name_str,
            status_strategy,
            tags_strategy,
            child_strategy,
        )
    
    record = draw(record_strategy(depth=0))
    # Serialize to JSON bytes
    return json.dumps(record).encode("utf-8")