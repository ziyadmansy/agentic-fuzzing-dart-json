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

# To maximize divergence:
# - We produce mostly well-formed records but vary one or two fields subtly.
# - For example, "id" as int normally, but sometimes as string or float.
# - "amount" normally string, but sometimes number or null or empty string.
# - "name" normally string or null, but sometimes number or boolean.
# - "status" normally one of three strings, but sometimes a similar string or uppercase.
# - "tags" normally array of strings, but sometimes empty array, or array with null or numbers.
# - "child" normally null or record, but sometimes a wrong type or partial record.
#
# We do not produce invalid JSON syntax.
# We keep recursion depth bounded to 2 (root + child).

@st.composite
def generated_json(draw, _depth=0):
    # Limit recursion depth to 1 (root) + 1 (child)
    max_depth = 1

    # id: mostly int, sometimes stringified int, sometimes float, sometimes negative or zero
    id_val = draw(
        st.one_of(
            st.integers(min_value=0, max_value=10**9),
            st.text(min_size=1, max_size=10).filter(lambda s: s.isdigit()),  # string digits
            st.floats(min_value=0, max_value=10**9, allow_nan=False, allow_infinity=False),
            st.integers(min_value=-1000, max_value=-1),
        )
    )

    # amount: normally string representing a number, sometimes empty string, sometimes number type, sometimes null
    amount_val = draw(
        st.one_of(
            st.text(min_size=1, max_size=20).filter(lambda s: all(c in "0123456789.-" for c in s)),
            st.just(""),  # empty string
            st.floats(allow_nan=False, allow_infinity=False).map(lambda f: str(f)),
            st.integers().map(str),
            st.none(),
        )
    )
    # If amount_val is None, replace with JSON null (which is None in Python)
    if amount_val is None:
        amount_val = None

    # name: string or null normally, sometimes int, bool, empty string, or whitespace string
    name_val = draw(
        st.one_of(
            st.none(),
            st.text(min_size=1, max_size=20),
            st.integers(min_value=-1000, max_value=1000),
            st.booleans(),
            st.just(""),
            st.just("   "),
        )
    )

    # status: one of "active", "inactive", "unknown" normally,
    # sometimes uppercase, sometimes misspelled, sometimes null or number
    status_val = draw(
        st.one_of(
            st.sampled_from(["active", "inactive", "unknown"]),
            st.sampled_from(["ACTIVE", "INACTIVE", "UNKNOWN"]),
            st.sampled_from(["activ", "inactiv", "unknwn"]),
            st.none(),
            st.integers(min_value=0, max_value=2),
        )
    )

    # tags: array of strings normally, sometimes empty array,
    # sometimes array with null, numbers, booleans, or mixed types
    tag_str = st.text(min_size=1, max_size=10)
    tags_val = draw(
        st.lists(
            st.one_of(
                tag_str,
                st.none(),
                st.integers(min_value=0, max_value=100),
                st.booleans(),
            ),
            min_size=0,
            max_size=5,
        )
    )

    # child: null or record (recursion), sometimes wrong type (string, number, bool)
    if _depth < max_depth:
        child_val = draw(
            st.one_of(
                st.none(),
                generated_json(_depth=_depth + 1),
                st.text(min_size=1, max_size=10),
                st.integers(min_value=0, max_value=100),
                st.booleans(),
            )
        )
    else:
        child_val = None

    record = {
        "id": id_val,
        "amount": amount_val,
        "name": name_val,
        "status": status_val,
        "tags": tags_val,
        "child": child_val,
    }

    # Serialize to JSON bytes
    # Use separators to minimize whitespace (not required, but cleaner)
    json_text = json.dumps(record, separators=(",", ":"))
    return json_text.encode("utf-8")