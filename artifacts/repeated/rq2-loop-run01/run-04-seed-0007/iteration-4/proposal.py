from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic atomic fields with mostly correct types, but allow subtle deviations
    # to trigger divergences between deserializers.
    #
    # id: normally integer, but allow string digits or floats that look like ints
    id_val = draw(
        st.one_of(
            st.integers(min_value=0, max_value=1000),
            st.text(min_size=1, max_size=5).filter(lambda s: s.isdigit()),  # string digits
            st.floats(min_value=0, max_value=1000, allow_nan=False, allow_infinity=False)
            .map(lambda f: int(f) if f.is_integer() else f),  # floats that might be int-like or not
        )
    )
    # amount: normally string representing decimal, allow numeric types or weird strings
    amount_val = draw(
        st.one_of(
            st.text(min_size=1, max_size=10).filter(lambda s: all(c in "0123456789." for c in s)),
            st.floats(min_value=0, max_value=10000, allow_nan=False, allow_infinity=False).map(lambda f: f if f >= 0 else abs(f)),
            st.integers(min_value=0, max_value=10000),
        )
    )
    # name: string or null, allow also empty string, or integer to test type confusion
    name_val = draw(
        st.one_of(
            st.none(),
            st.text(min_size=0, max_size=20),
            st.integers(min_value=0, max_value=100),
        )
    )
    # status: one of "active", "inactive", "unknown" normally, but allow case variants or wrong strings
    status_val = draw(
        st.one_of(
            st.sampled_from(["active", "inactive", "unknown"]),
            st.sampled_from(["Active", "INACTIVE", "Unknown", "pending", ""]),
        )
    )
    # tags: array of strings normally, allow empty array, array with null, or array with integers
    tags_val = draw(
        st.lists(
            st.one_of(
                st.text(min_size=1, max_size=10),
                st.none(),
                st.integers(min_value=0, max_value=10),
            ),
            max_size=5,
        )
    )

    # child: either null or a nested record (one level recursion)
    # To avoid infinite recursion, limit depth to 1.
    # For child, we produce a similar record but with no further child (child=null).
    # Also allow child to be null or malformed (e.g. missing fields, or wrong types)
    def make_child():
        # child fields, but no further child recursion (child=null)
        child_id = draw(
            st.one_of(
                st.integers(min_value=0, max_value=1000),
                st.text(min_size=1, max_size=5).filter(lambda s: s.isdigit()),
            )
        )
        child_amount = draw(
            st.one_of(
                st.text(min_size=1, max_size=10).filter(lambda s: all(c in "0123456789." for c in s)),
                st.floats(min_value=0, max_value=10000, allow_nan=False, allow_infinity=False),
            )
        )
        child_name = draw(
            st.one_of(
                st.none(),
                st.text(min_size=0, max_size=20),
            )
        )
        child_status = draw(
            st.one_of(
                st.sampled_from(["active", "inactive", "unknown"]),
                st.sampled_from(["ACTIVE", "Inactive", "unknown", ""]),
            )
        )
        child_tags = draw(
            st.lists(
                st.text(min_size=1, max_size=10),
                max_size=3,
            )
        )
        # child child is always null to limit recursion
        child_child = "null"

        # Compose child JSON object text
        child_json = (
            '{"id":' + (str(child_id) if isinstance(child_id, int) else '"' + child_id + '"') +
            ',"amount":' + (('"' + str(child_amount) + '"') if isinstance(child_amount, str) else ('"' + str(child_amount) + '"')) +
            ',"name":' + ("null" if child_name is None else ('"' + child_name + '"')) +
            ',"status":' + ('"' + child_status + '"') +
            ',"tags":[' + ",".join('"' + t + '"' for t in child_tags) + ']' +
            ',"child":' + child_child +
            '}'
        )
        return child_json

    child_present = draw(st.booleans())
    if child_present:
        child_val = make_child()
    else:
        child_val = "null"

    # Compose top-level JSON object text
    # id: if int, output as number; if string digits, output as string; if float, output as number
    if isinstance(id_val, int):
        id_text = str(id_val)
    elif isinstance(id_val, float):
        # floats output as number with decimal point
        id_text = repr(id_val)
    else:
        # string digits
        id_text = '"' + id_val + '"'

    # amount: if string, output as string; if int or float, output as number or string (try both)
    if isinstance(amount_val, str):
        amount_text = '"' + amount_val + '"'
    elif isinstance(amount_val, int):
        # sometimes output as string, sometimes as number to trigger divergence
        if draw(st.booleans()):
            amount_text = str(amount_val)
        else:
            amount_text = '"' + str(amount_val) + '"'
    else:
        # float
        amount_text = repr(amount_val)

    # name: null or string or int (output int as number)
    if name_val is None:
        name_text = "null"
    elif isinstance(name_val, int):
        name_text = str(name_val)
    else:
        name_text = '"' + name_val + '"'

    # status: output as string always
    status_text = '"' + status_val + '"'

    # tags: array of strings, nulls, ints
    tags_items = []
    for t in tags_val:
        if t is None:
            tags_items.append("null")
        elif isinstance(t, int):
            tags_items.append(str(t))
        else:
            tags_items.append('"' + t + '"')
    tags_text = "[" + ",".join(tags_items) + "]"

    json_text = (
        '{"id":' + id_text +
        ',"amount":' + amount_text +
        ',"name":' + name_text +
        ',"status":' + status_text +
        ',"tags":' + tags_text +
        ',"child":' + child_val +
        '}'
    )

    return json_text.encode("utf-8")