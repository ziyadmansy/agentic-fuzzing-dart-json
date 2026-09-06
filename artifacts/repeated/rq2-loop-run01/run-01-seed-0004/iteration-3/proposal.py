from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status field
    statuses = ["active", "inactive", "unknown"]

    # Helper to produce a JSON string literal with proper escaping of quotes and backslashes
    def json_string(s: str) -> str:
        # Minimal escaping for JSON string: backslash and quote
        # Hypothesis strings won't contain control chars by default, so minimal escaping is enough
        s = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{s}"'

    # Recursive generator for the "child" field, bounded to depth 1 (one level of recursion)
    def record(depth: int) -> st.SearchStrategy[str]:
        # id: integer
        # amount: string
        # name: string or null
        # status: one of "active", "inactive", "unknown"
        # tags: array of strings
        # child: record or null (only one level deep)
        # We will produce a JSON object string

        # id: mostly integer, but sometimes a stringified integer or a float to cause divergence
        # amount: string, sometimes a numeric string, sometimes a string with spaces or weird chars
        # name: string or null, sometimes empty string, sometimes a number as string, sometimes null
        # status: mostly valid enum string, sometimes invalid string or null to cause divergence
        # tags: array of strings, sometimes empty, sometimes with null or numbers as strings to cause divergence
        # child: either null or a nested record (only if depth == 0)

        # id field: mostly integer, but sometimes stringified integer or float string to cause divergence
        id_val = draw(
            st.one_of(
                st.integers(min_value=0, max_value=100000).map(str),
                st.integers(min_value=0, max_value=100000),
                st.floats(min_value=0, max_value=100000, allow_nan=False, allow_infinity=False).map(lambda f: f"{f:.1f}"),
            )
        )
        # id_val is either int, or string of int, or string float

        # amount: string, sometimes numeric string, sometimes with spaces or weird chars
        amount_val = draw(
            st.one_of(
                st.text(min_size=1, max_size=10).filter(lambda s: '"' not in s and '\\' not in s),
                st.integers(min_value=0, max_value=100000).map(str),
                st.floats(min_value=0, max_value=100000, allow_nan=False, allow_infinity=False).map(lambda f: f"{f:.2f}"),
            )
        )

        # name: string or null, sometimes empty string, sometimes numeric string, sometimes null
        name_val = draw(
            st.one_of(
                st.none(),
                st.text(min_size=0, max_size=10).filter(lambda s: '"' not in s and '\\' not in s),
                st.integers(min_value=0, max_value=100000).map(str),
            )
        )

        # status: mostly valid enum string, sometimes invalid string or null
        status_val = draw(
            st.one_of(
                st.sampled_from(statuses),
                st.text(min_size=1, max_size=10).filter(lambda s: s not in statuses and '"' not in s and '\\' not in s),
                st.none(),
            )
        )

        # tags: array of strings, sometimes empty, sometimes with null or numbers as strings to cause divergence
        # We'll produce a list of 0-3 elements, each element either string, null, or numeric string
        tag_elem = st.one_of(
            st.text(min_size=1, max_size=8).filter(lambda s: '"' not in s and '\\' not in s),
            st.none(),
            st.integers(min_value=0, max_value=1000).map(str),
        )
        tags_val = draw(st.lists(tag_elem, min_size=0, max_size=3))

        # child: either null or nested record (only if depth == 0)
        if depth == 0:
            child_val = draw(st.one_of(st.just(None), record(depth=1)))
        else:
            child_val = None

        # Now build JSON string for this record

        # id field: if id_val is int, output as number, if string, output as JSON string
        if isinstance(id_val, int):
            id_str = str(id_val)
        else:
            id_str = json_string(str(id_val))

        # amount is always string, so always JSON string
        amount_str = json_string(str(amount_val))

        # name: null or string
        if name_val is None:
            name_str = "null"
        else:
            name_str = json_string(str(name_val))

        # status: null or string
        if status_val is None:
            status_str = "null"
        else:
            status_str = json_string(str(status_val))

        # tags: array of strings or nulls or numeric strings, all as JSON strings or nulls
        tag_strs = []
        for t in tags_val:
            if t is None:
                tag_strs.append("null")
            else:
                tag_strs.append(json_string(str(t)))
        tags_str = "[" + ",".join(tag_strs) + "]"

        # child: null or nested record string
        if child_val is None:
            child_str = "null"
        else:
            child_str = child_val

        # Compose JSON object string
        json_obj = (
            "{"
            f'"id":{id_str},'
            f'"amount":{amount_str},'
            f'"name":{name_str},'
            f'"status":{status_str},'
            f'"tags":{tags_str},'
            f'"child":{child_str}'
            "}"
        )

        return json_obj

    # Draw top-level record string
    top_record = draw(record(depth=0))

    # Return as bytes
    return top_record.encode("utf-8")