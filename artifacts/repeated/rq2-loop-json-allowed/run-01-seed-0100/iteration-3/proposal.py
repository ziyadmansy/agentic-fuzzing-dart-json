from hypothesis import strategies as st
import json

# We define a bounded recursive strategy for the "child" field.
# The recursion depth is limited to 1 level as per the spec.
# We produce dicts with all six fields always present.
# We introduce subtle type variations and boundary values on one or two fields at a time,
# to maximize chances of divergence.

# The "status" field must be one of "active", "inactive", "unknown".
# We'll sometimes produce invalid strings or null to provoke divergence.

# The "amount" field is a string, but we can vary its content to be numeric strings,
# empty string, or strings that look like numbers but with slight invalidity.

# The "name" field can be string or null, but we can try empty string, or numeric strings,
# or even boolean values (which is invalid but might be accepted differently).

# The "tags" field is an array of strings; we can try empty array, array with empty string,
# array with null, or array with numbers (invalid).

# The "id" field is integer, but we can try boundary values (0, negative, very large),
# or sometimes a string that looks like an integer (invalid).

# We'll produce mostly valid documents but with one or two fields subtly off.

@st.composite
def generated_json(draw) -> bytes:
    # Helper strategies for fields with subtle invalidities

    # id: mostly int, sometimes stringified int, sometimes float or negative
    id_val = draw(
        st.one_of(
            st.integers(min_value=0, max_value=2**31 - 1),
            st.text(min_size=1, max_size=10).filter(lambda s: not s.isdigit()),  # invalid string id
            st.floats(allow_nan=False, allow_infinity=False).map(lambda f: int(f) if f > 0 else -1),
        )
    )

    # amount: string, mostly numeric strings, sometimes empty, sometimes with spaces, sometimes invalid numeric
    amount_val = draw(
        st.one_of(
            st.text(min_size=1, max_size=10).filter(lambda s: s.strip() != ""),  # non-empty string
            st.just(""),  # empty string
            st.just(" 123 "),  # string with spaces
            st.just("-123.45"),  # negative number string
            st.just("NaN"),  # invalid numeric string
        )
    )

    # name: string or null, sometimes boolean or number to provoke divergence
    name_val = draw(
        st.one_of(
            st.none(),
            st.text(min_size=0, max_size=20),
            st.integers(min_value=0, max_value=100).map(str),
            st.booleans(),
        )
    )

    # status: mostly valid enum strings, sometimes invalid strings or null
    status_val = draw(
        st.one_of(
            st.sampled_from(["active", "inactive", "unknown"]),
            st.text(min_size=1, max_size=10).filter(lambda s: s not in {"active", "inactive", "unknown"}),
            st.none(),
        )
    )

    # tags: array of strings, sometimes with null or numbers inside
    tags_val = draw(
        st.lists(
            st.one_of(
                st.text(min_size=0, max_size=10),
                st.none(),
                st.integers(min_value=0, max_value=100),
                st.booleans(),
            ),
            min_size=0,
            max_size=5,
        )
    )

    # child: either null or a nested record with same schema but no further recursion
    # To avoid infinite recursion, child.child is always null.
    def child_record():
        # id for child: mostly int, sometimes string
        child_id = draw(
            st.one_of(
                st.integers(min_value=0, max_value=2**31 - 1),
                st.text(min_size=1, max_size=10).filter(lambda s: not s.isdigit()),
            )
        )
        child_amount = draw(
            st.one_of(
                st.text(min_size=1, max_size=10).filter(lambda s: s.strip() != ""),
                st.just(""),
                st.just("NaN"),
            )
        )
        child_name = draw(
            st.one_of(
                st.none(),
                st.text(min_size=0, max_size=20),
                st.booleans(),
            )
        )
        child_status = draw(
            st.one_of(
                st.sampled_from(["active", "inactive", "unknown"]),
                st.text(min_size=1, max_size=10).filter(lambda s: s not in {"active", "inactive", "unknown"}),
                st.none(),
            )
        )
        child_tags = draw(
            st.lists(
                st.one_of(
                    st.text(min_size=0, max_size=10),
                    st.none(),
                    st.integers(min_value=0, max_value=100),
                ),
                min_size=0,
                max_size=3,
            )
        )
        return {
            "id": child_id,
            "amount": child_amount,
            "name": child_name,
            "status": child_status,
            "tags": child_tags,
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