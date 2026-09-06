from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status field
    statuses = ["active", "inactive", "unknown"]

    # Helper: produce a JSON string literal from a Python string (with minimal escaping)
    def json_string(s: str) -> str:
        # Escape backslash and double quote and control chars minimally
        # Hypothesis strings are unicode, but we keep it simple:
        s = s.replace("\\", "\\\\").replace('"', '\\"')
        # Replace control chars with \u escapes
        def esc_char(c):
            if ord(c) < 0x20:
                return "\\u%04x" % ord(c)
            return c
        s = "".join(esc_char(c) for c in s)
        return '"' + s + '"'

    # Recursive record generator, bounded depth 1 (child can be null or record with child=null)
    def record(depth=0):
        # id: integer (always present)
        # amount: string (always present)
        # name: string or null (always present)
        # status: one of "active", "inactive", "unknown" (always present)
        # tags: array of strings (always present)
        # child: record or null (one level recursion normally)
        # We will produce a dict of strings representing JSON fragments for each field,
        # then join them with commas and braces.

        # id: integer, but we will sometimes produce a string or float to cause divergence
        # Strategy: mostly int, sometimes stringified int, sometimes float, sometimes negative
        id_val = draw(st.one_of(
            st.integers(min_value=0, max_value=2**31-1).map(str),
            st.integers(min_value=-1000, max_value=-1).map(str),
            st.floats(allow_nan=False, allow_infinity=False).map(lambda f: ("%.1f" % f)),
            st.text(min_size=1, max_size=5).filter(lambda s: s.isdigit()),
        ))

        # amount: string, but sometimes a number or null to cause divergence
        # Mostly string decimal numbers, sometimes integer strings, sometimes null, sometimes number literals
        amount_val = draw(st.one_of(
            st.text(min_size=1, max_size=10).filter(lambda s: all(c in "0123456789." for c in s) and s.count('.')<=1).map(json_string),
            st.integers(min_value=0, max_value=100000).map(str),
            st.floats(allow_nan=False, allow_infinity=False).map(lambda f: ("%.2f" % f)),
            st.just("null"),
        ))

        # name: string or null, but also sometimes a number or boolean to cause divergence
        name_val = draw(st.one_of(
            st.none().map(lambda _: "null"),
            st.text(min_size=0, max_size=10).map(json_string),
            st.integers(min_value=-100, max_value=100).map(str),
            st.booleans().map(lambda b: "true" if b else "false"),
        ))

        # status: one of the three strings, but sometimes null or wrong string or number to cause divergence
        status_val = draw(st.one_of(
            st.sampled_from(statuses).map(json_string),
            st.none().map(lambda _: "null"),
            st.text(min_size=1, max_size=10).filter(lambda s: s not in statuses).map(json_string),
            st.integers(min_value=0, max_value=2).map(str),
        ))

        # tags: array of strings, but sometimes array of numbers, or null, or empty array
        # We'll produce JSON array text directly
        def tags_array():
            # array of strings (normal)
            arr_strs = draw(st.lists(st.text(min_size=0, max_size=5), min_size=0, max_size=5))
            arr_json = "[" + ",".join(json_string(s) for s in arr_strs) + "]"
            return arr_json

        def tags_array_numbers():
            arr_nums = draw(st.lists(st.integers(min_value=-10, max_value=10), min_size=0, max_size=5))
            arr_json = "[" + ",".join(str(n) for n in arr_nums) + "]"
            return arr_json

        tags_val = draw(st.one_of(
            st.just(tags_array()),
            st.just(tags_array_numbers()),
            st.just("null"),
            st.just("[]"),
        ))

        # child: either null or a record with child=null (depth limited to 1)
        if depth == 0:
            child_val = draw(st.one_of(
                st.just("null"),
                record(depth=1),
            ))
        else:
            # depth==1, child must be null to avoid deeper recursion
            child_val = "null"

        # Compose JSON object string
        # We deliberately vary the order of fields sometimes to test order sensitivity
        fields = [
            ('"id"', id_val),
            ('"amount"', amount_val),
            ('"name"', name_val),
            ('"status"', status_val),
            ('"tags"', tags_val),
            ('"child"', child_val),
        ]

        # Shuffle fields sometimes to vary order
        if draw(st.booleans()):
            import random
            random.shuffle(fields)

        obj_str = "{" + ",".join(f"{k}:{v}" for k, v in fields) + "}"
        return obj_str

    # Generate top-level record string
    json_text = record(depth=0)

    # Return bytes
    return json_text.encode("utf-8")