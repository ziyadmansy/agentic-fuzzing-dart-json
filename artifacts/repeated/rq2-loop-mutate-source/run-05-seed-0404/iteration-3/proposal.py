from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status enum
    statuses = ["active", "inactive", "unknown"]

    # Base valid fields strategies
    id_strat = st.one_of(
        st.integers(min_value=-(2**31), max_value=2**31-1),  # normal int range
        st.text(min_size=1, max_size=5).filter(lambda s: not s.isdigit())  # invalid string instead of int
    )
    amount_strat = st.one_of(
        st.text(min_size=1, max_size=10),  # valid string amount
        st.integers(min_value=0, max_value=1000).map(str),  # numeric strings
        st.integers(min_value=-(2**31), max_value=2**31-1),  # invalid int instead of string
        st.just(None),  # invalid null instead of string
    )
    name_strat = st.one_of(
        st.none(),
        st.text(min_size=0, max_size=10),
        st.integers(min_value=0, max_value=1000),  # invalid int instead of string/null
        st.just("null"),  # string "null" (valid string)
    )
    status_strat = st.one_of(
        st.sampled_from(statuses),
        st.text(min_size=1, max_size=7).filter(lambda s: s not in statuses),  # invalid enum string
        st.none(),  # null instead of string
        st.integers(min_value=0, max_value=3),  # invalid int instead of string
    )
    tags_strat = st.one_of(
        st.lists(st.text(min_size=0, max_size=5), max_size=5),
        st.none(),  # invalid null instead of array
        st.text(min_size=0, max_size=10),  # invalid string instead of array
        st.integers(min_value=0, max_value=10),  # invalid int instead of array
    )

    # Recursive child strategy with bounded depth
    # To avoid infinite recursion, max depth = 1 (child.child always null)
    @st.composite
    def record(draw, depth=0):
        # For child, only recurse if depth==0, else null or invalid
        child_val = None
        if depth == 0:
            # 80% chance to produce a valid child record, 20% chance invalid types/null
            child_val = draw(st.one_of(
                record(depth=depth+1),
                st.none(),
                st.text(min_size=0, max_size=10),
                st.integers(min_value=0, max_value=10),
            ))
        else:
            # depth>0: child must be null or invalid (no further recursion)
            child_val = draw(st.one_of(
                st.none(),
                st.text(min_size=0, max_size=10),
                st.integers(min_value=0, max_value=10),
            ))

        # Draw fields with some chance of wrong type or missing
        # But all fields must be present (per problem statement)
        # So we produce fields always, but some with invalid types

        id_val = draw(id_strat)
        amount_val = draw(amount_strat)
        name_val = draw(name_strat)
        status_val = draw(status_strat)
        tags_val = draw(tags_strat)

        # Build JSON text manually, carefully encoding values

        def json_str(s):
            # Escape backslash and quotes minimally for JSON string
            # Also escape control chars \b \f \n \r \t
            # Hypothesis strings are unicode, but we keep it simple
            s = s.replace('\\', '\\\\').replace('"', '\\"')
            s = s.replace('\b', '\\b').replace('\f', '\\f').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
            return f'"{s}"'

        def json_val(v):
            # Encode JSON value from Python value or invalid type
            if v is None:
                return "null"
            elif isinstance(v, bool):
                return "true" if v else "false"
            elif isinstance(v, int):
                return str(v)
            elif isinstance(v, str):
                return json_str(v)
            elif isinstance(v, list):
                # list of strings expected, but could be invalid
                items = []
                for x in v:
                    if isinstance(x, str):
                        items.append(json_str(x))
                    else:
                        # invalid element type, encode as JSON string forcibly
                        items.append(json_str(str(x)))
                return "[" + ",".join(items) + "]"
            elif isinstance(v, dict):
                # Should not happen here
                return "{}"
            else:
                # fallback: encode as JSON string forcibly
                return json_str(str(v))

        # child_val can be dict (record) or invalid type
        if isinstance(child_val, str) or isinstance(child_val, int) or child_val is None:
            child_json = json_val(child_val)
        else:
            # child_val is a JSON string from recursive call
            child_json = child_val

        # Compose JSON object string
        # id must be integer normally, but we allow invalid types
        # amount must be string normally, but we allow invalid types
        # name string or null
        # status enum string
        # tags array of strings
        # child record or null

        # id_val might be int or string (invalid)
        id_json = json_val(id_val)
        amount_json = json_val(amount_val)
        name_json = json_val(name_val)
        status_json = json_val(status_val)
        tags_json = json_val(tags_val)

        # --- Revised part: introduce subtle type boundary variations and null-vs-missing simulation ---
        # Since all fields must be present, simulate "missing" by using null or invalid types selectively
        # Also, add a small chance to produce numeric strings with leading zeros for amount (edge case)
        # And add a small chance to produce empty string for status (invalid enum but string)
        # Also, add a chance for tags to be an empty array or array with null elements (invalid elements)

        # Adjust amount_json to sometimes have leading zeros numeric string (edge case)
        if isinstance(amount_val, str) and amount_val.isdigit() and draw(st.booleans()):
            # Add leading zeros
            amount_json = json_str("0" * draw(st.integers(min_value=1, max_value=3)) + amount_val)

        # Adjust status_json to sometimes be empty string (invalid enum but string)
        if draw(st.booleans()):
            if status_val not in statuses and isinstance(status_val, str) and len(status_val) > 0:
                # leave as is (invalid enum string)
                pass
            else:
                # 10% chance to make status empty string
                if draw(st.integers(min_value=1, max_value=10)) == 1:
                    status_json = json_str("")

        # Adjust tags_json to sometimes include null elements (invalid elements)
        if isinstance(tags_val, list) and len(tags_val) > 0 and draw(st.booleans()):
            # Replace some elements with null
            new_tags = []
            for tag in tags_val:
                if draw(st.booleans()):
                    new_tags.append(None)
                else:
                    new_tags.append(tag)
            tags_json = json_val(new_tags)

        return (
            "{" +
            f'"id":{id_json},'
            f'"amount":{amount_json},'
            f'"name":{name_json},'
            f'"status":{status_json},'
            f'"tags":{tags_json},'
            f'"child":{child_json}' +
            "}"
        )

    # Draw top-level record, get JSON string, encode as bytes UTF-8
    json_text = draw(record())
    return json_text.encode("utf-8")