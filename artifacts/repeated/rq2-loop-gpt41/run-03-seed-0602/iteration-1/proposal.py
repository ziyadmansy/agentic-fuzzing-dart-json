from hypothesis import strategies as st

# Helper strategies for field values
id_strategy = st.integers(min_value=-2**31, max_value=2**31-1)

# For amount, try valid and edge-case strings (e.g. numeric, empty, weird unicode, etc.)
amount_strategy = st.one_of(
    st.text(min_size=1, max_size=20),  # normal string
    st.text(min_size=0, max_size=0),  # empty string
    st.text(alphabet="\u0000-\uFFFF", min_size=1, max_size=10),  # unicode
    st.integers().map(str),  # stringified integer
    st.floats(allow_nan=False, allow_infinity=False).map(str),  # stringified float
)

# For name, try string, null, and some edge cases (empty, numeric, boolean, etc.)
name_strategy = st.one_of(
    st.text(min_size=0, max_size=20),
    st.none(),
    st.integers().map(str),
    st.booleans().map(lambda b: "true" if b else "false"),
)

# For status, use valid and some invalid/edge-case values
status_strategy = st.one_of(
    st.sampled_from(["active", "inactive", "unknown"]),
    st.text(min_size=0, max_size=10).filter(lambda s: s not in {"active", "inactive", "unknown"}),
    st.integers().map(str),
    st.none().map(lambda _: "null"),
)

# For tags, try normal arrays, empty, arrays with non-string, etc.
tags_strategy = st.one_of(
    st.lists(st.text(min_size=0, max_size=10), min_size=0, max_size=5),
    st.lists(st.integers(), min_size=1, max_size=3),  # non-string elements
    st.lists(st.none(), min_size=1, max_size=2),      # nulls in array
    st.just([]),
)

# Recursion for child field, with bounded depth
def record_strategy(max_depth):
    @st.composite
    def _record(draw):
        # At depth 0, child is always null
        if max_depth <= 0:
            child_val = "null"
        else:
            # Either null or another record
            child_val = draw(
                st.one_of(
                    st.just("null"),
                    record_strategy(max_depth - 1)
                )
            )
        # Compose fields
        id_val = draw(id_strategy)
        amount_val = draw(amount_strategy)
        name_val = draw(name_strategy)
        status_val = draw(status_strategy)
        tags_val = draw(tags_strategy)
        # JSON-encode fields manually
        def json_str(s):
            # Escape backslash and double quote, minimal for test
            return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'
        id_json = str(id_val)
        amount_json = json_str(amount_val) if isinstance(amount_val, str) else str(amount_val)
        if name_val is None:
            name_json = "null"
        elif isinstance(name_val, str):
            name_json = json_str(name_val)
        else:
            name_json = str(name_val)
        status_json = json_str(status_val) if isinstance(status_val, str) else str(status_val)
        # tags: array of strings or other types
        def tag_json(v):
            if v is None:
                return "null"
            elif isinstance(v, str):
                return json_str(v)
            else:
                return str(v)
        tags_json = "[" + ",".join(tag_json(t) for t in tags_val) + "]"
        # Compose record
        record_json = (
            "{"
            f"\"id\":{id_json},"
            f"\"amount\":{amount_json},"
            f"\"name\":{name_json},"
            f"\"status\":{status_json},"
            f"\"tags\":{tags_json},"
            f"\"child\":{child_val}"
            "}"
        )
        return record_json
    return _record()

# Top-level strategy: generate one record, encode as bytes
@st.composite
def generated_json(draw):
    # Limit recursion depth to 1 or 2 for child
    record_json = draw(record_strategy(max_depth=1))
    # Return as bytes
    return record_json.encode("utf-8")