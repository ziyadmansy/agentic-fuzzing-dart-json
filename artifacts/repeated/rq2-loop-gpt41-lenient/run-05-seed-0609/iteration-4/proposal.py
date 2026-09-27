from hypothesis import strategies as st

# Constants for schema
STATUSES = ["active", "inactive", "unknown"]

def json_escape(s):
    # Minimal JSON string escaper for ASCII
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

@st.composite
def generated_json(draw, max_depth=1):
    # Helper to generate a valid or slightly malformed field value
    def field_id():
        # id: integer, but sometimes as string or float
        kind = draw(st.integers(0, 10))
        if kind < 7:
            return str(draw(st.integers(-2**31, 2**31-1)))
        elif kind == 7:
            # integer as string
            return json_escape(str(draw(st.integers(-2**31, 2**31-1))))
        elif kind == 8:
            # float instead of int
            return str(draw(st.floats(allow_nan=False, allow_infinity=False)))
        else:
            # null (should always be present, but test null)
            return "null"

    def field_amount():
        # amount: string, but sometimes as int, float, or null
        kind = draw(st.integers(0, 10))
        if kind < 7:
            return json_escape(draw(st.text(min_size=0, max_size=10)))
        elif kind == 7:
            # integer as string
            return str(draw(st.integers(-2**31, 2**31-1)))
        elif kind == 8:
            # float as string
            return str(draw(st.floats(allow_nan=False, allow_infinity=False)))
        elif kind == 9:
            # null
            return "null"
        else:
            # bool
            return "true" if draw(st.booleans()) else "false"

    def field_name():
        # name: string or null, but sometimes as int, float, or missing
        kind = draw(st.integers(0, 9))
        if kind < 6:
            return json_escape(draw(st.text(min_size=0, max_size=10)))
        elif kind == 6:
            return "null"
        elif kind == 7:
            return str(draw(st.integers(-2**31, 2**31-1)))
        elif kind == 8:
            return str(draw(st.floats(allow_nan=False, allow_infinity=False)))
        else:
            return "true" if draw(st.booleans()) else "false"

    def field_status():
        # status: enum, but sometimes as int, null, or wrong string
        kind = draw(st.integers(0, 9))
        if kind < 6:
            return json_escape(draw(st.sampled_from(STATUSES)))
        elif kind == 6:
            return json_escape(draw(st.text(min_size=1, max_size=8).filter(lambda s: s not in STATUSES)))
        elif kind == 7:
            return str(draw(st.integers(-2**31, 2**31-1)))
        elif kind == 8:
            return "null"
        else:
            return "true" if draw(st.booleans()) else "false"

    def field_tags():
        # tags: array of strings, but sometimes as string, null, or array with wrong types
        kind = draw(st.integers(0, 9))
        if kind < 6:
            # Normal array of strings
            arr = [json_escape(draw(st.text(min_size=0, max_size=8))) for _ in range(draw(st.integers(0, 4)))]
            return "[" + ",".join(arr) + "]"
        elif kind == 6:
            # Array with a non-string
            arr = [json_escape(draw(st.text(min_size=0, max_size=8))) for _ in range(draw(st.integers(0, 2)))]
            arr.append(str(draw(st.integers(-100, 100))))
            return "[" + ",".join(arr) + "]"
        elif kind == 7:
            # Just a string
            return json_escape(draw(st.text(min_size=0, max_size=8)))
        elif kind == 8:
            # null
            return "null"
        else:
            # Array with null
            arr = [json_escape(draw(st.text(min_size=0, max_size=8))) for _ in range(draw(st.integers(0, 2)))]
            arr.append("null")
            return "[" + ",".join(arr) + "]"

    def field_child(depth):
        # child: Record or null, but sometimes as wrong type
        kind = draw(st.integers(0, 8))
        if kind < 5 and depth < max_depth:
            # Recursively generate a child record
            return generated_json(max_depth=max_depth-1).map(lambda b: b.decode("utf-8")).example()
        elif kind == 5:
            return "null"
        elif kind == 6:
            # integer
            return str(draw(st.integers(-2**31, 2**31-1)))
        elif kind == 7:
            # string
            return json_escape(draw(st.text(min_size=0, max_size=8)))
        else:
            # array
            arr = [json_escape(draw(st.text(min_size=0, max_size=8))) for _ in range(draw(st.integers(0, 2)))]
            return "[" + ",".join(arr) + "]"

    # Randomly omit one field (but not more than one), or include all
    field_names = ["id", "amount", "name", "status", "tags", "child"]
    omit_field = draw(st.sampled_from(field_names + [None]))

    fields = []
    if omit_field != "id":
        fields.append('"id":' + field_id())
    if omit_field != "amount":
        fields.append('"amount":' + field_amount())
    if omit_field != "name":
        fields.append('"name":' + field_name())
    if omit_field != "status":
        fields.append('"status":' + field_status())
    if omit_field != "tags":
        fields.append('"tags":' + field_tags())
    if omit_field != "child":
        fields.append('"child":' + field_child(max_depth))

    # Shuffle field order
    draw(st.randoms()).shuffle(fields)

    json_obj = "{" + ",".join(fields) + "}"
    return json_obj.encode("utf-8")