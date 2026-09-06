from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for the "status" enum
    statuses = ["active", "inactive", "unknown"]

    # Recursive strategy for "child" field, bounded to 1 level of recursion
    # child can be null or a Record (one level only)
    # To avoid infinite recursion, we pass a parameter depth=0 and only recurse once
    def record(depth=0):
        # id: integer (any int in a reasonable range)
        id_val = draw(st.integers(min_value=0, max_value=2**31-1))
        # amount: string (decimal-ish, but we allow some edge cases)
        # To provoke divergence, sometimes use numeric strings with leading zeros, or empty string
        amount_val = draw(
            st.one_of(
                st.text(min_size=1, max_size=10).filter(lambda s: all(c in "0123456789." for c in s)),
                st.just("0"),
                st.just(""),
                st.just("000123.4500"),
                st.just("123"),
                st.just("0.0"),
            )
        )
        # name: string or null
        # To provoke divergence, sometimes use empty string, unicode, or null
        name_val = draw(st.one_of(st.none(), st.text(min_size=0, max_size=20)))
        # status: one of the three strings, but sometimes inject wrong casing or whitespace to provoke divergence
        status_val = draw(
            st.one_of(
                st.sampled_from(statuses),
                st.sampled_from([s.upper() for s in statuses]),
                st.sampled_from([s.capitalize() for s in statuses]),
                st.sampled_from([s + " " for s in statuses]),
                st.sampled_from(["active", "inactive", "unknown", "Active", "Inactive", "Unknown", " active"]),
            )
        )
        # tags: array of strings, sometimes empty, sometimes with empty strings, sometimes with unicode or spaces
        tags_val = draw(
            st.lists(
                st.one_of(
                    st.text(min_size=0, max_size=10),
                    st.just(""),
                    st.just(" "),
                    st.just("tag"),
                    st.just("TAG"),
                    st.just("täg"),
                ),
                min_size=0,
                max_size=5,
            )
        )
        # child: null or one level record (depth limited)
        if depth == 0:
            child_val = draw(st.one_of(st.none(), record(depth=1)))
        else:
            child_val = None

        # Now build JSON text for this record
        # We must produce syntactically valid JSON text, so:
        # - strings quoted with double quotes, with proper escaping of backslash and double quote
        # - null as literal null
        # - arrays as [ ... ]
        # - integers as digits
        # - enums as strings (quoted)
        # We do not import json, so we must escape strings ourselves minimally

        def json_escape(s: str) -> str:
            # Minimal JSON string escaping: backslash and double quote
            # Also escape control chars \b \f \n \r \t for safety
            # Hypothesis strings may contain any unicode, but we keep it simple
            s = s.replace("\\", "\\\\").replace('"', '\\"')
            s = s.replace("\b", "\\b").replace("\f", "\\f").replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
            return s

        def json_string_or_null(v):
            if v is None:
                return "null"
            else:
                return '"' + json_escape(v) + '"'

        def json_array_of_strings(arr):
            # arr is list of strings
            return "[" + ",".join(json_string_or_null(s) for s in arr) + "]"

        # Compose child JSON text
        if child_val is None:
            child_json = "null"
        else:
            child_json = child_val

        # Compose the JSON object text
        # We deliberately vary field order sometimes to provoke divergence
        # But to keep it simple, keep fixed order here

        # Compose fields as strings
        id_json = str(id_val)
        amount_json = json_string_or_null(amount_val)
        name_json = json_string_or_null(name_val)
        status_json = json_string_or_null(status_val)
        tags_json = json_array_of_strings(tags_val)
        child_json_text = child_json if isinstance(child_json, str) else child_json

        json_obj = (
            '{'
            + '"id":' + id_json + ','
            + '"amount":' + amount_json + ','
            + '"name":' + name_json + ','
            + '"status":' + status_json + ','
            + '"tags":' + tags_json + ','
            + '"child":' + child_json_text
            + '}'
        )
        return json_obj

    # Draw the top-level record JSON text
    top_json = record(depth=0)

    # Return bytes of the JSON text (UTF-8)
    return top_json.encode("utf-8")