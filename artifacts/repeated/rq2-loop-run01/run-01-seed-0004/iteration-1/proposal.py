from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status enum
    statuses = ["active", "inactive", "unknown"]

    # Helper to produce a JSON string literal with proper escaping of quotes and backslashes
    def json_string(s: str) -> str:
        # Minimal escaping for " and \ (enough for our generated strings)
        s = s.replace("\\", "\\\\").replace('"', '\\"')
        return '"' + s + '"'

    # Helper to produce a JSON array of strings (tags)
    def json_string_array(strings):
        return "[" + ",".join(json_string(s) for s in strings) + "]"

    # Recursive record generator with bounded depth (max 1 level of recursion)
    def record(depth=0):
        # id: integer (always present)
        # amount: string (always present)
        # name: string or null (always present)
        # status: one of "active", "inactive", "unknown" (always present)
        # tags: array of strings (always present)
        # child: record or null (one level recursion normally)
        # We will produce a dict of string->value and then serialize to JSON text

        # To induce divergence, we vary one or two fields slightly off from spec:
        # - id: sometimes a string instead of int
        # - amount: sometimes a number or null instead of string
        # - name: sometimes missing (to test missing vs null), or null, or string
        # - status: sometimes a string not in enum, or null, or missing
        # - tags: sometimes array of non-strings, or empty array, or null
        # - child: sometimes null, sometimes a record, sometimes missing

        # We produce a dict of fieldname -> JSON text (string representing the value)
        fields = {}

        # id: mostly int, sometimes string (to test type divergence)
        id_choice = draw(st.one_of(
            st.integers(min_value=0, max_value=1000).map(str),
            st.text(min_size=1, max_size=5).map(json_string),
        ))
        # id must be integer normally, so if string, we emit as JSON string literal
        # id_choice is JSON text for the id field value
        fields["id"] = id_choice

        # amount: mostly string, sometimes number or null
        amount_type = draw(st.sampled_from(["string", "number", "null"]))
        if amount_type == "string":
            amount_val = draw(st.text(min_size=1, max_size=10))
            fields["amount"] = json_string(amount_val)
        elif amount_type == "number":
            amount_val = draw(st.floats(allow_nan=False, allow_infinity=False))
            # floats can be serialized as str, but must be valid JSON number
            # Use repr to get canonical float string
            fields["amount"] = repr(amount_val)
        else:
            fields["amount"] = "null"

        # name: string or null or missing (missing to test divergence)
        name_option = draw(st.sampled_from(["string", "null", "missing"]))
        if name_option == "string":
            name_val = draw(st.one_of(st.none(), st.text(min_size=0, max_size=10)))
            if name_val is None:
                # null
                fields["name"] = "null"
            else:
                fields["name"] = json_string(name_val)
        elif name_option == "null":
            fields["name"] = "null"
        else:
            # missing: do not add "name" key at all
            pass

        # status: mostly valid enum string, sometimes invalid string, null, or missing
        status_option = draw(st.sampled_from(["valid", "invalid", "null", "missing"]))
        if status_option == "valid":
            status_val = draw(st.sampled_from(statuses))
            fields["status"] = json_string(status_val)
        elif status_option == "invalid":
            # invalid string not in enum
            invalid_status = draw(st.text(min_size=1, max_size=10).filter(lambda s: s not in statuses))
            fields["status"] = json_string(invalid_status)
        elif status_option == "null":
            fields["status"] = "null"
        else:
            # missing
            pass

        # tags: array of strings normally, sometimes array with non-string, or null, or missing
        tags_option = draw(st.sampled_from(["valid", "nonstring", "null", "missing"]))
        if tags_option == "valid":
            tags_list = draw(st.lists(st.text(min_size=0, max_size=5), min_size=0, max_size=5))
            fields["tags"] = json_string_array(tags_list)
        elif tags_option == "nonstring":
            # array with mixed types (strings and numbers)
            str_part = draw(st.lists(st.text(min_size=0, max_size=5), min_size=0, max_size=3))
            num_part = draw(st.lists(st.integers(min_value=0, max_value=10).map(str), min_size=0, max_size=2))
            # combine and shuffle
            combined = str_part + num_part
            # shuffle combined
            from random import shuffle
            shuffle(combined)
            # serialize: strings quoted, numbers as is
            def serialize_tag(t):
                try:
                    # if t is numeric string, emit as number
                    int(t)
                    return t
                except Exception:
                    return json_string(t)
            fields["tags"] = "[" + ",".join(serialize_tag(t) for t in combined) + "]"
        elif tags_option == "null":
            fields["tags"] = "null"
        else:
            # missing
            pass

        # child: null, record (one level recursion), or missing
        child_option = draw(st.sampled_from(["null", "record", "missing"]))
        if child_option == "null":
            fields["child"] = "null"
        elif child_option == "record" and depth == 0:
            # recurse once only
            child_json = record(depth=depth + 1)
            fields["child"] = child_json
        else:
            # missing
            pass

        # Compose JSON object text from fields dict
        # Fields order randomized to avoid bias
        keys = list(fields.keys())
        draw(st.randoms())  # consume randomness for shuffle
        # shuffle keys deterministically using draw.random
        rnd = draw.random
        keys.sort(key=lambda k: rnd.random())
        items = []
        for k in keys:
            items.append(json_string(k) + ":" + fields[k])
        json_obj = "{" + ",".join(items) + "}"
        return json_obj.encode("utf-8")

    return record()