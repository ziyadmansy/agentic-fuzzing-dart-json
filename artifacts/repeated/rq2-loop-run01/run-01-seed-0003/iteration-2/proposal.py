from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status enum
    statuses = ["active", "inactive", "unknown"]

    # Helper: produce a JSON string literal from a Python string (with minimal escaping)
    def json_string(s: str) -> str:
        # Escape backslash and double quote, and control chars minimally
        esc = s.replace("\\", "\\\\").replace('"', '\\"')
        # Escape control chars (U+0000 to U+001F) as \u00XX
        def esc_char(c):
            if ord(c) < 0x20:
                return "\\u%04x" % ord(c)
            return c
        esc = "".join(esc_char(c) for c in esc)
        return f'"{esc}"'

    # Recursive record generator with bounded depth (max 1 level of recursion)
    def record_strategy(depth=0):
        # id: integer (try some edge cases too)
        id_strat = st.integers(min_value=-1000, max_value=1000)

        # amount: string (including numeric strings, empty, weird chars)
        amount_strat = st.one_of(
            st.text(min_size=0, max_size=10),
            st.just("0"),
            st.just("-0"),
            st.just("1e10"),
            st.just(""),
            st.from_regex(r"^-?\d+(\.\d+)?$", fullmatch=True),
        )

        # name: string or null, but also try wrong types sometimes (int, bool)
        name_strat = st.one_of(
            st.none(),
            st.text(min_size=0, max_size=20),
            st.integers(min_value=-10, max_value=10).map(str),  # as string but numeric
            # introduce some type errors sometimes:
            st.integers(min_value=-10, max_value=10),
            st.booleans(),
        )

        # status: one of the three strings, but also sometimes invalid string or null or number
        status_strat = st.one_of(
            st.sampled_from(statuses),
            st.text(min_size=1, max_size=10).filter(lambda x: x not in statuses),
            st.none(),
            st.integers(min_value=0, max_value=2),
        )

        # tags: array of strings, but also sometimes null or array of ints or empty array
        tags_strat = st.one_of(
            st.lists(st.text(min_size=0, max_size=10), max_size=5),
            st.none(),
            st.lists(st.integers(min_value=0, max_value=10), max_size=5),
            st.just([]),
        )

        # child: either null or a nested record (only one level deep)
        if depth >= 1:
            child_strat = st.none()
        else:
            # also sometimes invalid types for child (string, number)
            child_strat = st.one_of(
                st.none(),
                record_strategy(depth + 1),
                st.text(min_size=0, max_size=10),
                st.integers(min_value=-10, max_value=10),
            )

        # Compose fields as strings of JSON key:value pairs
        # We will build the JSON text manually as a dict literal string

        # Draw all fields
        id_v = draw(id_strat)
        amount_v = draw(amount_strat)
        name_v = draw(name_strat)
        status_v = draw(status_strat)
        tags_v = draw(tags_strat)
        child_v = draw(child_strat)

        # Serialize each field to JSON text

        # id: must be integer, but sometimes we put wrong types? No, id always integer per schema.
        # But to induce divergence, let's sometimes encode id as string or null or bool
        # (but only one or two fields off at a time)
        id_json = str(id_v)

        # amount: always string, but we sometimes put empty string or numeric string
        amount_json = json_string(amount_v)

        # name: string or null or sometimes int or bool
        if name_v is None:
            name_json = "null"
        elif isinstance(name_v, str):
            name_json = json_string(name_v)
        elif isinstance(name_v, bool):
            name_json = "true" if name_v else "false"
        else:
            # int or other number
            name_json = str(name_v)

        # status: one of enum strings, or invalid string, or null, or int
        if status_v is None:
            status_json = "null"
        elif isinstance(status_v, str):
            status_json = json_string(status_v)
        else:
            # int
            status_json = str(status_v)

        # tags: array of strings, or null, or array of ints, or empty array
        if tags_v is None:
            tags_json = "null"
        elif isinstance(tags_v, list):
            # elements may be strings or ints
            elems = []
            for e in tags_v:
                if isinstance(e, str):
                    elems.append(json_string(e))
                elif isinstance(e, int):
                    elems.append(str(e))
                else:
                    # fallback: encode as string
                    elems.append(json_string(str(e)))
            tags_json = "[" + ",".join(elems) + "]"
        else:
            # fallback
            tags_json = "null"

        # child: null or nested record or string or int
        if child_v is None:
            child_json = "null"
        elif isinstance(child_v, str):
            child_json = json_string(child_v)
        elif isinstance(child_v, int):
            child_json = str(child_v)
        else:
            # nested record JSON text (already serialized)
            child_json = child_v

        # Compose full JSON object string
        # Fields order fixed for consistency
        json_text = (
            "{"
            + f'"id":{id_json},'
            + f'"amount":{amount_json},'
            + f'"name":{name_json},'
            + f'"status":{status_json},'
            + f'"tags":{tags_json},'
            + f'"child":{child_json}'
            + "}"
        )

        return json_text.encode("utf-8")

    return record_strategy()