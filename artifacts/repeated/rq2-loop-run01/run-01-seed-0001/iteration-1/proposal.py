from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status values
    statuses = ['"active"', '"inactive"', '"unknown"']

    # Helper to produce a JSON string literal with possible edge cases
    def json_string():
        # Include null as a string "null" or actual null (to cause divergence)
        # But schema says name can be string or null, so we handle that separately
        # Here for general strings, produce strings with escapes, unicode, empty, etc.
        # We'll produce strings with quotes escaped, unicode escapes, control chars
        # to trigger subtle parsing differences.
        # Use st.text with a restricted alphabet including escapes.
        # But we cannot import json to escape, so we do minimal escaping manually.
        # We'll produce strings without quotes or backslashes to avoid invalid JSON.
        # Instead, produce strings with allowed chars and some tricky unicode.
        # We'll produce strings that may contain \u escapes as raw text to test parsers.
        # But since we cannot produce raw \u escapes easily, produce normal unicode chars.

        # We'll produce strings that may contain control chars (like \b, \f, \n, \r, \t)
        # encoded as actual chars, which JSON allows escaped only.
        # This can cause divergence if some parsers accept raw control chars in strings.

        # To keep it simple and safe, produce strings with:
        # - ASCII printable except quotes and backslash
        # - some unicode chars > 0x7F
        # - empty string allowed
        # - strings "null", "true", "false" to test confusion with literals

        # We'll produce strings from a custom alphabet excluding " and \ to keep valid JSON.
        alphabet = (
            "abcdefghijklmnopqrstuvwxyz"
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            "0123456789"
            " !#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"
        )
        # Remove " and \ from alphabet to avoid breaking JSON string syntax
        alphabet = alphabet.replace('"', '').replace('\\', '')

        # Draw string length 0 to 20
        s = draw(st.text(alphabet, min_size=0, max_size=20))
        # Occasionally produce special strings that look like JSON literals
        special = draw(st.booleans())
        if special:
            s = draw(st.sampled_from(["null", "true", "false", "NaN", "Infinity", "-Infinity"]))
        return '"' + s + '"'

    # Helper to produce a JSON null literal or a string "null" (for name and child)
    def json_null_or_string():
        # For "name" field: string or null
        # We'll produce either null literal or a string (including "null" string)
        is_null = draw(st.booleans())
        if is_null:
            return "null"
        else:
            return json_string()

    # Helper to produce the "status" field value as JSON string literal
    def json_status():
        # To cause divergence, sometimes produce uppercase or mixed case status strings
        # even though schema says lowercase only.
        # Some parsers may accept, some may reject or decode differently.
        base = draw(st.sampled_from(["active", "inactive", "unknown"]))
        # Randomly uppercase some letters
        def random_case(s):
            return ''.join(draw(st.sampled_from([c.lower(), c.upper()])) for c in s)
        s = random_case(base)
        return '"' + s + '"'

    # Helper to produce "amount" field as a string representing a number or weird strings
    def json_amount():
        # amount is a string, but we can produce numeric strings, empty, or weird strings
        # to test divergence.
        # Also produce strings that look like numbers but with leading zeros, signs, decimals.
        choice = draw(st.integers(min_value=0, max_value=4))
        if choice == 0:
            # Normal decimal integer string
            n = draw(st.integers(min_value=0, max_value=10**9))
            return '"' + str(n) + '"'
        elif choice == 1:
            # Decimal with leading zeros
            n = draw(st.integers(min_value=0, max_value=999999))
            s = str(n).rjust(draw(st.integers(1,5)), '0')
            return '"' + s + '"'
        elif choice == 2:
            # Floating point string
            f = draw(st.floats(allow_nan=False, allow_infinity=False, width=32))
            # Format with repr to get decimal notation
            s = repr(f)
            return '"' + s + '"'
        elif choice == 3:
            # Empty string
            return '""'
        else:
            # Non-numeric string
            return json_string()

    # Helper to produce "tags" array of strings (possibly empty)
    def json_tags():
        # tags is array of strings
        # To cause divergence, produce empty array, array with nulls (invalid per schema),
        # or strings with tricky content.
        # But schema says always array of strings, so null elements are invalid.
        # We'll produce only strings, but sometimes empty strings or special strings.
        length = draw(st.integers(min_value=0, max_value=5))
        elements = []
        for _ in range(length):
            elements.append(json_string())
        return "[" + ",".join(elements) + "]"

    # Recursive helper to produce "child" field JSON value (null or nested record)
    # Limit recursion depth to 1 normally, but sometimes 0 or 1
    def json_record(depth):
        # depth 0 means no child (null)
        # depth 1 means child can be null or record with child=null
        # To cause divergence, sometimes produce child=null, sometimes child record
        # with fields that have tricky values.

        id_val = draw(st.integers(min_value=0, max_value=2**31-1))
        id_json = str(id_val)

        amount_json = json_amount()
        name_json = json_null_or_string()
        status_json = json_status()
        tags_json = json_tags()

        if depth <= 0:
            child_json = "null"
        else:
            # 50% chance null, 50% chance nested record with depth=0
            if draw(st.booleans()):
                child_json = "null"
            else:
                child_json = json_record(depth - 1)

        # Build JSON object string with fields in schema order
        # Intentionally vary whitespace and field order sometimes to test parsers
        # But JSON object field order is not significant, so no divergence expected
        # We'll keep order fixed to reduce noise.

        # Insert some spaces randomly around colons and commas
        def ws():
            return " " * draw(st.integers(0,2))

        json_obj = (
            "{" +
            ws() + '"id"' + ws() + ":" + ws() + id_json + "," +
            ws() + '"amount"' + ws() + ":" + ws() + amount_json + "," +
            ws() + '"name"' + ws() + ":" + ws() + name_json + "," +
            ws() + '"status"' + ws() + ":" + ws() + status_json + "," +
            ws() + '"tags"' + ws() + ":" + ws() + tags_json + "," +
            ws() + '"child"' + ws() + ":" + ws() + child_json +
            "}"
        )
        return json_obj

    # Top-level record with depth 1 recursion max
    json_text = json_record(depth=1)

    # Return bytes
    return json_text.encode("utf-8")