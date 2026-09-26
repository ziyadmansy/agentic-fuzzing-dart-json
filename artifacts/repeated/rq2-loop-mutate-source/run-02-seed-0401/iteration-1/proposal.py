from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status enum
    statuses = ["active", "inactive", "unknown"]

    # Helper to produce a JSON string literal with proper escaping of quotes and backslashes
    def json_string(s: str) -> str:
        # Minimal escaping for " and \ to keep JSON valid
        return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

    # Recursive record generator with depth limit 1 (child can be null or a record with child=null)
    def record(depth: int) -> st.SearchStrategy[str]:
        # id: integer, but we will sometimes produce a stringified integer or a float to cause divergence
        # amount: string, but sometimes a number or null to cause divergence
        # name: string or null, but sometimes a number or boolean to cause divergence
        # status: one of the three strings, but sometimes a wrong string or null to cause divergence
        # tags: array of strings, but sometimes empty array, or array with non-string elements to cause divergence
        # child: null or record (depth limit 1)

        # id field: mostly integer, sometimes stringified integer, sometimes float, sometimes string non-numeric
        id_val = draw(st.one_of(
            st.integers(min_value=0, max_value=1000).map(str),
            st.integers(min_value=0, max_value=1000),
            st.floats(allow_nan=False, allow_infinity=False).map(lambda f: str(f)),
            st.text(min_size=1, max_size=5).filter(lambda s: not s.isdigit())
        ))
        # id_val is string or int or float string or non-digit string

        # amount field: mostly string, sometimes number, sometimes null
        amount_val = draw(st.one_of(
            st.text(min_size=1, max_size=10).map(json_string),
            st.integers(min_value=0, max_value=100000).map(str),
            st.floats(allow_nan=False, allow_infinity=False).map(lambda f: str(f)),
            st.just("null")
        ))

        # name field: string or null, sometimes number or boolean or empty string
        name_val = draw(st.one_of(
            st.none().map(lambda _: "null"),
            st.text(min_size=0, max_size=10).map(json_string),
            st.integers(min_value=0, max_value=1000).map(str),
            st.booleans().map(lambda b: "true" if b else "false"),
        ))

        # status field: mostly one of the three strings, sometimes null, sometimes wrong string
        status_val = draw(st.one_of(
            st.sampled_from(statuses).map(json_string),
            st.none().map(lambda _: "null"),
            st.text(min_size=1, max_size=10).filter(lambda s: s not in statuses).map(json_string),
        ))

        # tags field: array of strings, sometimes empty, sometimes with non-string elements
        # We'll produce JSON array text directly
        def tag_element():
            return draw(st.one_of(
                st.text(min_size=1, max_size=5).map(json_string),
                st.integers(min_value=0, max_value=100).map(str),
                st.booleans().map(lambda b: "true" if b else "false"),
                st.none().map(lambda _: "null"),
            ))

        tags_len = draw(st.integers(min_value=0, max_value=3))
        tags_elements = [tag_element() for _ in range(tags_len)]
        tags_val = "[" + ",".join(tags_elements) + "]"

        # child field: null or record with depth limit 1
        if depth >= 1:
            child_val = "null"
        else:
            # 50% chance null, 50% chance nested record with depth=1
            if draw(st.booleans()):
                child_val = "null"
            else:
                child_val = draw(record(depth + 1))

        # Compose JSON object text
        # id_val might be string or number or float string or non-digit string
        # amount_val is JSON text already (string literal or number or null)
        # name_val is JSON text already (string literal or null or number or boolean as string)
        # status_val is JSON text already (string literal or null)
        # tags_val is JSON array text
        # child_val is JSON object text or null

        # id_val: if string type, emit as JSON string, else emit as is
        if isinstance(id_val, str):
            # Check if id_val is a digit string, then emit as number, else as string
            if id_val.isdigit():
                id_json = id_val
            else:
                # id_val is non-digit string, emit as JSON string
                id_json = json_string(id_val)
        else:
            # id_val is int or float string
            id_json = str(id_val)

        json_obj = (
            "{" +
            f'"id":{id_json},' +
            f'"amount":{amount_val},' +
            f'"name":{name_val},' +
            f'"status":{status_val},' +
            f'"tags":{tags_val},' +
            f'"child":{child_val}' +
            "}"
        )
        return json_obj

    # Draw top-level record with depth=0
    json_text = draw(record(0))
    return json_text.encode("utf-8")