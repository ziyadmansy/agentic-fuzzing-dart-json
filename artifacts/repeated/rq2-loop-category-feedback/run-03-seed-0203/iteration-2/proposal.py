from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for enum values
    statuses = ["active", "inactive", "unknown"]

    # Helper: generate a JSON string literal with proper escaping of quotes and backslashes
    def json_string(s: str) -> str:
        # Minimal escaping for " and \ to keep JSON valid
        # Hypothesis strings can contain any unicode, but we keep it simple here
        s = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{s}"'

    # Recursive record generator with bounded depth (max 1 level of recursion)
    def gen_record(depth=0):
        # id: integer
        id_val = draw(st.integers(min_value=0, max_value=2**31-1))
        # amount: string, but try some edge cases (empty, numeric strings, large numbers)
        amount_val = draw(
            st.one_of(
                st.text(min_size=0, max_size=10),
                st.integers(min_value=0, max_value=10**10).map(str),
                st.just("0"),
                st.just(""),
                st.just("000123"),
                st.just("-123.45"),
                st.just("1e10"),
            )
        )
        # name: string or null, try empty string, unicode, or null
        name_val = draw(st.one_of(st.none(), st.text(min_size=0, max_size=20)))

        # status: one of the three strings, but also try to break by inserting wrong casing or whitespace sometimes
        status_val = draw(
            st.one_of(
                st.sampled_from(statuses),
                st.sampled_from([s.upper() for s in statuses]),
                st.sampled_from([s.capitalize() for s in statuses]),
                st.sampled_from([s + " " for s in statuses]),
                st.sampled_from(["active", "inactive", "unknown", "Active", "Inactive", "Unknown", " active", "inactive "]),
            )
        )

        # tags: array of strings, try empty array, array with empty string, or strings with commas/quotes
        tags_len = draw(st.integers(min_value=0, max_value=3))
        tags_vals = []
        for _ in range(tags_len):
            tag = draw(
                st.one_of(
                    st.text(min_size=0, max_size=10),
                    st.just(""),
                    st.just("tag,with,commas"),
                    st.just('tag"quote'),
                    st.just("tag\\backslash"),
                )
            )
            tags_vals.append(tag)

        # child: null or a record (one level recursion max)
        if depth == 0:
            child_val = draw(st.one_of(st.none(), gen_record(depth=1)))
        else:
            child_val = None

        # Build JSON text for this record
        # Compose fields in order: id, amount, name, status, tags, child
        parts = []

        # id: integer
        parts.append(f'"id":{id_val}')

        # amount: string
        parts.append(f'"amount":{json_string(amount_val)}')

        # name: string or null
        if name_val is None:
            parts.append(f'"name":null')
        else:
            parts.append(f'"name":{json_string(name_val)}')

        # status: string (possibly invalid casing or whitespace)
        parts.append(f'"status":{json_string(status_val)}')

        # tags: array of strings
        tags_json = "[" + ",".join(json_string(t) for t in tags_vals) + "]"
        parts.append(f'"tags":{tags_json}')

        # child: null or nested record
        if child_val is None:
            parts.append(f'"child":null')
        else:
            parts.append(f'"child":{child_val}')

        json_obj = "{" + ",".join(parts) + "}"
        return json_obj

    # Draw the top-level record JSON string
    json_text = draw(gen_record(depth=0))
    return json_text.encode("utf-8")