from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status field
    statuses = ["active", "inactive", "unknown"]

    # Helper to produce a JSON string literal with proper escaping of quotes and backslashes
    def json_string(s: str) -> str:
        # Escape backslash and double quotes minimally
        s = s.replace("\\", "\\\\").replace('"', '\\"')
        # Also escape control chars (at least newline, tab, carriage return)
        s = s.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
        return '"' + s + '"'

    # Helper to produce JSON array of strings
    def json_string_array(strs):
        return "[" + ",".join(json_string(s) for s in strs) + "]"

    # Recursive record generator, bounded depth = 1 (child is either null or a record with child=null)
    def record(depth=0):
        # id: integer (always present)
        # amount: string (always present)
        # name: string or null (always present)
        # status: one of "active", "inactive", "unknown" (always present)
        # tags: array of strings (always present)
        # child: record or null (one level of recursion normally)

        # To maximize divergence, we vary one or two fields with "almost valid" values:
        # - id: integer normally, but sometimes a stringified integer or float string
        # - amount: string normally, but sometimes a numeric string with weird formatting or empty string
        # - name: string or null normally, but sometimes a number or boolean (invalid type)
        # - status: normally one of three strings, but sometimes a similar string with case difference or typo
        # - tags: array of strings normally, but sometimes empty array, or array with null or number inside
        # - child: null or record normally, but sometimes missing (not allowed), or null replaced by empty object {}

        # We produce a dict of fields as strings (JSON text), then join.

        # id field variations
        id_choice = draw(st.one_of(
            st.integers(min_value=0, max_value=2**31-1).map(str),  # normal integer as string
            st.integers(min_value=0, max_value=2**31-1).map(lambda i: '"' + str(i) + '"'),  # id as JSON string (wrong type)
            st.floats(min_value=0, max_value=1e6, allow_infinity=False, allow_nan=False).map(lambda f: str(int(f)) if f.is_integer() else str(f)),  # float as number string (wrong type)
        ))
        # amount field variations
        amount_choice = draw(st.one_of(
            st.text(min_size=1, max_size=10).filter(lambda s: all(c not in s for c in '"\\\n\r\t')),  # normal string without escapes
            st.just(""),  # empty string
            st.integers(min_value=0, max_value=100000).map(str),  # numeric string but as number string (wrong type)
            st.floats(min_value=0, max_value=100000, allow_infinity=False, allow_nan=False).map(lambda f: str(f)),  # float string
        ))

        # name field variations
        name_choice = draw(st.one_of(
            st.none().map(lambda _: "null"),
            st.text(min_size=0, max_size=15).map(json_string),
            st.integers(min_value=-1000, max_value=1000).map(str),  # invalid type: number instead of string or null
            st.booleans().map(lambda b: "true" if b else "false"),  # invalid type: boolean
        ))

        # status field variations
        status_choice = draw(st.one_of(
            st.sampled_from(statuses).map(json_string),
            st.sampled_from(["Active", "Inactive", "Unknown"]).map(json_string),  # case difference
            st.sampled_from(["activ", "inactiv", "unknwon"]).map(json_string),  # typos
            st.integers(min_value=0, max_value=2).map(str),  # invalid type: number
        ))

        # tags field variations
        # array of strings normally, but sometimes with null or number inside
        tags_len = draw(st.integers(min_value=0, max_value=5))
        tags_elements = []
        for _ in range(tags_len):
            elem = draw(st.one_of(
                st.text(min_size=1, max_size=10).filter(lambda s: all(c not in s for c in '"\\\n\r\t')).map(json_string),
                st.just("null"),
                st.integers(min_value=0, max_value=100).map(str),
            ))
            tags_elements.append(elem)
        tags_choice = "[" + ",".join(tags_elements) + "]"

        # child field variations
        # null or record normally, but sometimes empty object {}, or missing (not allowed but test)
        # We never omit fields because schema says always present, but we try empty object or null or record
        if depth == 0:
            child_choice = draw(st.one_of(
                st.just("null"),
                record(depth=1),
                st.just("{}"),  # empty object instead of record or null
            ))
        else:
            # at depth 1, child must be null normally (one level recursion)
            child_choice = draw(st.one_of(
                st.just("null"),
                st.just("{}"),  # empty object invalid
            ))

        # Compose fields in random order to test order independence
        fields = [
            ('"id"', id_choice),
            ('"amount"', json_string(amount_choice) if not amount_choice.startswith('"') else amount_choice),
            ('"name"', name_choice),
            ('"status"', status_choice),
            ('"tags"', tags_choice),
            ('"child"', child_choice),
        ]

        # Shuffle fields order
        draw_order = draw(st.permutations(fields))
        # Join fields as JSON object
        obj_text = "{" + ",".join(f"{k}:{v}" for k, v in draw_order) + "}"
        return obj_text

    # Generate top-level record
    top_obj = record(depth=0)
    return top_obj.encode("utf-8")