```python
from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status field
    statuses = ["active", "inactive", "unknown"]

    # Helper to produce a JSON string literal with proper escaping of quotes and backslashes
    def json_string(s: str) -> str:
        # Escape backslash and quote
        esc = s.replace("\\", "\\\\").replace("\"", "\\\"")
        # Also escape control chars minimally (newline, tab)
        esc = esc.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
        return f"\"{esc}\""

    # Generate a JSON string literal for amount field (string representing a number)
    # To provoke divergence, sometimes produce numeric strings with leading zeros, or with + sign, or exponent
    def amount_string():
        # Choose among normal decimal, leading zeros, exponent, + sign, negative sign (though negative might be invalid)
        base_num = draw(st.integers(min_value=0, max_value=999999).map(str))
        variant = draw(st.sampled_from(["normal", "leading_zeros", "plus_sign", "exponent", "decimal_point"]))
        if variant == "normal":
            return json_string(base_num)
        elif variant == "leading_zeros":
            # prepend 1-3 zeros
            zeros = "0" * draw(st.integers(1, 3))
            return json_string(zeros + base_num)
        elif variant == "plus_sign":
            return json_string("+" + base_num)
        elif variant == "exponent":
            # add exponent part, e.g. 1e3, 12E-2
            exp_sign = draw(st.sampled_from(["", "+", "-"]))
            exp_num = draw(st.integers(0, 5))
            return json_string(base_num + "e" + exp_sign + str(exp_num))
        else:  # decimal_point
            # insert decimal point at random position
            if len(base_num) == 1:
                return json_string(base_num + ".0")
            pos = draw(st.integers(1, len(base_num)-1))
            return json_string(base_num[:pos] + "." + base_num[pos:])

    # Generate a JSON string or null for name field
    # To provoke divergence, sometimes produce null, sometimes empty string, sometimes string with unicode escapes
    def name_value():
        choice = draw(st.sampled_from(["null", "string", "empty_string", "unicode_escape"]))
        if choice == "null":
            return "null"
        elif choice == "string":
            # normal string with ascii letters and spaces
            s = draw(st.text(alphabet=st.characters(blacklist_categories=("Cs",)), min_size=1, max_size=20))
            return json_string(s)
        elif choice == "empty_string":
            return "\"\""
        else:  # unicode_escape
            # produce string with unicode escape sequences (e.g. \u00E9)
            # Hypothesis text does not produce escapes, so we insert manually
            base = draw(st.text(alphabet=st.characters(blacklist_categories=("Cs",)), min_size=1, max_size=10))
            # insert 1-2 unicode escapes at random positions
            def insert_escapes(s):
                n = draw(st.integers(1, 2))
                for _ in range(n):
                    pos = draw(st.integers(0, len(s)))
                    codepoint = draw(st.integers(0x80, 0xFFFF))
                    esc = "\\u" + f"{codepoint:04x}"
                    s = s[:pos] + esc + s[pos:]
                return s
            s = insert_escapes(base)
            return json_string(s)

    # Generate status field: one of the three strings, or sometimes a wrong type to provoke divergence
    def status_value():
        # 80% chance valid string, 20% chance invalid type (number, null, bool)
        valid = draw(st.booleans())
        if valid:
            return json_string(draw(st.sampled_from(statuses)))
        else:
            # invalid type: number, null, bool, empty string
            invalid = draw(st.sampled_from([
                "null",
                "true",
                "false",
                "0",
                "-1",
                "\"\""
            ]))
            return invalid

    # Generate tags array: array of strings
    # To provoke divergence, sometimes empty array, sometimes array with null, sometimes array with non-string
    def tags_value():
        # 70% valid array of strings, 30% array with one invalid element or null
        valid = draw(st.booleans())
        if valid:
            # array of 0-5 strings (ascii letters)
            count = draw(st.integers(0, 5))
            strs = []
            for _ in range(count):
                s = draw(st.text(alphabet=st.characters(blacklist_categories=("Cs",)), min_size=1, max_size=10))
                strs.append(json_string(s))
            return "[" + ",".join(strs) + "]"
        else:
            # array with one invalid element or null
            count = draw(st.integers(1, 5))
            elems = []
            invalid_pos = draw(st.integers(0, count-1))
            for i in range(count):
                if i == invalid_pos:
                    # invalid element: number, null, bool
                    invalid = draw(st.sampled_from([
                        "null",
                        "true",
                        "false",
                        "0",
                        "-1",
                        "123"
                    ]))
                    elems.append(invalid)
                else:
                    s = draw(st.text(alphabet=st.characters(blacklist_categories=("Cs",)), min_size=1, max_size=10))
                    elems.append(json_string(s))
            return "[" + ",".join(elems) + "]"

    # Generate id field: integer, but sometimes as string to provoke divergence
    def id_value():
        # 80% integer, 20% string integer
        as_string = draw(st.booleans())
        val = draw(st.integers(min_value=0, max_value=1000000))
        if as_string:
            return json_string(str(val))
        else:
            return str(val)

    # Generate child field: either null or a nested record (one level only)
    # To provoke divergence, sometimes produce child with one field wrong type or missing
    def child_value(depth=0):
        # limit recursion depth to 1
        if depth > 0:
            return "null"
        # 50% null, 50% nested record
        is_null = draw(st.booleans())
        if is_null:
            return "null"
        else:
            # nested record with one field possibly wrong or missing
            # choose one field to corrupt or omit or keep valid
            fields = ["id", "amount", "name", "status", "tags", "child"]
            corrupt_field = draw(st.sampled_from(fields + [None]))  # None means no corruption

            # Build nested record fields
            nested_fields = {}

            # id
            if corrupt_field == "id":
                # corrupt id: string with letters or float string
                corrupt_id = draw(st.sampled_from([
                    json_string("notanint"),
                    json_string("123.45"),
                    "\"-1\"",
                    "null"
                ]))
                nested_fields["id"] = corrupt_id
            else:
                nested_fields["id"] = str(draw(st.integers(min_value=0, max_value=1000000)))

            # amount
            if corrupt_field == "amount":
                # amount as number (not string), or null
                nested_fields["amount"] = draw(st.sampled_from([
                    "123",
                    "null",
                    "true"
                ]))
            else:
                nested_fields["amount"] = amount_string()

            # name
            if corrupt_field == "name":
                # name as number or missing
                choice = draw(st.sampled_from(["number", "missing"]))
                if choice == "number":
                    nested_fields["name"] = "123"
                else:
                    # omit field by not adding it
                    pass
            else:
                nested_fields["name"] = name_value()

            # status
            if corrupt_field == "status":
                # status as invalid string or number
                nested_fields["status"] = draw(st.sampled_from([
                    json_string("invalid"),
                    "123",
                    "null"
                ]))
            else:
                nested_fields["status"] = status_value()

            # tags
            if corrupt_field == "tags":
                # tags as string or null
                nested_fields["tags"] = draw(st.sampled_from([
                    json_string("notanarray"),
                    "null"
                ]))
            else:
                nested_fields["tags"] = tags_value()

            # child (nested child disallowed, so always null or missing)
            if corrupt_field == "child":
                # child as string or number
                nested_fields["child"] = draw(st.sampled_from([
                    json_string("notarecord"),
                    "123",
                    "null"
                ]))
            else:
                nested_fields["child"] = "null"

            # Compose nested JSON object string
            # If name was omitted, remove it from dict keys
            if corrupt_field == "name" and "name" not in nested_fields:
                keys = [k for k in nested_fields.keys()]
            else:
                keys = list(nested_fields.keys())

            # Compose fields in fixed order for consistency
            order = ["id", "amount", "name", "status", "tags", "child"]
            parts = []
            for k in order:
                if k in nested_fields:
                    parts.append(json_string(k) + ":" + nested_fields[k])
            return "{" + ",".join(parts) + "}"

    # Compose top-level record fields, with one or two fields possibly corrupted or missing
    # To provoke divergence, corrupt or omit exactly one field at top level, otherwise valid

    # Choose one or two fields to corrupt or omit or keep valid
    fields = ["id", "amount", "name", "status", "tags", "child"]
    corrupt_fields = draw(st.lists(st.sampled_from(fields), min_size=0, max_size=2, unique=True))

    # Build top-level fields
    top_fields = {}

    # id
    if "id" in corrupt_fields:
        # id as string with letters or float string or null
        top_fields["id"] = draw(st.sampled_from([
            json_string("notanint"),
            json_string("123.45"),
            "\"-1\"",
            "null"
        ]))
    else:
        top_fields["id"] = id_value()

    # amount
    if "amount" in corrupt_fields:
        # amount as number (not string), or null
        top_fields["amount"] = draw(st.sampled_from([
            "123",
            "null",
            "true"
        ]))
    else:
        top_fields["amount"] = amount_string()

    # name
    if "name" in corrupt_fields:
        # name as number or missing
        choice = draw(st.sampled_from(["number", "missing"]))
        if choice == "number":
            top_fields["name"] = "123"
        else:
            # omit field by not adding it
            pass
    else:
        top_fields["name"] = name_value()

    # status
    if "status" in corrupt_fields:
        # status as invalid string or number
        top_fields["status"] = draw(st.sampled_from([
            json_string("invalid"),
            "123",
            "null"
        ]