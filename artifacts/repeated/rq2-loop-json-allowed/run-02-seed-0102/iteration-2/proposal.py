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
# - We vary "id" near integer boundaries and also sometimes as a float (which is invalid but JSON-valid).
# - "amount" is always a string but sometimes numeric-looking strings, sometimes empty, sometimes with whitespace.
# - "name" is string or null, but sometimes empty string or whitespace string.
# - "status" is one of the three strings, but sometimes with trailing spaces or uppercase variants (which might cause enum parsing issues).
# - "tags" is an array of strings, but sometimes empty, sometimes with empty strings, sometimes with null (which is invalid but JSON-valid).
# - "child" is either null or a nested record, but we limit recursion depth to 1.
#
# We also sometimes omit fields or replace them with wrong types to trigger divergence.
# However, the prompt says all six fields are always present in a well-formed document,
# so we keep all fields present but vary their types subtly to trigger divergence.

@st.composite
def generated_json(draw) -> bytes:
    # Helper to produce "id" field with subtle variations:
    # Usually an integer, but sometimes a float or a stringified int.
    id_val = draw(
        st.one_of(
            st.integers(min_value=0, max_value=2**31 - 1),
            st.floats(min_value=0, max_value=2**31 - 1, allow_nan=False, allow_infinity=False),
            st.text(min_size=1, max_size=10).filter(lambda s: s.isdigit()),
        )
    )

    # "amount" must be a string, but we vary content:
    # numeric strings, empty string, whitespace, or strings with leading zeros
    amount_val = draw(
        st.one_of(
            st.from_regex(r"^\d+(\.\d+)?$", fullmatch=True),  # numeric string
            st.just(""),  # empty string
            st.just("  "),  # whitespace string
            st.from_regex(r"^0\d+$", fullmatch=True),  # leading zeros
            st.text(min_size=1, max_size=5).filter(lambda s: not s.isspace()),
        )
    )

    # "name" is string or null, but sometimes empty or whitespace string
    name_val = draw(
        st.one_of(
            st.none(),
            st.just(""),
            st.just(" "),
            st.text(min_size=1, max_size=10),
        )
    )

    # "status" is one of "active", "inactive", "unknown"
    # We add variants with trailing spaces or uppercase to test enum parsing
    status_val = draw(
        st.one_of(
            st.sampled_from(["active", "inactive", "unknown"]),
            st.sampled_from(["active ", "inactive ", "unknown "]),
            st.sampled_from(["ACTIVE", "INACTIVE", "UNKNOWN"]),
        )
    )

    # "tags" is array of strings, but sometimes empty, sometimes with empty strings,
    # sometimes with null (which is invalid but JSON-valid)
    tags_val = draw(
        st.lists(
            st.one_of(
                st.text(min_size=0, max_size=10),
                st.none(),
            ),
            min_size=0,
            max_size=5,
        )
    )

    # Recursive child record or null, depth limited to 1
    # To avoid infinite recursion, we do not recurse further inside child.
    def child_record():
        # For child, we do not recurse further (child: null or no child)
        child_id = draw(
            st.one_of(
                st.integers(min_value=0, max_value=2**31 - 1),
                st.floats(min_value=0, max_value=2**31 - 1, allow_nan=False, allow_infinity=False),
                st.text(min_size=1, max_size=10).filter(lambda s: s.isdigit()),
            )
        )
        child_amount = draw(
            st.one_of(
                st.from_regex(r"^\d+(\.\d+)?$", fullmatch=True),
                st.just(""),
                st.just("  "),
                st.from_regex(r"^0\d+$", fullmatch=True),
                st.text(min_size=1, max_size=5).filter(lambda s: not s.isspace()),
            )
        )
        child_name = draw(
            st.one_of(
                st.none(),
                st.just(""),
                st.just(" "),
                st.text(min_size=1, max_size=10),
            )
        )
        child_status = draw(
            st.one_of(
                st.sampled_from(["active", "inactive", "unknown"]),
                st.sampled_from(["active ", "inactive ", "unknown "]),
                st.sampled_from(["ACTIVE", "INACTIVE", "UNKNOWN"]),
            )
        )
        child_tags = draw(
            st.lists(
                st.one_of(
                    st.text(min_size=0, max_size=10),
                    st.none(),
                ),
                min_size=0,
                max_size=5,
            )
        )
        # child of child is always null to limit recursion
        return {
            "id": child_id,
            "amount": child_amount,
            "name": child_name,
            "status": child_status,
            "tags": child_tags,
            "child": None,
        }

    child_val = draw(st.one_of(st.none(), st.just(child_record())))

    # Compose the full record
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