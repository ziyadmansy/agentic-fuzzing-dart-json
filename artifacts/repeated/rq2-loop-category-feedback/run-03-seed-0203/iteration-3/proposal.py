from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants
    statuses = ["active", "inactive", "unknown"]

    # Helper: produce a JSON string literal from a Python string
    # (only escape backslash and double quote for simplicity)
    def json_string(s: str) -> str:
        return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

    # Helper: produce JSON array of strings
    def json_array_of_strings(lst):
        return "[" + ",".join(json_string(x) for x in lst) + "]"

    # Recursive record generator with bounded depth (max 1 level of recursion)
    def record(depth=0):
        # id: integer, but sometimes a string to provoke divergence
        # Mostly int, sometimes stringified int, sometimes float as string
        id_val = draw(st.one_of(
            st.integers(min_value=0, max_value=1000).map(str),
            st.text(min_size=1, max_size=5).filter(lambda s: not s.isdigit()),  # invalid string
            st.integers(min_value=0, max_value=1000).map(str),
        ))

        # amount: string, but sometimes a number (int or float) to provoke divergence
        amount_val = draw(st.one_of(
            st.text(min_size=0, max_size=10),  # arbitrary string
            st.integers(min_value=0, max_value=10000).map(str),
            st.floats(allow_nan=False, allow_infinity=False).map(lambda f: format(f, '.6g')),
            st.integers(min_value=0, max_value=10000),  # number instead of string
        ))

        # name: string or null, sometimes number or boolean to provoke divergence
        name_val = draw(st.one_of(
            st.none().map(lambda _: "null"),
            st.text(min_size=0, max_size=10).map(json_string),
            st.integers(min_value=0, max_value=1000).map(str),  # number as string
            st.booleans().map(lambda b: "true" if b else "false"),  # boolean as string
            st.integers(min_value=0, max_value=1000).map(str),  # number without quotes (invalid)
        ))

        # status: one of the three strings, sometimes null or invalid string
        status_val = draw(st.one_of(
            st.sampled_from(statuses).map(json_string),
            st.none().map(lambda _: "null"),
            st.text(min_size=1, max_size=7).filter(lambda s: s not in statuses).map(json_string),
        ))

        # tags: array of strings, sometimes array of numbers or empty array
        tags_list = draw(st.one_of(
            st.lists(st.text(min_size=0, max_size=5), max_size=5).map(json_array_of_strings),
            st.lists(st.integers(min_value=0, max_value=1000).map(str), max_size=5).map(
                lambda lst: "[" + ",".join(lst) + "]"
            ),
            st.just("[]"),
        ))

        # child: null or a record (one level recursion max)
        if depth == 0:
            child_val = draw(st.one_of(
                st.just("null"),
                record(depth=1),
                # sometimes invalid types to provoke divergence
                st.integers(min_value=0, max_value=1000).map(str),
                st.text(min_size=0, max_size=10).map(json_string),
            ))
        else:
            child_val = "null"

        # Compose JSON object text with some fields possibly invalid types (unquoted numbers, booleans)
        # We deliberately produce some fields as unquoted numbers or booleans to provoke divergence.
        # We do not quote id_val if it looks like a number, else quote it.
        def maybe_quote_id(s):
            # If s is digits only, output as number (no quotes)
            if s.isdigit():
                return s
            # else quote it
            return json_string(s)

        # amount_val can be string or number, if string quote it, else output raw
        def maybe_quote_amount(val):
            # If val is str and looks like a number, output raw else quoted
            if isinstance(val, str):
                try:
                    float(val)
                    # looks like number, output raw
                    return val
                except Exception:
                    return json_string(val)
            else:
                # number, output raw
                return str(val)

        # name_val is already a JSON fragment (string literal, "null", or unquoted number/boolean)
        # status_val is already a JSON fragment (string literal or "null")

        json_obj = (
            "{" +
            f'"id":{maybe_quote_id(id_val)},' +
            f'"amount":{maybe_quote_amount(amount_val)},' +
            f'"name":{name_val},' +
            f'"status":{status_val},' +
            f'"tags":{tags_list},' +
            f'"child":{child_val}' +
            "}"
        )
        return json_obj

    # Draw a record at top level
    json_text = record(depth=0)

    # Return bytes
    return json_text.encode("utf-8")