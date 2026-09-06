from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status enum
    statuses = ["active", "inactive", "unknown"]

    # Helper to produce a JSON string literal with proper escaping of quotes and backslashes
    def json_string(s: str) -> str:
        # Minimal escaping: backslash and double quote
        s = s.replace("\\", "\\\\").replace('"', '\\"')
        # Also escape control characters for safety (e.g. newline, tab)
        s = s.replace("\b", "\\b").replace("\f", "\\f").replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
        return f'"{s}"'

    # Recursive record generator with bounded depth (max 1 level of child)
    def record(depth=0):
        # id: integer normally, but to induce divergence, sometimes string or float
        # amount: string normally, but sometimes number or null
        # name: string or null normally, but sometimes number or boolean
        # status: one of enum normally, but sometimes invalid string or null
        # tags: array of strings normally, but sometimes array of mixed types or empty array
        # child: null or record (only one level recursion)
        # We'll vary one or two fields per record to try to induce divergence.

        # Base valid fields
        # id: mostly int, sometimes string or float to induce divergence
        id_val = draw(st.one_of(
            st.integers(min_value=0, max_value=2**31-1),
            st.text(min_size=1, max_size=5).filter(lambda x: not x.isdigit()),  # non-digit string to cause parse failure
            st.floats(allow_infinity=False, allow_nan=False).map(lambda f: round(f, 2))
        ))

        # amount: mostly string representing a decimal number, sometimes number or null
        amount_val = draw(st.one_of(
            st.text(min_size=1, max_size=10).filter(lambda s: all(c in "0123456789." for c in s) and s.count('.') <= 1),
            st.floats(allow_infinity=False, allow_nan=False).map(lambda f: f"{f:.2f}"),
            st.none(),
            st.integers(min_value=0, max_value=1000)
        ))

        # name: string or null normally, sometimes boolean or number
        name_val = draw(st.one_of(
            st.none(),
            st.text(min_size=0, max_size=10),
            st.booleans(),
            st.integers(min_value=-100, max_value=100)
        ))

        # status: mostly valid enum, sometimes invalid string or null
        status_val = draw(st.one_of(
            st.sampled_from(statuses),
            st.text(min_size=1, max_size=7).filter(lambda s: s not in statuses),
            st.none()
        ))

        # tags: mostly array of strings, sometimes array with mixed types or empty
        tags_val = draw(st.one_of(
            st.lists(st.text(min_size=1, max_size=5), min_size=1, max_size=5),
            st.lists(st.one_of(st.text(min_size=1, max_size=5), st.integers(), st.booleans()), min_size=0, max_size=3)
        ))

        # child: null or one level record
        if depth == 0:
            child_val = draw(st.one_of(
                st.none(),
                record(depth=1)
            ))
        else:
            child_val = None

        # Now build JSON text for this record, carefully formatting each field.

        # id field
        if isinstance(id_val, int):
            id_json = str(id_val)
        elif isinstance(id_val, float):
            # JSON float formatting
            id_json = repr(id_val)
        else:
            # string
            id_json = json_string(str(id_val))

        # amount field
        if amount_val is None:
            amount_json = "null"
        elif isinstance(amount_val, (int, float)):
            amount_json = repr(amount_val)
        else:
            amount_json = json_string(str(amount_val))

        # name field
        if name_val is None:
            name_json = "null"
        elif isinstance(name_val, str):
            name_json = json_string(name_val)
        elif isinstance(name_val, bool):
            name_json = "true" if name_val else "false"
        else:
            # number
            name_json = repr(name_val)

        # status field
        if status_val is None:
            status_json = "null"
        else:
            status_json = json_string(status_val)

        # tags field
        # tags_val is a list, elements can be string/int/bool
        tags_json_items = []
        for t in tags_val:
            if isinstance(t, str):
                tags_json_items.append(json_string(t))
            elif isinstance(t, bool):
                tags_json_items.append("true" if t else "false")
            elif isinstance(t, int):
                tags_json_items.append(str(t))
            else:
                # fallback to string
                tags_json_items.append(json_string(str(t)))
        tags_json = "[" + ",".join(tags_json_items) + "]"

        # child field
        if child_val is None:
            child_json = "null"
        else:
            child_json = child_val

        # Compose full JSON object string
        json_obj = (
            "{" +
            f'"id":{id_json},' +
            f'"amount":{amount_json},' +
            f'"name":{name_json},' +
            f'"status":{status_json},' +
            f'"tags":{tags_json},' +
            f'"child":{child_json}' +
            "}"
        )

        return json_obj

    # Draw the top-level record JSON string
    json_text = record(depth=0)

    # Return as bytes (UTF-8)
    return json_text.encode("utf-8")