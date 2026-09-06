from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status field
    statuses = ["active", "inactive", "unknown"]

    # Helper: produce a JSON string literal from a Python string (with minimal escaping)
    def json_string(s: str) -> str:
        # Escape backslash and double quote and control chars minimally
        # We do not import json, so do a minimal safe escaping for test purposes
        esc = s.replace('\\', '\\\\').replace('"', '\\"')
        # Replace control chars with \u escapes (only a few common ones)
        esc = esc.replace('\b', '\\b').replace('\f', '\\f').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
        return f'"{esc}"'

    # Recursive generator for "child" field, bounded to depth 1 (child.child always null)
    def record(depth: int) -> st.SearchStrategy[str]:
        # id: integer, but sometimes produce a string or float to cause divergence
        # amount: string, sometimes empty, sometimes numeric string, sometimes a number (wrong type)
        # name: string or null, sometimes a number or boolean to cause divergence
        # status: one of the three strings, sometimes a wrong string or null
        # tags: array of strings, sometimes empty, sometimes with non-string elements
        # child: null or record(depth+1), but at depth 1 child must be null

        # id field: mostly int, sometimes string or float (wrong type)
        id_val = draw(
            st.one_of(
                st.integers(min_value=0, max_value=1000).map(str),
                st.floats(allow_nan=False, allow_infinity=False).map(lambda f: f"{f}"),
                st.text(min_size=1, max_size=3).filter(lambda s: not s.isdigit()),  # invalid string id
            )
        )

        # amount field: mostly numeric strings, sometimes empty string, sometimes number (wrong type)
        amount_val = draw(
            st.one_of(
                st.text(min_size=0, max_size=5).filter(lambda s: all(c in "0123456789." for c in s)),  # numeric-ish string incl empty
                st.floats(allow_nan=False, allow_infinity=False).map(lambda f: f"{f}"),  # number as string (wrong type)
                st.integers(min_value=0, max_value=10000).map(str),
            )
        )

        # name field: string or null, sometimes number or boolean (wrong type)
        name_val = draw(
            st.one_of(
                st.none().map(lambda _: "null"),
                st.text(min_size=0, max_size=10).map(json_string),
                st.integers(min_value=0, max_value=1000).map(str),  # number as string (wrong type)
                st.booleans().map(lambda b: "true" if b else "false"),  # boolean as string (wrong type)
            )
        )

        # status field: mostly one of the three strings, sometimes null or wrong string
        status_val = draw(
            st.one_of(
                st.sampled_from(statuses).map(json_string),
                st.none().map(lambda _: "null"),
                st.text(min_size=1, max_size=7).filter(lambda s: s not in statuses).map(json_string),
            )
        )

        # tags field: array of strings, sometimes empty, sometimes with non-string elements (numbers, booleans)
        # We'll produce JSON array text directly
        def tag_element():
            return draw(
                st.one_of(
                    st.text(min_size=0, max_size=5).map(json_string),
                    st.integers(min_value=0, max_value=100).map(str),
                    st.booleans().map(lambda b: "true" if b else "false"),
                )
            )

        tags_len = draw(st.integers(min_value=0, max_value=3))
        tags_vals = [tag_element() for _ in range(tags_len)]
        tags_val = "[" + ",".join(tags_vals) + "]"

        # child field: null or record(depth+1), but at depth 1 child must be null
        if depth >= 1:
            child_val = "null"
        else:
            # sometimes null, sometimes a nested record
            child_val = draw(
                st.one_of(
                    st.just("null"),
                    record(depth + 1),
                )
            )

        # Compose JSON object string with fields in fixed order
        # id and amount are raw strings (id_val and amount_val) but must be JSON values:
        # id_val is a string representing a JSON value (int as string, float as string, or string literal)
        # amount_val is a string representing a JSON value (string literal or number literal)
        # name_val and status_val are JSON literals (strings or null)
        # tags_val is JSON array text
        # child_val is JSON object text or null

        # id_val: if it looks like a number string, output as number, else as string literal
        def id_json_val(s: str) -> str:
            # If s is digits only, output as number literal
            if s.isdigit():
                return s
            # If s looks like a float number (digits and dot), output as number literal
            try:
                float(s)
                # But reject if s contains letters or other chars
                if all(c in "0123456789.eE+-" for c in s):
                    return s
            except Exception:
                pass
            # else output as JSON string literal
            return json_string(s)

        id_json = id_json_val(id_val)

        # amount_val: if it looks like a number, output as number literal, else string literal
        def amount_json_val(s: str) -> str:
            try:
                float(s)
                if all(c in "0123456789.eE+-" for c in s) and s != "":
                    return s
            except Exception:
                pass
            return json_string(s)

        amount_json = amount_json_val(amount_val)

        # name_val and status_val are already JSON literals (strings or null)
        # tags_val is JSON array text
        # child_val is JSON object text or null

        json_obj = (
            "{" +
            f'"id":{id_json},' +
            f'"amount":{amount_json},' +
            f'"name":{name_val},' +
            f'"status":{status_val},' +
            f'"tags":{tags_val},' +
            f'"child":{child_val}' +
            "}"
        )
        return json_obj

    # Generate top-level record with depth 0
    json_text = draw(record(0))
    return json_text.encode("utf-8")