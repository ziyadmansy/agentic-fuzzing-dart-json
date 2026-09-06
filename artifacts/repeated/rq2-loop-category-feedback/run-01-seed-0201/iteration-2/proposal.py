from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status enum
    statuses = ["active", "inactive", "unknown"]

    # Helper: generate a JSON string literal with proper escaping of quotes and backslashes
    def json_string(s: str) -> str:
        # Minimal escaping for " and \ (enough for this context)
        esc = s.replace("\\", "\\\\").replace("\"", "\\\"")
        return f"\"{esc}\""

    # Helper: generate a JSON array of strings
    def json_string_array(draw):
        # Array length 0..3 for bounded size
        arr_len = draw(st.integers(min_value=0, max_value=3))
        # Elements are strings (non-null), possibly empty, ASCII printable chars except quotes/backslash for simplicity
        elems = draw(st.lists(st.text(alphabet=st.characters(blacklist_characters='"\\"'), min_size=0, max_size=5), min_size=arr_len, max_size=arr_len))
        return "[" + ",".join(json_string(e) for e in elems) + "]"

    # Helper: generate "name" field value: either null or string
    def json_name(draw):
        # 80% chance string, 20% chance null (to test null vs string)
        if draw(st.booleans().filter(lambda b: b)):  # roughly 50/50 but we want more strings
            # string possibly empty, ASCII printable except quotes/backslash
            s = draw(st.text(alphabet=st.characters(blacklist_characters='"\\"'), max_size=10))
            return json_string(s)
        else:
            return "null"

    # Helper: generate "status" field value: mostly valid enum, sometimes invalid string or wrong type
    def json_status(draw):
        # 85% chance valid enum string, 15% chance invalid
        if draw(st.integers(min_value=1, max_value=100)) <= 85:
            val = draw(st.sampled_from(statuses))
            return json_string(val)
        else:
            # invalid: either a wrong string, a number, or null
            choice = draw(st.integers(min_value=1, max_value=3))
            if choice == 1:
                # invalid string
                invalid_str = draw(st.text(alphabet=st.characters(blacklist_characters='"\\"'), min_size=1, max_size=10).filter(lambda x: x not in statuses))
                return json_string(invalid_str)
            elif choice == 2:
                # number as string (to test type confusion)
                num = draw(st.integers(min_value=-1000, max_value=1000))
                return str(num)
            else:
                # null
                return "null"

    # Helper: generate "amount" field value: string, but sometimes numeric string, sometimes empty
    def json_amount(draw):
        # 90% string of digits or decimal, 10% empty string or whitespace
        p = draw(st.integers(min_value=1, max_value=100))
        if p <= 90:
            # numeric string, possibly negative, possibly decimal
            neg = draw(st.booleans())
            int_part = draw(st.integers(min_value=0, max_value=9999))
            frac_part = draw(st.one_of(st.just(""), st.text(alphabet="0123456789", min_size=1, max_size=3)))
            s = ("-" if neg else "") + str(int_part)
            if frac_part != "":
                s += "." + frac_part
            return json_string(s)
        else:
            # empty or whitespace string
            ws = draw(st.text(alphabet=" \t\n\r", min_size=0, max_size=3))
            return json_string(ws)

    # Helper: generate "id" field value: integer or sometimes string (to test type confusion)
    def json_id(draw):
        # 90% integer, 10% string of digits
        if draw(st.integers(min_value=1, max_value=100)) <= 90:
            return str(draw(st.integers(min_value=0, max_value=1000000)))
        else:
            # string of digits
            digits = draw(st.text(alphabet="0123456789", min_size=1, max_size=7))
            return json_string(digits)

    # Recursive generation of the "child" field: either null or a nested record (one level max)
    def json_child(draw, depth=0):
        # Limit recursion depth to 1 (only one level of child)
        if depth >= 1:
            return "null"
        # 70% chance null, 30% chance nested record
        if draw(st.integers(min_value=1, max_value=100)) <= 70:
            return "null"
        else:
            # nested record with same schema but no further nesting
            return json_record(draw, depth=depth+1)

    # Generate a full record JSON object as string
    def json_record(draw, depth=0):
        # We will vary one or two fields to be "almost" valid but slightly off to trigger divergence
        # Pick 0-2 fields to mutate away from nominal valid values
        fields = ["id", "amount", "name", "status", "tags", "child"]
        mutate_count = draw(st.integers(min_value=0, max_value=2))
        mutate_fields = draw(st.lists(st.sampled_from(fields), min_size=mutate_count, max_size=mutate_count, unique=True))

        # For each field, generate value, mutated if in mutate_fields
        parts = []

        # id
        if "id" in mutate_fields:
            # mutate id: sometimes string instead of int, sometimes negative int, sometimes float string
            choice = draw(st.integers(min_value=1, max_value=3))
            if choice == 1:
                # string digits (already covered by json_id)
                val = json_id(draw)
            elif choice == 2:
                # negative int as int
                val = str(draw(st.integers(min_value=-1000, max_value=-1)))
            else:
                # float string (invalid for int)
                val = json_string(str(draw(st.floats(allow_infinity=False, allow_nan=False, width=32))))
            parts.append(f"\"id\":{val}")
        else:
            parts.append(f"\"id\":{json_id(draw)}")

        # amount
        if "amount" in mutate_fields:
            # mutate amount: sometimes number (not string), sometimes null
            choice = draw(st.integers(min_value=1, max_value=3))
            if choice == 1:
                # number (int or float) instead of string
                val = str(draw(st.one_of(st.integers(min_value=-1000, max_value=10000), st.floats(allow_infinity=False, allow_nan=False))))
                parts.append(f"\"amount\":{val}")
            elif choice == 2:
                # null instead of string
                parts.append(f"\"amount\":null")
            else:
                # empty string or whitespace string
                parts.append(f"\"amount\":{json_amount(draw)}")
        else:
            parts.append(f"\"amount\":{json_amount(draw)}")

        # name
        if "name" in mutate_fields:
            # mutate name: sometimes number, sometimes missing (omit field), sometimes boolean
            choice = draw(st.integers(min_value=1, max_value=3))
            if choice == 1:
                # number instead of string/null
                val = str(draw(st.integers(min_value=-1000, max_value=1000)))
                parts.append(f"\"name\":{val}")
            elif choice == 2:
                # boolean instead of string/null
                val = "true" if draw(st.booleans()) else "false"
                parts.append(f"\"name\":{val}")
            else:
                # null explicitly
                parts.append(f"\"name\":null")
        else:
            parts.append(f"\"name\":{json_name(draw)}")

        # status
        if "status" in mutate_fields:
            # mutate status: sometimes invalid string, sometimes number, sometimes null
            parts.append(f"\"status\":{json_status(draw)}")
        else:
            # valid status string
            val = draw(st.sampled_from(statuses))
            parts.append(f"\"status\":{json_string(val)}")

        # tags
        if "tags" in mutate_fields:
            # mutate tags: sometimes array of numbers, sometimes null, sometimes empty array
            choice = draw(st.integers(min_value=1, max_value=3))
            if choice == 1:
                # array of numbers instead of strings
                arr_len = draw(st.integers(min_value=0, max_value=3))
                nums = [str(draw(st.integers(min_value=-100, max_value=100))) for _ in range(arr_len)]
                parts.append(f"\"tags\":[{','.join(nums)}]")
            elif choice == 2:
                # null instead of array
                parts.append(f"\"tags\":null")
            else:
                # empty array
                parts.append(f"\"tags\":[]")
        else:
            parts.append(f"\"tags\":{json_string_array(draw)}")

        # child
        if "child" in mutate_fields:
            # mutate child: sometimes missing (omit field), sometimes number, sometimes string, sometimes null
            choice = draw(st.integers(min_value=1, max_value=4))
            if choice == 1:
                # omit field entirely (not allowed by schema but tests missing field)
                pass
            elif choice == 2:
                # number
                val = str(draw(st.integers(min_value=-1000, max_value=1000)))
                parts.append(f"\"child\":{val}")
            elif choice == 3:
                # string
                val = json_string(draw(st.text(min_size=0, max_size=10)))
                parts.append(f"\"child\":{val}")
            else:
                # null
                parts.append(f"\"child\":null")
        else:
            parts.append(f"\"child\":{json_child(draw, depth=depth)}")

        # Join all parts with commas
        # If child was omitted, parts length is 5, else 6
        json_obj = "{" + ",".join(parts) + "}"
        return json_obj

    # Generate the top-level record JSON string
    json_text = json_record(draw, depth=0)
    # Return as bytes (UTF-8)
    return json_text.encode("utf-8")