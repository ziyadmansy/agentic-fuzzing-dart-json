from hypothesis import strategies as st

# Helper strategies for slightly-off values
def almost_int(draw):
    # Usually an int, but sometimes a float, string, bool, or null
    choice = draw(st.integers(min_value=0, max_value=9))
    if choice < 6:
        return str(draw(st.integers(-2**31, 2**31-1)))
    elif choice == 6:
        return str(draw(st.floats(allow_nan=False, allow_infinity=False)))
    elif choice == 7:
        return '"' + str(draw(st.integers(-2**31, 2**31-1))) + '"'
    elif choice == 8:
        return "null"
    else:
        return "true" if draw(st.booleans()) else "false"

def almost_amount(draw):
    # Usually a string, but sometimes a number, null, or bool
    choice = draw(st.integers(min_value=0, max_value=9))
    if choice < 7:
        # Valid string, sometimes empty or weird
        s = draw(st.text(min_size=0, max_size=12))
        return '"' + s.replace('"', '\\"') + '"'
    elif choice == 7:
        return str(draw(st.integers(-10000, 10000)))
    elif choice == 8:
        return "null"
    else:
        return "false" if draw(st.booleans()) else "true"

def almost_name(draw):
    # Usually string or null, but sometimes number, bool, or missing
    choice = draw(st.integers(min_value=0, max_value=9))
    if choice < 6:
        s = draw(st.text(min_size=0, max_size=12))
        return '"' + s.replace('"', '\\"') + '"'
    elif choice == 6:
        return "null"
    elif choice == 7:
        return str(draw(st.integers(-10000, 10000)))
    elif choice == 8:
        return "true" if draw(st.booleans()) else "false"
    else:
        return None  # signal to omit the field

def almost_status(draw):
    # Usually one of the three, but sometimes a wrong string, null, or number
    choice = draw(st.integers(min_value=0, max_value=9))
    if choice < 7:
        val = draw(st.sampled_from(["active", "inactive", "unknown"]))
        return '"' + val + '"'
    elif choice == 7:
        # Wrong string
        s = draw(st.text(min_size=1, max_size=8).filter(lambda x: x not in {"active", "inactive", "unknown"}))
        return '"' + s.replace('"', '\\"') + '"'
    elif choice == 8:
        return "null"
    else:
        return str(draw(st.integers(-10, 10)))

def almost_tags(draw):
    # Usually array of strings, but sometimes array of wrong types, or not an array, or null
    choice = draw(st.integers(min_value=0, max_value=9))
    if choice < 6:
        # Valid array of strings
        arr = draw(st.lists(st.text(min_size=0, max_size=10).map(lambda s: '"' + s.replace('"', '\\"') + '"'), min_size=0, max_size=4))
        return "[" + ", ".join(arr) + "]"
    elif choice == 6:
        # Array with a wrong type inside
        arr = draw(st.lists(
            st.one_of(
                st.text(min_size=0, max_size=10).map(lambda s: '"' + s.replace('"', '\\"') + '"'),
                st.integers(-10, 10).map(str),
                st.just("null"),
                st.just("true"),
                st.just("false"),
            ), min_size=1, max_size=4
        ))
        return "[" + ", ".join(arr) + "]"
    elif choice == 7:
        # Not an array
        return '"' + draw(st.text(min_size=0, max_size=10)).replace('"', '\\"') + '"'
    elif choice == 8:
        return "null"
    else:
        return str(draw(st.integers(-10, 10)))

def almost_child(draw, depth):
    # Usually a nested record or null, but sometimes wrong type or missing
    choice = draw(st.integers(min_value=0, max_value=9))
    if choice < 6 and depth < 1:
        # Valid nested record
        return generated_record(draw, depth=depth+1)
    elif choice == 6:
        return "null"
    elif choice == 7:
        return '"' + draw(st.text(min_size=0, max_size=10)).replace('"', '\\"') + '"'
    elif choice == 8:
        return str(draw(st.integers(-10, 10)))
    else:
        return None  # signal to omit the field

def generated_record(draw, depth=0):
    # Compose the fields, sometimes omitting one optional field (name or child)
    fields = []

    # id: always present, but sometimes wrong type
    id_val = almost_int(draw)
    fields.append(f'"id": {id_val}')

    # amount: always present, but sometimes wrong type
    amount_val = almost_amount(draw)
    fields.append(f'"amount": {amount_val}')

    # name: sometimes omitted
    name_val = almost_name(draw)
    if name_val is not None:
        fields.append(f'"name": {name_val}')

    # status: always present, but sometimes wrong type
    status_val = almost_status(draw)
    fields.append(f'"status": {status_val}')

    # tags: always present, but sometimes wrong type
    tags_val = almost_tags(draw)
    fields.append(f'"tags": {tags_val}')

    # child: sometimes omitted
    child_val = almost_child(draw, depth)
    if child_val is not None:
        fields.append(f'"child": {child_val}')

    return "{" + ", ".join(fields) + "}"

@st.composite
def generated_json(draw) -> bytes:
    # Top-level record
    json_str = generated_record(draw)
    return json_str.encode("utf-8")