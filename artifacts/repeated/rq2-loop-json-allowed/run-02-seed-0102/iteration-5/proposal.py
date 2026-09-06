from hypothesis import strategies as st
import json

# Allowed status values
_status_values = st.sampled_from(["active", "inactive", "unknown"])

@st.composite
def generated_json(draw) -> bytes:
    """
    Generate a JSON object as bytes, representing a Record with fields:
    {
      "id": <integer>,
      "amount": <string>,
      "name": <string or null>,
      "status": <one of "active", "inactive", "unknown">,
      "tags": <array of strings>,
      "child": <Record or null, one level recursion>
    }

    Introduce subtle divergences by:
    - Sometimes making a field null vs missing (but here always present, so null vs correct type)
    - Sometimes using a string that looks like a number for "amount"
    - Sometimes using boundary integers for "id"
    - Sometimes using empty string or null for "name"
    - Sometimes using empty list or list with empty strings for "tags"
    - Sometimes making "child" null or a nested record (one level only)
    - Sometimes using a wrong type for a single field (e.g. number instead of string for amount)
    """

    # id: integer, but sometimes boundary values or negative (though spec doesn't forbid negative)
    id_val = draw(
        st.one_of(
            st.integers(min_value=0, max_value=2**31 - 1),
            st.just(-1),  # negative id to test divergence
            st.just(2**31),  # just above 32-bit int max
        )
    )

    # amount: string normally, but sometimes numeric string, sometimes numeric type (wrong type)
    amount_str = draw(
        st.one_of(
            st.text(min_size=1, max_size=10),
            st.integers(min_value=0, max_value=100000).map(str),
            st.floats(min_value=0, max_value=100000).map(lambda f: f"{f:.2f}"),
            st.integers(min_value=0, max_value=100000),  # wrong type: int instead of string
            st.floats(min_value=0, max_value=100000),  # wrong type: float instead of string
        )
    )

    # name: string or null, sometimes empty string, sometimes null
    name_val = draw(
        st.one_of(
            st.none(),
            st.text(min_size=0, max_size=20),
        )
    )

    # status: one of the three strings, but sometimes wrong string or null (wrong type)
    status_val = draw(
        st.one_of(
            _status_values,
            st.text(min_size=1, max_size=10).filter(lambda s: s not in ["active", "inactive", "unknown"]),
            st.none(),
        )
    )

    # tags: array of strings, sometimes empty, sometimes with empty strings, sometimes null (wrong type)
    tags_val = draw(
        st.one_of(
            st.lists(st.text(min_size=0, max_size=10), max_size=5),
            st.lists(st.just(""), max_size=3),
            st.none(),
        )
    )

    # child: null or nested record (one level only)
    # To avoid infinite recursion, child record fields are simpler (no child inside child)
    def child_record():
        child_id = draw(st.integers(min_value=0, max_value=1000))
        child_amount = draw(st.text(min_size=1, max_size=10))
        child_name = draw(st.one_of(st.none(), st.text(min_size=0, max_size=10)))
        child_status = draw(_status_values)
        child_tags = draw(st.lists(st.text(min_size=0, max_size=5), max_size=3))
        # child.child is always null to limit recursion
        return {
            "id": child_id,
            "amount": child_amount,
            "name": child_name,
            "status": child_status,
            "tags": child_tags,
            "child": None,
        }

    child_val = draw(
        st.one_of(
            st.none(),
            st.builds(child_record),
        )
    )

    # Build the record dict
    record = {
        "id": id_val,
        "amount": amount_str,
        "name": name_val,
        "status": status_val,
        "tags": tags_val,
        "child": child_val,
    }

    # Serialize to JSON bytes
    json_bytes = json.dumps(record).encode("utf-8")
    return json_bytes