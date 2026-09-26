from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status enum
    statuses = ["active", "inactive", "unknown"]

    # Helper to produce a JSON string literal with proper escaping of quotes and backslashes
    def json_string(s: str) -> str:
        # Minimal escaping for " and \ for JSON string literals
        # Hypothesis strings are unicode, but we keep it simple here
        s = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{s}"'

    # Recursive record generator with bounded depth (max 1 level of recursion)
    def record(depth=0):
        # id: integer
        id_val = draw(st.integers(min_value=-(2**31), max_value=2**31-1))
        id_json = str(id_val)

        # amount: string (valid JSON string)
        # To induce divergence, sometimes produce numeric strings, sometimes empty, sometimes with spaces
        amount_val = draw(
            st.one_of(
                st.text(min_size=1, max_size=10).filter(lambda x: '"' not in x and '\\' not in x),
                st.integers(min_value=0, max_value=999999).map(str),
                st.just("0"),
                st.just(""),
                st.just(" 123 "),  # spaces inside string
            )
        )
        amount_json = json_string(amount_val)

        # name: string or null
        # To induce divergence, sometimes produce null, sometimes empty string, sometimes string with unicode
        name_val = draw(
            st.one_of(
                st.none(),
                st.text(min_size=0, max_size=20).filter(lambda x: '"' not in x and '\\' not in x),
                st.just(""),
                st.just("null"),  # string "null" to confuse null vs string
            )
        )
        if name_val is None:
            name_json = "null"
        else:
            name_json = json_string(name_val)

        # status: one of "active", "inactive", "unknown"
        # To induce divergence, sometimes produce a wrong enum string (like "Active" capitalized)
        status_val = draw(
            st.one_of(
                st.sampled_from(statuses),
                st.sampled_from([s.capitalize() for s in statuses]),  # capitalized variants
                st.just(""),  # empty string
                st.just("unknown "),  # trailing space
            )
        )
        status_json = json_string(status_val)

        # tags: array of strings (possibly empty)
        # To induce divergence, sometimes produce empty array, sometimes array with empty string, sometimes array with null inside (should be invalid)
        tags_list = draw(
            st.one_of(
                st.lists(
                    st.text(min_size=0, max_size=10).filter(lambda x: '"' not in x and '\\' not in x),
                    min_size=0,
                    max_size=3,
                ),
                st.lists(st.none(), min_size=0, max_size=2),  # null inside array (invalid)
                st.just([]),
                st.just([""]),  # array with empty string
            )
        )
        # Build tags JSON array string
        def tag_json(t):
            if t is None:
                return "null"
            else:
                return json_string(t)

        tags_json = "[" + ",".join(tag_json(t) for t in tags_list) + "]"

        # child: Record or null
        # Only recurse if depth == 0 (one level of recursion)
        if depth == 0:
            child_val = draw(
                st.one_of(
                    st.none(),
                    st.just("null"),
                    record(depth=1),
                )
            )
            if child_val == "null" or child_val is None:
                child_json = "null"
            else:
                child_json = child_val
        else:
            # depth == 1, no further recursion
            child_json = "null"

        # Compose JSON object string
        # Intentionally vary field order sometimes to see if any implementation is sensitive (should not be)
        fields = [
            ('"id"', id_json),
            ('"amount"', amount_json),
            ('"name"', name_json),
            ('"status"', status_json),
            ('"tags"', tags_json),
            ('"child"', child_json),
        ]

        # Shuffle fields order sometimes to induce subtle differences
        if draw(st.booleans()):
            fields = fields
        else:
            fields = list(reversed(fields))

        json_obj = "{" + ",".join(f"{k}:{v}" for k, v in fields) + "}"
        return json_obj

    # Draw the top-level record JSON string
    json_str = record(depth=0)

    # Return as bytes
    return json_str.encode("utf-8")