from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Helper strategies for fields

    # id: integer, but sometimes as string or float to provoke divergence
    id_val = draw(
        st.one_of(
            st.integers(min_value=0, max_value=2**31 - 1),
            st.text(min_size=1, max_size=10).filter(lambda s: s.isdigit()),  # numeric string
            st.floats(allow_infinity=False, allow_nan=False, width=32).map(lambda f: f if f >= 0 else abs(f)),
        )
    )

    # amount: string normally, but sometimes number or null to provoke divergence
    amount_val = draw(
        st.one_of(
            st.text(min_size=1, max_size=10),
            st.integers(min_value=0, max_value=1000000).map(str),
            st.floats(allow_infinity=False, allow_nan=False).map(lambda f: str(f)),
            st.none(),
            st.integers(min_value=0, max_value=1000000),
        )
    )

    # name: string or null, sometimes number or boolean to provoke divergence
    name_val = draw(
        st.one_of(
            st.none(),
            st.text(min_size=0, max_size=20),
            st.integers(min_value=-1000, max_value=1000),
            st.booleans(),
        )
    )

    # status: one of "active", "inactive", "unknown" normally,
    # sometimes a wrong string, or null, or number to provoke divergence
    status_val = draw(
        st.one_of(
            st.sampled_from(["active", "inactive", "unknown"]),
            st.text(min_size=1, max_size=10).filter(lambda s: s not in {"active", "inactive", "unknown"}),
            st.none(),
            st.integers(min_value=0, max_value=10),
        )
    )

    # tags: array of strings normally, sometimes array of numbers, or null, or empty string
    tags_val = draw(
        st.one_of(
            st.lists(st.text(min_size=0, max_size=10), max_size=5),
            st.lists(st.integers(min_value=0, max_value=100), max_size=5),
            st.none(),
            st.text(min_size=0, max_size=5),
        )
    )

    # child: either null or a nested record (one level only)
    # To avoid infinite recursion, child record fields are simpler and less variant
    def child_record():
        child_id = draw(st.integers(min_value=0, max_value=1000))
        child_amount = draw(st.text(min_size=1, max_size=10))
        child_name = draw(st.one_of(st.none(), st.text(min_size=0, max_size=10)))
        child_status = draw(st.sampled_from(["active", "inactive", "unknown"]))
        child_tags = draw(st.lists(st.text(min_size=0, max_size=5), max_size=3))
        # child.child is always null to limit recursion depth
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

    # Now build JSON text manually, carefully encoding values as JSON text

    def json_encode_str(s):
        # Minimal JSON string escaping for quotes and backslash
        # Hypothesis strings are unicode, but we keep it simple here
        s = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{s}"'

    def json_encode_value(v):
        if v is None:
            return "null"
        elif isinstance(v, bool):
            return "true" if v else "false"
        elif isinstance(v, int):
            return str(v)
        elif isinstance(v, float):
            # JSON floats must not be NaN or Infinity, ensured by strategy
            # Use repr to get a JSON-compatible float string
            return repr(v)
        elif isinstance(v, str):
            return json_encode_str(v)
        elif isinstance(v, list):
            return "[" + ",".join(json_encode_value(x) for x in v) + "]"
        elif isinstance(v, dict):
            items = []
            for key, val in v.items():
                items.append(json_encode_str(key) + ":" + json_encode_value(val))
            return "{" + ",".join(items) + "}"
        else:
            # fallback to string
            return json_encode_str(str(v))

    # Compose top-level dict
    top_level = {
        "id": id_val,
        "amount": amount_val,
        "name": name_val,
        "status": status_val,
        "tags": tags_val,
        "child": child_val,
    }

    json_text = json_encode_value(top_level)
    return json_text.encode("utf-8")