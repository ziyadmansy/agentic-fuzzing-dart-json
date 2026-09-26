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
    def record(depth=0):
        # id: integer, but we will sometimes produce a string or float to cause divergence
        # amount: string, but sometimes number or null or boolean to cause divergence
        # name: string or null, sometimes number or boolean to cause divergence
        # status: one of the three strings, sometimes null or wrong string or number
        # tags: array of strings, sometimes empty array, sometimes array with non-string elements
        # child: null or record (depth limit 1)

        # id field: mostly integer, sometimes stringified int, sometimes float, sometimes string non-int
        id_val = draw(st.one_of(
            st.integers(min_value=0, max_value=2**31-1).map(str),  # as string (wrong type)
            st.integers(min_value=0, max_value=2**31-1),           # as int (correct)
            st.floats(allow_nan=False, allow_infinity=False).map(lambda f: str(f)),  # as string float (wrong type)
            st.text(min_size=1, max_size=5).filter(lambda s: not s.isdigit())  # random string (wrong type)
        ))

        # amount field: mostly string, sometimes number, sometimes boolean, sometimes null
        amount_val = draw(st.one_of(
            st.text(min_size=1, max_size=10).map(json_string),  # correct string
            st.integers(min_value=0, max_value=100000).map(str),  # number as string (wrong type)
            st.floats(allow_nan=False, allow_infinity=False).map(lambda f: str(f)),  # number as string (wrong type)
            st.booleans().map(lambda b: "true" if b else "false"),  # boolean as string (wrong type)
            st.just("null")  # null literal (wrong type)
        ))

        # name field: string or null normally, sometimes number, boolean, or missing (simulate missing by null)
        name_choice = draw(st.one_of(
            st.none().map(lambda _: "null"),  # null literal
            st.text(min_size=0, max_size=10).map(json_string),  # string literal
            st.integers(min_value=0, max_value=1000).map(str),  # number as string (wrong type)
            st.booleans().map(lambda b: "true" if b else "false")  # boolean as string (wrong type)
        ))

        # status field: mostly one of the three strings, sometimes null, sometimes wrong string, sometimes number
        status_choice = draw(st.one_of(
            st.sampled_from(statuses).map(json_string),  # correct enum string
            st.none().map(lambda _: "null"),             # null literal (wrong type)
            st.text(min_size=1, max_size=10).filter(lambda s: s not in statuses).map(json_string),  # wrong string
            st.integers(min_value=0, max_value=10).map(str)  # number (wrong type)
        ))

        # tags field: array of strings normally, sometimes array with non-string elements, sometimes empty array
        # We'll produce JSON array text manually
        def tags_array():
            # choose length 0 to 3
            length = draw(st.integers(min_value=0, max_value=3))
            elements = []
            for _ in range(length):
                elem = draw(st.one_of(
                    st.text(min_size=0, max_size=10).map(json_string),  # string element
                    st.integers(min_value=0, max_value=100).map(str),  # number element (wrong type)
                    st.none().map(lambda _: "null"),                    # null element (wrong type)
                    st.booleans().map(lambda b: "true" if b else "false")  # boolean element (wrong type)
                ))
                elements.append(elem)
            return "[" + ",".join(elements) + "]"

        tags_val = tags_array()

        # child field: null or a record with child=null (depth limit 1)
        if depth == 0:
            child_is_null = draw(st.booleans())
            if child_is_null:
                child_val = "null"
            else:
                # child record with depth=1, child=null forced
                # We reuse record with depth=1, but force child=null
                def child_record():
                    # id field for child: integer only (to reduce complexity)
                    child_id = draw(st.integers(min_value=0, max_value=2**31-1))
                    # amount: string only
                    child_amount = draw(st.text(min_size=1, max_size=10)).replace('"', '\\"')
                    child_amount = json_string(child_amount)
                    # name: string or null
                    child_name = draw(st.one_of(
                        st.none().map(lambda _: "null"),
                        st.text(min_size=0, max_size=10).map(json_string)
                    ))
                    # status: correct enum string only
                    child_status = draw(st.sampled_from(statuses)).map(json_string)
                    # tags: array of strings only
                    child_tags_len = draw(st.integers(min_value=0, max_value=3))
                    child_tags = []
                    for _ in range(child_tags_len):
                        s = draw(st.text(min_size=0, max_size=10))
                        child_tags.append(json_string(s))
                    child_tags_val = "[" + ",".join(child_tags) + "]"
                    # child: null literal
                    return (
                        '{'
                        f'"id":{child_id},'
                        f'"amount":{child_amount},'
                        f'"name":{child_name},'
                        f'"status":{child_status},'
                        f'"tags":{child_tags_val},'
                        f'"child":null'
                        '}'
                    )
                child_val = child_record()
        else:
            # depth 1: child must be null
            child_val = "null"

        # Compose the full record JSON text
        # id_val can be int or string or float string or random string
        # amount_val is string literal or number string or boolean string or null literal (all as strings)
        # name_choice is string literal or null literal or number string or boolean string (all as strings)
        # status_choice is string literal or null literal or wrong string literal or number string (all as strings)
        # tags_val is JSON array text
        # child_val is JSON object text or null literal

        # id_val: if it's a string literal, it is quoted, else raw number or string
        # We detect if id_val is a string literal by checking if it starts and ends with quotes
        # But we never put quotes around id_val in the generation, so if id_val is a string, it is raw text
        # So we must quote id_val if it is not a pure number or float string

        def id_json_text(v):
            # If v is an int, output as number
            if isinstance(v, int):
                return str(v)
            # else v is string: check if it looks like a number (int or float)
            try:
                float(v)
                # looks like number, output raw
                return v
            except Exception:
                # not a number, output as JSON string literal
                return json_string(v)

        id_json = id_json_text(id_val)

        # amount_val is already a JSON literal string (quoted string or number string or boolean string or null literal)
        # name_choice is already a JSON literal string (quoted string or null literal or number string or boolean string)
        # status_choice is already a JSON literal string (quoted string or null literal or number string)
        # tags_val is JSON array text
        # child_val is JSON object text or null literal

        # Compose fields in order
        json_text = (
            '{'
            f'"id":{id_json},'
            f'"amount":{amount_val},'
            f'"name":{name_choice},'
            f'"status":{status_choice},'
            f'"tags":{tags_val},'
            f'"child":{child_val}'
            '}'
        )

        return json_text

    # Draw the top-level record with depth=0
    result = record(depth=0)

    # Return bytes
    return result.encode("utf-8")