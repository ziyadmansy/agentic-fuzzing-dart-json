from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status enum
    statuses = ["active", "inactive", "unknown"]

    # To induce subtle divergences, we vary:
    # - "id" as integer or string integer (wrong type)
    # - "amount" as string numeric or numeric (wrong type)
    # - "name" as string, null, or missing (missing is not allowed, so we won't omit but can use null)
    # - "status" as correct enum string, or a close-but-invalid string (e.g. "Active", "inactiv", or number)
    # - "tags" as array of strings or array of mixed types or empty array
    # - "child" as null or a nested record (one level only), or a wrong type (e.g. string or number)
    # We produce syntactically valid JSON objects only.

    # Helper to produce a valid or subtly invalid "id"
    def id_strategy():
        # 80% int, 20% string int (wrong type)
        return st.one_of(
            st.integers(min_value=0, max_value=2**31 - 1),
            st.integers(min_value=0, max_value=2**31 - 1).map(str),
        )

    # Helper to produce "amount" as string numeric or number (wrong type)
    def amount_strategy():
        # 75% string numeric, 25% numeric (float or int)
        numeric_str = st.floats(min_value=0, max_value=1e6, allow_infinity=False, allow_nan=False).map(lambda f: f"{f:.2f}")
        numeric_num = st.floats(min_value=0, max_value=1e6, allow_infinity=False, allow_nan=False)
        return st.one_of(numeric_str, numeric_num)

    # Helper for "name" as string or null
    def name_strategy():
        # 90% string, 10% null
        return st.one_of(
            st.text(min_size=0, max_size=20),
            st.just(None),
        )

    # Helper for "status" as correct enum or close invalid
    def status_strategy():
        # 85% correct enum, 15% close invalid strings or wrong type
        invalid_statuses = ["Active", "inactiv", "unknown ", "0", "", None]
        return st.one_of(
            st.sampled_from(statuses),
            st.sampled_from(invalid_statuses),
            st.integers(min_value=0, max_value=2),
        )

    # Helper for "tags" as array of strings or mixed types
    def tags_strategy():
        # 80% array of strings, 20% array with some non-string elements
        strings = st.text(min_size=1, max_size=10)
        mixed = st.one_of(strings, st.integers(), st.none())
        # length 0 to 5
        return st.one_of(
            st.lists(strings, min_size=0, max_size=5),
            st.lists(mixed, min_size=0, max_size=5),
        )

    # Recursive helper for "child" record or null or wrong type
    # Limit recursion depth to 1 (only one level)
    def child_strategy(depth=0):
        if depth > 0:
            # At max depth, only null or wrong type (string or number)
            return st.one_of(
                st.just(None),
                st.text(min_size=1, max_size=10),
                st.integers(min_value=0, max_value=100),
            )
        else:
            # 70% null, 20% valid nested record, 10% wrong type
            def build_record():
                return record_strategy(depth=depth + 1)
            return st.one_of(
                st.just(None),
                build_record(),
                st.text(min_size=1, max_size=10),
            )

    # Compose the record as a dict with all fields present
    def record_strategy(depth=0):
        return st.fixed_dictionaries({
            "id": id_strategy(),
            "amount": amount_strategy(),
            "name": name_strategy(),
            "status": status_strategy(),
            "tags": tags_strategy(),
            "child": child_strategy(depth),
        })

    # Now we have a record dict with possible wrong types or invalid enum values.
    # We must serialize it to JSON text ourselves, carefully:
    # - integers and floats as numbers (no quotes)
    # - strings as JSON strings with quotes and escaped characters
    # - null as literal null
    # - arrays as JSON arrays
    # - nested record as JSON object recursively

    # JSON string escape helper (minimal, escapes backslash and quotes)
    def json_escape(s: str) -> str:
        # Replace backslash and quote with escaped versions
        s = s.replace("\\", "\\\\").replace("\"", "\\\"")
        # Also escape control chars (optional, but safer)
        # Replace control chars with \u00XX
        def esc_char(c):
            o = ord(c)
            if o < 0x20:
                return "\\u%04x" % o
            else:
                return c
        return "".join(esc_char(c) for c in s)

    # Serialize a Python value to JSON text according to our schema
    def serialize_json(val):
        if val is None:
            return "null"
        elif isinstance(val, bool):
            return "true" if val else "false"
        elif isinstance(val, int):
            return str(val)
        elif isinstance(val, float):
            # Use repr to preserve precision, but avoid inf/nan (should not appear)
            return repr(val)
        elif isinstance(val, str):
            return "\"" + json_escape(val) + "\""
        elif isinstance(val, list):
            return "[" + ",".join(serialize_json(x) for x in val) + "]"
        elif isinstance(val, dict):
            # keys are always strings
            items = []
            for k, v in val.items():
                items.append("\"" + json_escape(k) + "\":" + serialize_json(v))
            return "{" + ",".join(items) + "}"
        else:
            # fallback: treat as string
            return "\"" + json_escape(str(val)) + "\""

    # Draw a record dict
    record = draw(record_strategy())

    # Serialize to JSON text
    json_text = serialize_json(record)

    # Return bytes
    return json_text.encode("utf-8")