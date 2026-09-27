from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status field
    status_values = ["active", "inactive", "unknown"]

    # Helper: JSON string escaping for simple strings (no control chars)
    def json_string(s: str) -> str:
        # Escape backslash and double quote only for simplicity
        return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

    # Helper: produce JSON text for a list of strings
    def json_string_list(lst):
        return "[" + ",".join(json_string(e) for e in lst) + "]"

    # Helper: produce JSON text for a record (dict) with given fields
    # We produce a JSON object string with fields in fixed order for determinism
    def json_record_text(rec):
        # rec is dict with keys: id, amount, name, status, tags, child
        parts = []
        # id: integer or double (see below)
        parts.append('"id":' + rec["id"])
        # amount: string
        parts.append('"amount":' + json_string(rec["amount"]))
        # name: string or null
        if rec["name"] is None:
            parts.append('"name":null')
        else:
            parts.append('"name":' + json_string(rec["name"]))
        # status: string (one of known values or possibly invalid for testing)
        parts.append('"status":' + json_string(rec["status"]))
        # tags: array of strings or possibly missing (None means missing)
        if rec.get("tags") is not None:
            parts.append('"tags":' + json_string_list(rec["tags"]))
        # child: null or nested record JSON text
        if rec["child"] is None:
            parts.append('"child":null')
        else:
            parts.append('"child":' + rec["child"])
        return "{" + ",".join(parts) + "}"

    # Strategy for id field:
    # To maximize divergence, produce either:
    # - a JSON integer literal (e.g. "123")
    # - a JSON number literal with decimal point (e.g. "123.0") to be parsed as double
    # - a large integer outside 64-bit range as double (e.g. 2**63 as double)
    # We produce the JSON text for the number directly as string.
    def id_strategy():
        # 64-bit int range
        int64_min = -(2**63)
        int64_max = 2**63 - 1

        # Choose one of three variants:
        variant = draw(st.integers(min_value=0, max_value=2))
        if variant == 0:
            # Normal int in 64-bit range, output as integer literal
            v = draw(st.integers(min_value=int64_min, max_value=int64_max))
            return str(v)
        elif variant == 1:
            # Normal int in 64-bit range, output as double literal with .0
            v = draw(st.integers(min_value=int64_min, max_value=int64_max))
            return str(v) + ".0"
        else:
            # Large integer outside 64-bit range, output as double literal
            # Pick a large integer > int64_max or < int64_min
            large_pos = draw(st.integers(min_value=int64_max + 1, max_value=int64_max + 10**6))
            large_neg = draw(st.integers(min_value=int64_min - 10**6, max_value=int64_min - 1))
            v = draw(st.sampled_from([large_pos, large_neg]))
            # Output as double literal with .0
            return str(v) + ".0"

    # amount: always a string, nonempty ascii printable without control chars
    amount_str = st.text(min_size=1, max_size=20, alphabet=st.characters(min_codepoint=32, max_codepoint=126).filter(lambda c: c not in '"\\'))

    # name: nullable string or null
    name_str = st.one_of(st.none(), st.text(min_size=0, max_size=20, alphabet=st.characters(min_codepoint=32, max_codepoint=126).filter(lambda c: c not in '"\\')))

    # status: mostly valid values, but sometimes invalid string to test rejection
    status_str = st.one_of(
        st.sampled_from(status_values),
        st.text(min_size=1, max_size=10).filter(lambda s: s not in status_values)
    )

    # tags: array of strings or missing (None)
    # To maximize divergence, sometimes omit tags (None), sometimes empty list, sometimes nonempty list
    tags_strategy = st.one_of(
        st.none(),  # missing tags field (built_value accepts, others reject)
        st.lists(st.text(min_size=1, max_size=10, alphabet=st.characters(min_codepoint=32, max_codepoint=126).filter(lambda c: c not in '"\\')), max_size=5)
    )

    # child: nullable record or null
    # To avoid deep recursion, limit depth to 1 level only
    # We'll produce child as JSON text recursively with depth=1 only
    # To avoid infinite recursion, child can be null or a record with child=null
    @st.composite
    def child_strategy(draw):
        # 50% null child
        if draw(st.booleans()):
            return None
        # else produce a record with child=null (no deeper recursion)
        child_rec = {
            "id": draw(id_strategy()),
            "amount": draw(amount_str),
            "name": draw(name_str),
            "status": draw(status_str),
            "tags": draw(tags_strategy),
            "child": None,
        }
        return json_record_text(child_rec)

    # Compose the full record
    id_val = draw(id_strategy())
    amount_val = draw(amount_str)
    name_val = draw(name_str)
    status_val = draw(status_str)
    tags_val = draw(tags_strategy)
    child_val = draw(child_strategy())

    record = {
        "id": id_val,
        "amount": amount_val,
        "name": name_val,
        "status": status_val,
        "tags": tags_val,
        "child": child_val,
    }

    json_text = json_record_text(record)
    return json_text.encode("utf-8")