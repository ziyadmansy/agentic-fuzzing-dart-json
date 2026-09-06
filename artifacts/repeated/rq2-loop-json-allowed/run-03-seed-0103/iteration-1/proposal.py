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
#
# To maximize chances of divergence:
# - We produce mostly valid documents but vary one or two fields subtly.
# - For example, "id" as int or a stringified int (wrong type).
# - "amount" normally string, but sometimes a number or null.
# - "name" null or string, sometimes empty string or unusual unicode.
# - "status" mostly valid enum, sometimes a string close but invalid.
# - "tags" mostly array of strings, sometimes empty array, sometimes array with null or numbers.
# - "child" either null or a nested record (depth limited to 1).
#
# We produce a dict and then json.dumps it to bytes.

@st.composite
def generated_json(draw) -> bytes:
    # Helper for "id": mostly int, sometimes stringified int (wrong type)
    id_val = draw(
        st.one_of(
            st.integers(min_value=0, max_value=10**9),
            st.text(min_size=1, max_size=10).filter(lambda s: s.isdigit()),
        )
    )

    # Helper for "amount": mostly string, sometimes number or null
    amount_val = draw(
        st.one_of(
            st.text(min_size=1, max_size=20),
            st.floats(allow_nan=False, allow_infinity=False).map(lambda f: str(f)),
            st.none(),
        )
    )
    # If amount_val is float string, keep as string; if none, keep as None

    # Helper for "name": string or null, sometimes empty or unicode
    name_val = draw(
        st.one_of(
            st.none(),
            st.text(min_size=0, max_size=20),
        )
    )

    # Helper for "status": mostly valid enum, sometimes close invalid string
    status_val = draw(
        st.one_of(
            st.sampled_from(["active", "inactive", "unknown"]),
            st.text(min_size=1, max_size=10).filter(
                lambda s: s not in {"active", "inactive", "unknown"}
            ),
        )
    )

    # Helper for "tags": mostly array of strings, sometimes empty, sometimes with null or numbers
    tags_val = draw(
        st.one_of(
            st.lists(st.text(min_size=1, max_size=10), min_size=0, max_size=5),
            st.lists(
                st.one_of(
                    st.text(min_size=1, max_size=10),
                    st.none(),
                    st.integers(min_value=0, max_value=100),
                ),
                min_size=0,
                max_size=5,
            ),
        )
    )

    # Recursive "child" record or null, depth limited to 1 (no grandchild)
    # To avoid infinite recursion, we define a helper function here:
    def child_record():
        # For child, we do not recurse further (child.child is always null)
        id_c = draw(
            st.one_of(
                st.integers(min_value=0, max_value=10**9),
                st.text(min_size=1, max_size=10).filter(lambda s: s.isdigit()),
            )
        )
        amount_c = draw(
            st.one_of(
                st.text(min_size=1, max_size=20),
                st.floats(allow_nan=False, allow_infinity=False).map(lambda f: str(f)),
                st.none(),
            )
        )
        name_c = draw(
            st.one_of(
                st.none(),
                st.text(min_size=0, max_size=20),
            )
        )
        status_c = draw(
            st.one_of(
                st.sampled_from(["active", "inactive", "unknown"]),
                st.text(min_size=1, max_size=10).filter(
                    lambda s: s not in {"active", "inactive", "unknown"}
                ),
            )
        )
        tags_c = draw(
            st.one_of(
                st.lists(st.text(min_size=1, max_size=10), min_size=0, max_size=5),
                st.lists(
                    st.one_of(
                        st.text(min_size=1, max_size=10),
                        st.none(),
                        st.integers(min_value=0, max_value=100),
                    ),
                    min_size=0,
                    max_size=5,
                ),
            )
        )
        return {
            "id": id_c,
            "amount": amount_c,
            "name": name_c,
            "status": status_c,
            "tags": tags_c,
            "child": None,
        }

    child_val = draw(st.one_of(st.none(), st.just(child_record())))

    record = {
        "id": id_val,
        "amount": amount_val,
        "name": name_val,
        "status": status_val,
        "tags": tags_val,
        "child": child_val,
    }

    # Serialize to JSON bytes
    return json.dumps(record).encode("utf-8")