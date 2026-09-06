from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for enum values
    STATUS_VALUES = ["active", "inactive", "unknown"]

    # To produce a valid JSON string literal with proper escaping,
    # we generate a unicode string without control chars or quotes/backslashes,
    # then wrap it in quotes.
    def json_string(s: str) -> str:
        # Escape backslash and double quotes
        s = s.replace("\\", "\\\\").replace('"', '\\"')
        # Escape control characters (U+0000 to U+001F)
        def esc_char(c):
            if ord(c) < 0x20:
                return "\\u%04x" % ord(c)
            return c
        s = "".join(esc_char(c) for c in s)
        return '"' + s + '"'

    # Compose JSON array of strings
    def json_array_of_strings(lst):
        return "[" + ",".join(json_string(x) for x in lst) + "]"

    # Compose JSON object from dict of key->json_value (already serialized strings)
    def json_object(d):
        # keys are always strings, no need to escape keys here because keys are fixed literals
        items = []
        for k, v in d.items():
            items.append('"' + k + '":' + v)
        return "{" + ",".join(items) + "}"

    # Recursive record generator with bounded depth
    def gen_record(depth):
        # id: integer (always present)
        # amount: string (always present)
        # name: string or null (always present)
        # status: one of "active", "inactive", "unknown" (always present)
        # tags: array of strings (always present)
        # child: Record or null (one level recursion normally)

        # We will produce a dict of JSON text values (strings) for each field

        # id: integer, but we will sometimes produce a string or float to cause divergence
        # Strategy: mostly int, sometimes stringified int, sometimes float, sometimes negative, zero, large
        id_val = draw(
            st.one_of(
                st.integers(min_value=0, max_value=2**31 - 1).map(str),
                st.integers(min_value=-1000, max_value=-1).map(str),
                st.floats(allow_nan=False, allow_infinity=False).map(lambda f: ('%.8g' % f)),
                st.text(min_size=1, max_size=5, alphabet=st.characters(blacklist_characters='"\\')).filter(lambda s: s.isdigit()),
            )
        )

        # amount: string, but sometimes a number or null to cause divergence
        # Mostly a decimal string, sometimes a number string with weird formatting, sometimes null (invalid)
        amount_val = draw(
            st.one_of(
                st.decimals(min_value=0, max_value=1e9, places=2).map(lambda d: str(d)),
                st.text(min_size=1, max_size=10, alphabet=st.characters(blacklist_characters='"\\')).filter(lambda s: s.replace('.', '', 1).isdigit()),
                st.integers(min_value=0, max_value=1000000).map(str),
                st.just("null"),  # invalid but syntactically valid string "null"
            )
        )
        # Wrap amount_val in quotes if not "null" (which is invalid for amount but syntactically valid JSON string)
        if amount_val != "null":
            amount_val_json = json_string(amount_val)
        else:
            amount_val_json = "null"  # null literal, not string

        # name: string or null
        # Sometimes null literal, sometimes string, sometimes empty string, sometimes string with unicode
        name_val = draw(
            st.one_of(
                st.none().map(lambda _: "null"),
                st.text(min_size=0, max_size=10).map(json_string),
            )
        )

        # status: one of "active", "inactive", "unknown"
        # Sometimes invalid string to cause divergence, sometimes null literal
        status_val = draw(
            st.one_of(
                st.sampled_from(STATUS_VALUES).map(json_string),
                st.text(min_size=1, max_size=7).filter(lambda s: s not in STATUS_VALUES).map(json_string),
                st.just("null"),
            )
        )

        # tags: array of strings (always present)
        # Sometimes empty array, sometimes array with empty string, sometimes array with null element (invalid)
        # Sometimes array of numbers as strings (valid), sometimes array with a number literal (invalid)
        tags_len = draw(st.integers(min_value=0, max_value=3))
        tags_elements = []
        for _ in range(tags_len):
            tag = draw(
                st.one_of(
                    st.text(min_size=0, max_size=10).map(json_string),
                    st.just("null"),
                    st.integers(min_value=0, max_value=100).map(str),
                )
            )
            tags_elements.append(tag)
        tags_val = "[" + ",".join(tags_elements) + "]"

        # child: either null or a nested record (only one level deep)
        if depth <= 0:
            child_val = "null"
        else:
            # 50% chance null, 50% chance nested record with depth-1
            if draw(st.booleans()):
                child_val = "null"
            else:
                child_val = gen_record(depth - 1)

        # Compose the record JSON object
        obj = {
            "id": id_val,
            "amount": amount_val_json,
            "name": name_val,
            "status": status_val,
            "tags": tags_val,
            "child": child_val,
        }
        return json_object(obj)

    # Generate record with depth 1 (one level recursion)
    json_text = gen_record(1)
    return json_text.encode("utf-8")