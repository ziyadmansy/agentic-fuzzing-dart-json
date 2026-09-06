from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status enum
    statuses = ["active", "inactive", "unknown"]

    # Helper: produce a JSON string literal with proper escaping of quotes and backslashes
    def json_string(s: str) -> str:
        # minimal escaping for " and \ to keep JSON valid
        # Hypothesis strings can contain any Unicode, but we keep it simple
        s = s.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{s}"'

    # Helper: produce JSON array of strings
    def json_string_array():
        # array of 0 to 3 strings, each string is simple ascii printable chars
        return st.lists(
            st.text(
                alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E).filter(lambda c: c not in ['"', '\\']),
                min_size=0,
                max_size=8,
            ),
            min_size=0,
            max_size=3,
        ).map(lambda arr: "[" + ",".join(json_string(s) for s in arr) + "]")

    # Recursive record generator with bounded depth (max 1 level of recursion)
    def record(depth=0):
        # id: integer, but try also some edge cases as strings or floats to provoke divergence
        # but mostly integer or integer-like strings
        id_val = draw(
            st.one_of(
                st.integers(min_value=0, max_value=1000),
                st.text(min_size=1, max_size=3).filter(lambda s: s.isdigit()),  # numeric string
                st.floats(min_value=0, max_value=1000).map(lambda f: f if f.is_integer() else f),  # floats (some integer)
            )
        )
        # amount: string, but try numeric strings, empty string, or strings with spaces
        amount_val = draw(
            st.one_of(
                st.text(min_size=0, max_size=5).filter(lambda s: all(c not in s for c in ['"', '\\'])),
                st.integers(min_value=0, max_value=1000).map(str),
                st.floats(min_value=0, max_value=1000).map(lambda f: f"{f:.2f}"),
            )
        )

        # name: string or null, but also try empty string, or number as string, or null
        name_val = draw(
            st.one_of(
                st.none(),
                st.text(min_size=0, max_size=10).filter(lambda s: all(c not in s for c in ['"', '\\'])),
                st.integers(min_value=0, max_value=100).map(str),
            )
        )

        # status: one of the three valid strings, but also try invalid strings or null to provoke divergence
        status_val = draw(
            st.one_of(
                st.sampled_from(statuses),
                st.text(min_size=1, max_size=7).filter(lambda s: s not in statuses),
                st.none(),
            )
        )

        # tags: array of strings, but also try null or array with non-string elements (encoded as strings)
        tags_val = draw(
            st.one_of(
                json_string_array(),
                st.just("null"),
                # array with one integer element encoded as string (to provoke divergence)
                st.just('[123]'),
                # array with mixed types encoded as string
                st.just('["tag1", 42]'),
            )
        )

        # child: either null or a nested record (only one level deep)
        if depth == 0:
            child_val = draw(
                st.one_of(
                    st.just("null"),
                    record(depth=1),
                )
            )
        else:
            # at depth 1, child must be null (no deeper recursion)
            child_val = st.just("null").example()

        # Build JSON object string with fields in fixed order
        # id: if int or float, emit as number; if string, emit as JSON string
        if isinstance(id_val, int):
            id_json = str(id_val)
        elif isinstance(id_val, float):
            # emit float with minimal decimals
            id_json = str(id_val) if id_val % 1 else str(int(id_val))
        else:
            # string
            id_json = json_string(id_val)

        # amount always string
        amount_json = json_string(str(amount_val))

        # name: null or string
        if name_val is None:
            name_json = "null"
        else:
            name_json = json_string(str(name_val))

        # status: null or string
        if status_val is None:
            status_json = "null"
        else:
            status_json = json_string(str(status_val))

        # tags: already JSON array string or "null" or malformed array string
        tags_json = tags_val

        # child: already JSON object string or "null"
        child_json = child_val

        json_obj = (
            "{" +
            f'"id":{id_json},'
            f'"amount":{amount_json},'
            f'"name":{name_json},'
            f'"status":{status_json},'
            f'"tags":{tags_json},'
            f'"child":{child_json}'
            "}"
        )
        return json_obj.encode("utf-8")

    return draw(record())