from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status enum
    statuses = ["active", "inactive", "unknown"]

    # Helper: produce a JSON string literal from a Python string (with minimal escaping)
    def json_string(s: str) -> str:
        # Escape backslash and double quote and control chars minimally
        # Hypothesis strings are unicode, so also escape control chars <0x20
        def escape_char(c):
            o = ord(c)
            if c == '"':
                return r'\"'
            elif c == '\\':
                return r'\\'
            elif o < 0x20:
                # Use \u00XX escape
                return '\\u%04x' % o
            else:
                return c
        return '"' + ''.join(escape_char(c) for c in s) + '"'

    # Compose a JSON array of strings
    def json_array_of_strings(lst):
        return '[' + ','.join(json_string(s) for s in lst) + ']'

    # Compose a JSON object from a dict of field_name -> json_text
    def json_object(d):
        # d keys are strings, values are strings representing JSON values
        items = []
        for k, v in d.items():
            items.append(json_string(k) + ':' + v)
        return '{' + ','.join(items) + '}'

    # Recursive strategy for the "child" field, bounded to depth 1 (one level of recursion)
    # To induce divergences, we vary presence, null, and type of fields slightly.
    # We produce a JSON text string representing a Record or null.

    # We will produce a dict of fields as strings (JSON text) for the record,
    # then serialize to JSON text.

    # To induce divergences, we vary:
    # - "id": normally integer, but sometimes string or float or missing (missing counts as malformed)
    # - "amount": normally string, but sometimes number or null or missing
    # - "name": string or null, but sometimes number or missing
    # - "status": one of enum strings, but sometimes invalid string or number or missing
    # - "tags": array of strings, but sometimes array of numbers or empty array or missing
    # - "child": null or nested record or missing or wrong type (string or number)

    # We vary at most one or two fields per record to keep it "almost well-formed".

    # Strategy for "id" field value (as JSON text)
    id_strategy = st.one_of(
        st.integers(min_value=0, max_value=2**31-1).map(str),  # valid integer as JSON number text
        st.text(min_size=1, max_size=5).map(json_string),      # invalid string instead of int
        st.floats(allow_nan=False, allow_infinity=False).map(lambda f: repr(f)),  # float number text
    )

    # Strategy for "amount" field value (normally string)
    amount_strategy = st.one_of(
        st.text(min_size=1, max_size=10).map(json_string),  # valid string
        st.integers(min_value=0, max_value=10000).map(str), # number instead of string
        st.just("null"),                                    # null instead of string
    )

    # Strategy for "name" field value (string or null normally)
    name_strategy = st.one_of(
        st.text(min_size=0, max_size=10).map(json_string),  # string
        st.just("null"),                                    # null
        st.integers(min_value=0, max_value=100).map(str),  # number instead of string/null
    )

    # Strategy for "status" field value (enum string normally)
    status_strategy = st.one_of(
        st.sampled_from(statuses).map(json_string),        # valid enum string
        st.text(min_size=1, max_size=7).filter(lambda s: s not in statuses).map(json_string),  # invalid string
        st.integers(min_value=0, max_value=2).map(str),    # number instead of string
    )

    # Strategy for "tags" field value (array of strings normally)
    tags_strategy = st.one_of(
        st.lists(st.text(min_size=1, max_size=5), min_size=0, max_size=5).map(json_array_of_strings),  # valid array of strings
        st.lists(st.integers(min_value=0, max_value=10), min_size=0, max_size=5).map(lambda lst: '[' + ','.join(str(i) for i in lst) + ']'),  # array of numbers instead of strings
        st.just("null"),  # null instead of array
    )

    # Forward declaration for child record (to allow recursion)
    # We limit recursion depth to 1: child can be null or a record with child=null only
    # To do this, we define a helper function with depth parameter

    def record_strategy(depth):
        # If depth == 0, child must be null or missing (we always include child field, but can vary type)
        # We vary one or two fields per record to induce divergences

        # Draw which fields to "corrupt" (0, 1 or 2 fields)
        corrupt_fields = draw(st.lists(st.sampled_from(["id","amount","name","status","tags","child"]), max_size=2, unique=True))

        # id field
        if "id" in corrupt_fields:
            id_val = draw(id_strategy)
        else:
            id_val = str(draw(st.integers(min_value=0, max_value=2**31-1)))

        # amount field
        if "amount" in corrupt_fields:
            amount_val = draw(amount_strategy)
        else:
            amount_val = json_string(draw(st.text(min_size=1, max_size=10)))

        # name field
        if "name" in corrupt_fields:
            name_val = draw(name_strategy)
        else:
            # string or null normally
            name_val = draw(st.one_of(st.just("null"), st.text(min_size=0, max_size=10).map(json_string)))

        # status field
        if "status" in corrupt_fields:
            status_val = draw(status_strategy)
        else:
            status_val = json_string(draw(st.sampled_from(statuses)))

        # tags field
        if "tags" in corrupt_fields:
            tags_val = draw(tags_strategy)
        else:
            tags_val = json_array_of_strings(draw(st.lists(st.text(min_size=1, max_size=5), min_size=0, max_size=5)))

        # child field
        if depth == 0:
            # no recursion, child must be null or corrupted
            if "child" in corrupt_fields:
                # corrupt child: string, number, or missing (we always include child, so no missing)
                child_val = draw(st.one_of(
                    st.just("null"),
                    st.text(min_size=1, max_size=5).map(json_string),
                    st.integers(min_value=0, max_value=10).map(str),
                ))
            else:
                child_val = "null"
        else:
            if "child" in corrupt_fields:
                # corrupt child: string, number, or null or nested record with corrupted fields
                child_val = draw(st.one_of(
                    st.just("null"),
                    st.text(min_size=1, max_size=5).map(json_string),
                    st.integers(min_value=0, max_value=10).map(str),
                    record_strategy(depth - 1),
                ))
            else:
                # normal nested record with depth-1
                child_val = draw(record_strategy(depth - 1))

        obj = {
            "id": id_val,
            "amount": amount_val,
            "name": name_val,
            "status": status_val,
            "tags": tags_val,
            "child": child_val,
        }
        return json_object(obj)

    # Draw top-level record with depth=1 recursion allowed
    json_text = draw(record_strategy(depth=1))

    # Return bytes
    return json_text.encode("utf-8")