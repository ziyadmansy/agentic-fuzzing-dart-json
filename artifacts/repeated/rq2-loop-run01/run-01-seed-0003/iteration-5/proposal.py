from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants
    STATUS_VALUES = ['"active"', '"inactive"', '"unknown"']

    # Helper to produce a JSON string literal with controlled escaping
    def json_string(draw):
        # Use ASCII printable except control chars and backslash, quote
        # but allow some unicode escapes to trigger subtle parser differences
        # We'll keep it simple here: generate strings without quotes or backslash
        s = draw(st.text(
            alphabet=st.characters(
                blacklist_characters=['\\', '"', '\b', '\f', '\n', '\r', '\t'],
                min_codepoint=0x20,
                max_codepoint=0x7E,
            ),
            min_size=0,
            max_size=10,
        ))
        # Occasionally insert unicode escapes by replacing some chars with \uXXXX
        # But since we cannot use json module, skip this complexity for now
        return '"' + s + '"'

    # id: integer, but try to produce borderline integer values as strings sometimes
    # We'll produce either an integer or a string that looks like an integer (to cause type confusion)
    def id_field(draw):
        # 80% integer, 20% string integer
        if draw(st.booleans().filter(lambda b: b)):  # always True, just to get a bool
            val = draw(st.integers(min_value=-(2**31), max_value=2**31-1))
            return str(val)
        else:
            val = draw(st.integers(min_value=-(2**31), max_value=2**31-1))
            return '"' + str(val) + '"'

    # amount: string, but sometimes a number or null to cause divergence
    def amount_field(draw):
        choice = draw(st.integers(min_value=0, max_value=9))
        if choice <= 6:
            # valid string amount, numeric string or arbitrary string
            # numeric string with optional decimal point
            if draw(st.booleans()):
                # numeric string
                whole = draw(st.integers(min_value=0, max_value=9999))
                frac = draw(st.one_of(st.none(), st.integers(min_value=0, max_value=99)))
                if frac is None:
                    return '"' + str(whole) + '"'
                else:
                    return '"' + f"{whole}.{frac:02d}" + '"'
            else:
                # arbitrary string
                return json_string(draw)
        elif choice == 7:
            # number (not string) - invalid type for amount
            if draw(st.booleans()):
                return str(draw(st.integers(min_value=-(10**9), max_value=10**9)))
            else:
                # float number
                f = draw(st.floats(allow_nan=False, allow_infinity=False, width=32))
                # format float with minimal digits
                return repr(f)
        elif choice == 8:
            # null instead of string
            return "null"
        else:
            # boolean instead of string
            return "true" if draw(st.booleans()) else "false"

    # name: string or null, but sometimes number or missing (missing handled by omitting field)
    # We will always include the field (per spec), but sometimes put null or number or boolean
    def name_field(draw):
        choice = draw(st.integers(min_value=0, max_value=9))
        if choice <= 6:
            # string or null
            if draw(st.booleans()):
                return json_string(draw)
            else:
                return "null"
        elif choice == 7:
            # number instead of string/null
            return str(draw(st.integers(min_value=-1000, max_value=1000)))
        elif choice == 8:
            # boolean instead of string/null
            return "true" if draw(st.booleans()) else "false"
        else:
            # empty string
            return '""'

    # status: one of "active", "inactive", "unknown"
    # but sometimes wrong string, or number, or null
    def status_field(draw):
        choice = draw(st.integers(min_value=0, max_value=9))
        if choice <= 6:
            # valid enum string
            return draw(st.sampled_from(STATUS_VALUES))
        elif choice == 7:
            # invalid string
            return json_string(draw)
        elif choice == 8:
            # null
            return "null"
        else:
            # number or boolean
            if draw(st.booleans()):
                return str(draw(st.integers(min_value=0, max_value=10)))
            else:
                return "true" if draw(st.booleans()) else "false"

    # tags: array of strings, but sometimes null, or array with non-string elements, or empty array
    def tags_field(draw):
        choice = draw(st.integers(min_value=0, max_value=9))
        if choice <= 6:
            # valid array of strings (possibly empty)
            length = draw(st.integers(min_value=0, max_value=5))
            elems = []
            for _ in range(length):
                elems.append(json_string(draw))
            return "[" + ",".join(elems) + "]"
        elif choice == 7:
            # null instead of array
            return "null"
        elif choice == 8:
            # array with some non-string elements
            length = draw(st.integers(min_value=1, max_value=5))
            elems = []
            for _ in range(length):
                t = draw(st.integers(min_value=0, max_value=3))
                if t == 0:
                    elems.append(json_string(draw))
                elif t == 1:
                    elems.append(str(draw(st.integers(min_value=-10, max_value=10))))
                elif t == 2:
                    elems.append("null")
                else:
                    elems.append("true" if draw(st.booleans()) else "false")
            return "[" + ",".join(elems) + "]"
        else:
            # empty array
            return "[]"

    # child: either null or a nested record (one level recursion max)
    # We will produce either null or a nested record with no further child (child=null)
    # But sometimes produce malformed child: missing fields, wrong types, or null replaced by number
    def child_field(draw):
        choice = draw(st.integers(min_value=0, max_value=9))
        if choice <= 5:
            # null child
            return "null"
        elif choice <= 8:
            # nested record with correct fields but possibly one field off
            # build nested record fields with slight chance of type error on one field
            # We'll reuse the same field generators but force child.child=null always
            # To avoid infinite recursion, child.child is always null

            # For nested child, we allow only one field to be "off" to maximize divergence
            # Pick which field to corrupt (or none)
            corrupt_field = draw(st.sampled_from(['id', 'amount', 'name', 'status', 'tags', None]))

            def nested_id():
                if corrupt_field == 'id':
                    # corrupt id: string instead of int or vice versa
                    if draw(st.booleans()):
                        return '"' + str(draw(st.integers(min_value=-(2**31), max_value=2**31-1))) + '"'
                    else:
                        return str(draw(st.integers(min_value=-(2**31), max_value=2**31-1)))
                else:
                    return str(draw(st.integers(min_value=-(2**31), max_value=2**31-1)))

            def nested_amount():
                if corrupt_field == 'amount':
                    # number instead of string
                    return str(draw(st.integers(min_value=-1000, max_value=1000)))
                else:
                    # valid string numeric
                    whole = draw(st.integers(min_value=0, max_value=999))
                    return '"' + str(whole) + '"'

            def nested_name():
                if corrupt_field == 'name':
                    # number instead of string/null
                    return str(draw(st.integers(min_value=-100, max_value=100)))
                else:
                    # string or null
                    if draw(st.booleans()):
                        return json_string(draw)
                    else:
                        return "null"

            def nested_status():
                if corrupt_field == 'status':
                    # invalid string
                    return '"invalid_status"'
                else:
                    return draw(st.sampled_from(STATUS_VALUES))

            def nested_tags():
                if corrupt_field == 'tags':
                    # null instead of array
                    return "null"
                else:
                    length = draw(st.integers(min_value=0, max_value=3))
                    elems = []
                    for _ in range(length):
                        elems.append(json_string(draw))
                    return "[" + ",".join(elems) + "]"

            nested_fields = [
                '"id":' + nested_id(),
                '"amount":' + nested_amount(),
                '"name":' + nested_name(),
                '"status":' + nested_status(),
                '"tags":' + nested_tags(),
                '"child":null'
            ]
            return "{" + ",".join(nested_fields) + "}"
        else:
            # malformed child: number instead of object/null
            return str(draw(st.integers(min_value=-10, max_value=10)))

    # Compose top-level record fields
    fields = [
        '"id":' + id_field(draw),
        '"amount":' + amount_field(draw),
        '"name":' + name_field(draw),
        '"status":' + status_field(draw),
        '"tags":' + tags_field(draw),
        '"child":' + child_field(draw),
    ]

    json_text = "{" + ",".join(fields) + "}"
    return json_text.encode("utf-8")