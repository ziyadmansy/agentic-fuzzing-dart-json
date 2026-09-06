from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status enum
    statuses = ["active", "inactive", "unknown"]

    # Helper to produce a JSON string literal with proper escaping of quotes and backslashes
    def json_string_literal(s: str) -> str:
        # Escape backslash and double quotes minimally for JSON string
        s = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{s}"'

    # Recursive generator for the "child" field, bounded to depth 1 (one level of recursion)
    # We produce either null or a nested record with no further child (child=null)
    def record(depth: int) -> st.SearchStrategy[str]:
        # id: integer (we allow some boundary values and some invalid types as strings to provoke divergence)
        # amount: string (sometimes a numeric string, sometimes a string with spaces or unusual chars)
        # name: string or null (sometimes null, sometimes string, sometimes empty string)
        # status: one of the three strings, sometimes invalid string to provoke divergence
        # tags: array of strings (sometimes empty, sometimes with unusual strings)
        # child: null or nested record (only one level deep)

        # id field: mostly integer, but sometimes stringified integer or float string to provoke divergence
        id_val = draw(
            st.one_of(
                st.integers(min_value=0, max_value=2**31 - 1).map(str),
                st.text(min_size=1, max_size=5).filter(lambda x: not x.isdigit()),  # invalid id string
                st.floats(allow_nan=False, allow_infinity=False).map(lambda f: repr(f)),
            )
        )

        # amount field: string, sometimes numeric string, sometimes with spaces or currency symbols
        amount_val = draw(
            st.one_of(
                st.floats(allow_nan=False, allow_infinity=False).map(lambda f: f"{f:.2f}"),
                st.text(min_size=1, max_size=10).filter(lambda s: any(c.isalpha() for c in s)),
                st.just(""),  # empty string edge case
            )
        )

        # name field: string or null, sometimes empty string, sometimes null
        name_val = draw(
            st.one_of(
                st.none(),
                st.text(min_size=0, max_size=10),
                st.just(""),  # empty string edge case
            )
        )

        # status field: mostly valid enum, sometimes invalid string to provoke divergence
        status_val = draw(
            st.one_of(
                st.sampled_from(statuses),
                st.text(min_size=1, max_size=7).filter(lambda s: s not in statuses),
            )
        )

        # tags field: array of strings, sometimes empty, sometimes with empty string, sometimes with null (invalid)
        tags_val = draw(
            st.lists(
                st.one_of(
                    st.text(min_size=0, max_size=5),
                    st.just(""),  # empty string tag
                    st.none(),  # invalid null tag to provoke divergence
                ),
                min_size=0,
                max_size=3,
            )
        )

        # child field: null or nested record (only one level deep)
        if depth == 0:
            child_val = draw(st.none())
        else:
            child_val = draw(st.one_of(st.none(), record(depth - 1)))

        # Build JSON string for this record
        # Compose each field as JSON text

        # id field: sometimes invalid string, so output as string literal or number literal accordingly
        # We try to detect if id_val is a valid integer string or float string or invalid string
        # If id_val is digits only, output as number literal (no quotes)
        # else output as string literal (with quotes)
        def is_int_string(s):
            return s.isdigit()

        def is_float_string(s):
            try:
                float(s)
                return True
            except Exception:
                return False

        if is_int_string(id_val):
            id_json = id_val
        elif is_float_string(id_val):
            id_json = id_val
        else:
            id_json = json_string_literal(id_val)

        # amount is always string, so always quoted
        amount_json = json_string_literal(amount_val)

        # name is string or null
        if name_val is None:
            name_json = "null"
        else:
            name_json = json_string_literal(name_val)

        # status is string, always quoted
        status_json = json_string_literal(status_val)

        # tags is array of strings, but may contain null (invalid)
        # Output JSON array with elements quoted if string, or null literal if None
        tags_json_elems = []
        for t in tags_val:
            if t is None:
                tags_json_elems.append("null")
            else:
                tags_json_elems.append(json_string_literal(t))
        tags_json = "[" + ",".join(tags_json_elems) + "]"

        # child is null or nested record JSON string
        if child_val is None:
            child_json = "null"
        else:
            child_json = child_val

        # Compose full JSON object string
        json_obj = (
            "{"
            + '"id":' + id_json + ","
            + '"amount":' + amount_json + ","
            + '"name":' + name_json + ","
            + '"status":' + status_json + ","
            + '"tags":' + tags_json + ","
            + '"child":' + child_json
            + "}"
        )
        return json_obj

    # Generate top-level record with depth 1 recursion allowed
    json_text = draw(record(depth=1))

    # Return bytes encoded UTF-8
    return json_text.encode("utf-8")