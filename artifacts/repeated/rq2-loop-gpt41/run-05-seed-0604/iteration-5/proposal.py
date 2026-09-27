from hypothesis import strategies as st

# Helper strategies for fields with subtle edge cases
id_strategy = st.integers(-2**31, 2**31 - 1) | st.floats(allow_nan=False, allow_infinity=False).filter(lambda x: x.is_integer()).map(int)
amount_strategy = (
    st.text(min_size=0, max_size=32)
    | st.integers(-2**63, 2**63-1).map(str)
    | st.floats(allow_nan=False, allow_infinity=False).map(lambda f: format(f, ".16g"))
)
name_strategy = (
    st.none()
    | st.text(min_size=0, max_size=32)
    | st.integers(-2**31, 2**31-1).map(str)
    | st.booleans().map(lambda b: "true" if b else "false")
)
status_strategy = (
    st.sampled_from(["active", "inactive", "unknown"])
    | st.text(min_size=0, max_size=16).filter(lambda s: s not in {"active", "inactive", "unknown"})
    | st.integers(-1, 1).map(str)
)
tags_strategy = (
    st.lists(
        st.text(min_size=0, max_size=16)
        | st.integers(-2**31, 2**31-1).map(str)
        | st.none().map(lambda _: "null"),
        min_size=0, max_size=4
    )
    | st.text(min_size=2, max_size=32).map(lambda s: [s])
    | st.none().map(lambda _: [])
)
# For recursion, we need to bound the depth
def _record_strategy(depth):
    if depth <= 0:
        child_strategy = st.just("null")
    else:
        child_strategy = (
            st.none().map(lambda _: "null")
            | st.deferred(lambda: _record_strategy(depth-1))
        )
    # Sometimes omit a field, or swap types, or reorder fields
    base_fields = [
        ("id", id_strategy),
        ("amount", amount_strategy),
        ("name", name_strategy),
        ("status", status_strategy),
        ("tags", tags_strategy),
        ("child", child_strategy),
    ]
    # Sometimes drop a field (simulate missing field)
    maybe_drop = st.booleans()
    def build_fields(draw):
        fields = []
        for k, strat in base_fields:
            # With low probability, drop a field (except id, which is always present)
            if k != "id" and draw(st.integers(0, 9)) == 0:
                continue
            v = draw(strat)
            # For null, don't quote; for others, quote if string
            if v == "null":
                json_v = "null"
            elif isinstance(v, str):
                # Escape quotes and backslashes
                json_v = '"' + v.replace('\\', '\\\\').replace('"', '\\"') + '"'
            elif isinstance(v, list):
                json_v = "[" + ",".join(
                    "null" if x == "null" else '"' + x.replace('\\', '\\\\').replace('"', '\\"') + '"' for x in v
                ) + "]"
            else:
                json_v = str(v)
            fields.append(f'"{k}":{json_v}')
        # With low probability, duplicate a field
        if draw(st.integers(0, 19)) == 0:
            fields.append(fields[-1])
        # With low probability, reorder fields
        if draw(st.integers(0, 9)) == 0:
            draw(st.permutations(fields))
        return "{" + ",".join(fields) + "}"
    return st.builds(lambda x: x, st.deferred(build_fields))

@st.composite
def generated_json(draw) -> bytes:
    # Limit recursion depth and document size
    doc = draw(_record_strategy(depth=1 + draw(st.integers(0, 1))))
    # Ensure output is bytes
    return doc.encode("utf-8")