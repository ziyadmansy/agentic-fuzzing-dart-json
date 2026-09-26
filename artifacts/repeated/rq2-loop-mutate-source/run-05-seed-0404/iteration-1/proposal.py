from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status field
    statuses = ["active", "inactive", "unknown"]

    # Helper to produce a JSON string literal with proper escaping of quotes and backslashes
    def json_string(s: str) -> str:
        # Minimal escaping for " and \ to keep JSON valid
        # Hypothesis strings won't contain control chars by default, so this is enough
        return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

    # Helper to produce JSON array of strings
    def json_array_of_strings(lst):
        return "[" + ",".join(json_string(x) for x in lst) + "]"

    # Helper to produce JSON null or a nested record (one-level recursion)
    # We limit recursion depth to 1 (child can have child=null only)
    def json_record(depth=0):
        # id: integer (try edge cases and normal)
        # amount: string (sometimes numeric string, sometimes weird strings)
        # name: string or null (try null, empty string, normal string, or a string with escapes)
        # status: one of the three strings, but also try wrong types or wrong strings to provoke divergence
        # tags: array of strings (try empty, normal, or with unusual strings)
        # child: null or record (only one level deep)
        # We will produce mostly valid fields but occasionally inject one or two subtle type errors or boundary cases

        # id: mostly integer, but sometimes a stringified number (wrong type)
        id_val = draw(st.one_of(
            st.integers(min_value=0, max_value=2**31-1).map(str),
            st.text(min_size=1, max_size=5).filter(lambda x: not x.isdigit()),  # invalid id string
        ))

        # amount: string, often numeric string, sometimes empty or weird
        amount_val = draw(st.one_of(
            st.text(min_size=1, max_size=10).filter(lambda s: all(c in "0123456789." for c in s)),
            st.text(min_size=0, max_size=10),
        ))

        # name: string or null, sometimes empty string, sometimes string with escapes
        name_val = draw(st.one_of(
            st.none(),
            st.text(min_size=0, max_size=10),
        ))

        # status: mostly valid strings, sometimes invalid strings or wrong types (number, null)
        status_val = draw(st.one_of(
            st.sampled_from(statuses),
            st.text(min_size=1, max_size=10).filter(lambda s: s not in statuses),
            st.integers(min_value=0, max_value=10).map(str),
            st.none(),
        ))

        # tags: array of strings, sometimes empty, sometimes with unusual strings (empty, spaces, unicode)
        tags_val = draw(st.lists(st.text(min_size=0, max_size=5), min_size=0, max_size=5))

        # child: null or nested record (only one level)
        if depth == 0:
            child_val = draw(st.one_of(
                st.just(None),
                json_record(depth=1),
            ))
        else:
            # depth 1: child must be null (no deeper recursion)
            child_val = None

        # Build JSON text for fields, injecting subtle type errors occasionally

        # id field: sometimes number, sometimes string (wrong type)
        # We try to produce either a number or a string JSON literal for id
        try:
            id_int = int(id_val)
            id_json = id_val  # number as string (valid JSON number)
        except Exception:
            id_json = json_string(id_val)  # string literal

        # amount: always string JSON literal
        amount_json = json_string(amount_val)

        # name: null or string literal
        if name_val is None:
            name_json = "null"
        else:
            name_json = json_string(name_val)

        # status: sometimes string literal, sometimes null, sometimes number (wrong type)
        if status_val is None:
            status_json = "null"
        elif status_val in statuses:
            status_json = json_string(status_val)
        else:
            # if status_val is integer string, output as number, else string literal
            try:
                intval = int(status_val)
                status_json = status_val
            except Exception:
                status_json = json_string(status_val)

        # tags: array of string literals
        tags_json = json_array_of_strings(tags_val)

        # child: null or nested record JSON text
        if child_val is None:
            child_json = "null"
        else:
            child_json = child_val

        # Compose JSON object text
        json_obj = (
            "{" +
            f'"id":{id_json},'
            f'"amount":{amount_json},'
            f'"name":{name_json},'
            f'"status":{status_json},'
            f'"tags":{tags_json},'
            f'"child":{child_json}'
            "}"
        )
        return json_obj

    # Draw the top-level record JSON text
    json_text = draw(json_record(depth=0))

    # Return as bytes
    return json_text.encode("utf-8")