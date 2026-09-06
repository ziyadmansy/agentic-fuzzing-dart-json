from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic components
    id_int = draw(
        st.one_of(
            st.integers(min_value=-(2**64), max_value=2**64),  # boundary_id emphasis
            st.integers(min_value=0, max_value=1000),
        )
    )
    # amount: string, but try normal decimal strings and some unusual numeric strings
    amount_str = draw(
        st.one_of(
            st.text(min_size=1, max_size=10).filter(lambda s: all(c in "0123456789.-" for c in s)),
            st.just("0"),
            st.just("1.0"),
            st.just("-0"),
            st.just("000123"),
        )
    )
    # name: string or null, with null_override emphasis
    name_val = draw(st.one_of(st.none(), st.text(min_size=0, max_size=20)))

    # status: enum with bad_enum emphasis
    status_val = draw(
        st.one_of(
            st.sampled_from(["active", "inactive", "unknown"]),
            st.text(min_size=1, max_size=10).filter(lambda s: s not in {"active", "inactive", "unknown"}),
        )
    )

    # tags: array of strings, including empty array and some with empty strings
    tags_list = draw(
        st.lists(
            st.one_of(st.text(min_size=0, max_size=10), st.just("")),
            min_size=0,
            max_size=5,
        )
    )

    # child: null or one-level recursion (no deeper than 1 level)
    # To keep bounded recursion, child can be null or a record with child=null
    # We vary null_override and some fields inside child as well
    def record_strategy():
        # id near boundaries or normal
        id_inner = draw(
            st.one_of(
                st.integers(min_value=-(2**64), max_value=2**64),
                st.integers(min_value=0, max_value=1000),
            )
        )
        amount_inner = draw(
            st.one_of(
                st.text(min_size=1, max_size=10).filter(lambda s: all(c in "0123456789.-" for c in s)),
                st.just("0"),
                st.just("1.0"),
                st.just("-0"),
                st.just("000123"),
            )
        )
        name_inner = draw(st.one_of(st.none(), st.text(min_size=0, max_size=20)))
        status_inner = draw(
            st.one_of(
                st.sampled_from(["active", "inactive", "unknown"]),
                st.text(min_size=1, max_size=10).filter(lambda s: s not in {"active", "inactive", "unknown"}),
            )
        )
        tags_inner = draw(
            st.lists(
                st.one_of(st.text(min_size=0, max_size=10), st.just("")),
                min_size=0,
                max_size=5,
            )
        )
        # child is always null here to avoid deep nesting
        return {
            "id": id_inner,
            "amount": amount_inner,
            "name": name_inner,
            "status": status_inner,
            "tags": tags_inner,
            "child": None,
        }

    child_val = draw(st.one_of(st.none(), st.just(record_strategy())))

    # Compose JSON string manually
    # Helper to JSON-encode strings (minimal escaping for quotes and backslash)
    def json_str(s):
        if s is None:
            return "null"
        # escape backslash and double quote
        esc = s.replace("\\", "\\\\").replace('"', '\\"')
        # also escape control chars (minimal)
        esc = "".join(
            c if c >= " " else "\\u%04x" % ord(c)
            for c in esc
        )
        return f'"{esc}"'

    def json_array(arr):
        return "[" + ",".join(json_str(x) for x in arr) + "]"

    def json_record(rec):
        # rec is dict with all fields present, child is None or dict
        parts = []
        parts.append(f'"id":{rec["id"]}')
        parts.append(f'"amount":{json_str(rec["amount"])}')
        parts.append(f'"name":{json_str(rec["name"])}')
        parts.append(f'"status":{json_str(rec["status"])}')
        parts.append(f'"tags":{json_array(rec["tags"])}')
        if rec["child"] is None:
            parts.append(f'"child":null')
        else:
            parts.append(f'"child":{json_record(rec["child"])}')
        return "{" + ",".join(parts) + "}"

    top_record = {
        "id": id_int,
        "amount": amount_str,
        "name": name_val,
        "status": status_val,
        "tags": tags_list,
        "child": child_val,
    }

    json_text = json_record(top_record)
    return json_text.encode("utf-8")