from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status enum
    statuses = ["active", "inactive", "unknown"]

    # Helper: generate a JSON string literal (with quotes and escaped chars)
    def json_string(s: str) -> str:
        # Escape backslash and quotes minimally for JSON string
        s = s.replace("\\", "\\\\").replace('"', '\\"')
        # Also escape control chars minimally (e.g. \n, \r, \t)
        s = s.replace("\b", "\\b").replace("\f", "\\f").replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
        return f'"{s}"'

    # Helper: generate JSON array of strings
    def json_string_array():
        # Array length 0..3 for bounded size
        arr_len = draw(st.integers(min_value=0, max_value=3))
        # Elements: strings, possibly empty, possibly with escapes
        elements = [draw(st.text(min_size=0, max_size=10)) for _ in range(arr_len)]
        # Map to JSON strings
        elements_json = [json_string(e) for e in elements]
        return "[" + ",".join(elements_json) + "]"

    # Helper: generate a field with a chance to be:
    # - correct type and present
    # - present but wrong type (one wrong type per field)
    # - missing (omit field)
    # This helps create "almost well-formed" documents.
    # We will apply this per field except "id" which we always include as integer (to keep mostly valid)
    # and "status" which we always include but sometimes wrong type or wrong enum string.
    # For "child" we recurse with bounded depth.

    # We'll define a sub-strategy for a record at given depth
    def record_strategy(depth: int):
        # To avoid infinite recursion, max depth = 1 (child can be null or record at depth 1)
        # At depth 2, child is always null.

        # id: integer, always present, but sometimes as string or float to cause divergence
        id_field = draw(
            st.one_of(
                st.integers(min_value=0, max_value=1000).map(str),  # correct integer as string (will be parsed as string)
                st.integers(min_value=0, max_value=1000).map(str),  # correct integer as string (duplicate to weight)
                st.integers(min_value=0, max_value=1000),  # correct integer as number
                st.floats(allow_nan=False, allow_infinity=False).map(lambda f: f if f.is_integer() else int(f)),  # float that is int
                st.text(min_size=1, max_size=5),  # wrong type string
            )
        )
        # We want to emit JSON text, so if id_field is int or float, emit as number, else as string literal
        def id_json(val):
            if isinstance(val, int):
                return str(val)
            elif isinstance(val, float):
                # floats that are integers, emit as int string
                if val.is_integer():
                    return str(int(val))
                else:
                    return str(val)
            else:
                # string
                return json_string(val)

        id_json_val = id_json(id_field)

        # amount: string, sometimes null, sometimes number, sometimes missing
        amount_field = draw(
            st.one_of(
                st.text(min_size=0, max_size=10).map(json_string),
                st.just("null"),
                st.integers(min_value=0, max_value=1000).map(str),
                st.none().map(lambda _: "null"),
            )
        )

        # name: string or null or missing or wrong type (number)
        name_field = draw(
            st.one_of(
                st.text(min_size=0, max_size=10).map(json_string),
                st.just("null"),
                st.integers(min_value=0, max_value=1000).map(str),
                st.none().map(lambda _: "null"),
            )
        )

        # status: one of enum strings, or wrong string, or number, or missing
        status_field = draw(
            st.one_of(
                st.sampled_from(statuses).map(json_string),
                st.text(min_size=1, max_size=10).filter(lambda s: s not in statuses).map(json_string),
                st.integers(min_value=0, max_value=10).map(str),
                st.just("null"),
            )
        )

        # tags: array of strings, or null, or string, or missing
        tags_field = draw(
            st.one_of(
                json_string_array(),
                st.just("null"),
                st.text(min_size=0, max_size=10).map(json_string),
            )
        )

        # child: null or record or wrong type (string, number)
        if depth >= 2:
            # no recursion beyond depth 2
            child_field = "null"
        else:
            child_choice = draw(
                st.one_of(
                    st.just("null"),
                    record_strategy(depth + 1),
                    st.text(min_size=0, max_size=10).map(json_string),
                    st.integers(min_value=0, max_value=1000).map(str),
                )
            )
            child_field = child_choice

        # Compose fields, sometimes omit fields (except id and status always present)
        # We'll omit fields with low probability to create divergence on missing vs present
        def maybe_field(name, val, always_present=False):
            if always_present:
                return f'"{name}":{val}'
            else:
                include = draw(st.booleans())
                if include:
                    return f'"{name}":{val}'
                else:
                    return None

        fields = [
            f'"id":{id_json_val}',  # always present
            maybe_field("amount", amount_field),
            maybe_field("name", name_field),
            f'"status":{status_field}',  # always present
            maybe_field("tags", tags_field),
            maybe_field("child", child_field),
        ]

        # Filter out omitted fields
        fields = [f for f in fields if f is not None]

        # Shuffle fields to avoid positional bias
        fields = draw(st.permutations(fields))

        return "{" + ",".join(fields) + "}"

    # Generate top-level record at depth 0
    json_text = record_strategy(0)

    return json_text.encode("utf-8")