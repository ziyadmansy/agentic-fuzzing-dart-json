from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status enum
    statuses = ["active", "inactive", "unknown"]

    # Helper: produce a JSON string literal from a Python string
    def json_string(s: str) -> str:
        # Minimal escaping for JSON string (only backslash and quote)
        # Hypothesis strings are unicode, but we keep it simple here.
        esc = s.replace('\\', '\\\\').replace('"', '\\"')
        return '"' + esc + '"'

    # Helper: produce JSON text for a string or null, with a chance of wrong type
    def gen_name():
        # 80% chance to be string or null, 20% chance to be a number (wrong type)
        choice = draw(st.floats(min_value=0, max_value=1))
        if choice < 0.4:
            # string or null normally
            return st.one_of(st.none().map(lambda _: "null"),
                             st.text(min_size=0, max_size=10).map(json_string))
        elif choice < 0.8:
            # null or string but with some empty string edge cases
            return st.one_of(st.none().map(lambda _: "null"),
                             st.just(json_string("")))
        else:
            # wrong type: number as string (unquoted number)
            return st.integers(min_value=-10, max_value=10).map(str)

    # Helper: produce JSON text for status, with chance of invalid enum string or number
    def gen_status():
        # 85% chance valid enum string, 15% chance invalid string or number
        choice = draw(st.floats(min_value=0, max_value=1))
        if choice < 0.85:
            return st.sampled_from(statuses).map(json_string)
        elif choice < 0.925:
            # invalid string (not in enum)
            return st.text(min_size=1, max_size=8).filter(lambda s: s not in statuses).map(json_string)
        else:
            # number instead of string
            return st.integers(min_value=-5, max_value=5).map(str)

    # Helper: produce JSON text for tags array of strings, or wrong type
    def gen_tags():
        # 90% chance array of strings, 10% chance wrong type (string or number)
        choice = draw(st.floats(min_value=0, max_value=1))
        if choice < 0.9:
            # array of 0-3 strings
            arr = st.lists(st.text(min_size=0, max_size=5), min_size=0, max_size=3)
            return arr.map(lambda lst: "[" + ",".join(json_string(s) for s in lst) + "]")
        elif choice < 0.95:
            # string instead of array
            return st.text(min_size=0, max_size=5).map(json_string)
        else:
            # number instead of array
            return st.integers(min_value=-3, max_value=3).map(str)

    # Helper: produce JSON text for id (integer), or stringified number, or float
    def gen_id():
        # 80% int, 10% stringified int, 10% float
        choice = draw(st.floats(min_value=0, max_value=1))
        if choice < 0.8:
            return st.integers(min_value=0, max_value=1000).map(str)
        elif choice < 0.9:
            return st.integers(min_value=0, max_value=1000).map(lambda i: json_string(str(i)))
        else:
            return st.floats(min_value=0, max_value=1000).map(lambda f: repr(f))

    # Helper: produce JSON text for amount (string), or number (wrong type)
    def gen_amount():
        # 85% string, 15% number
        choice = draw(st.floats(min_value=0, max_value=1))
        if choice < 0.85:
            # string representing a decimal number or empty string
            s = draw(st.one_of(
                st.decimals(min_value=0, max_value=1000, places=2).map(str),
                st.just("")
            ))
            return json_string(s)
        else:
            # number (int or float)
            n = draw(st.one_of(st.integers(min_value=0, max_value=1000),
                               st.floats(min_value=0, max_value=1000)))
            return str(n)

    # Recursive generation of child record or null, bounded depth 1
    def gen_child(depth=0):
        if depth > 0:
            # Only allow null at depth > 0 to avoid deep recursion
            return st.just("null")
        else:
            # 70% chance null, 30% chance nested record
            choice = draw(st.floats(min_value=0, max_value=1))
            if choice < 0.7:
                return st.just("null")
            else:
                # nested record, but depth=1 max
                return gen_record(depth=1)

    # Generate a full record JSON text
    def gen_record(depth=0):
        # Compose fields, each is a JSON text fragment (string)
        id_json = gen_id()
        amount_json = gen_amount()
        name_json = gen_name()
        status_json = gen_status()
        tags_json = gen_tags()
        child_json = gen_child(depth)

        # Draw all fields
        id_val = draw(id_json)
        amount_val = draw(amount_json)
        name_val = draw(name_json)
        status_val = draw(status_json)
        tags_val = draw(tags_json)
        child_val = draw(child_json)

        # Compose JSON object text with all fields in fixed order
        obj = (
            '{'
            + '"id":' + id_val + ','
            + '"amount":' + amount_val + ','
            + '"name":' + name_val + ','
            + '"status":' + status_val + ','
            + '"tags":' + tags_val + ','
            + '"child":' + child_val
            + '}'
        )
        return obj

    # Draw top-level record JSON text
    json_text = gen_record(depth=0)

    # Return bytes
    return json_text.encode("utf-8")