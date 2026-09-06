from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic atomic fields
    id_str = draw(st.integers(min_value=0, max_value=2**31-1).map(str))
    # amount: string, but vary content to include numeric strings, empty, or weird formats
    amount_str = draw(st.one_of(
        st.decimals(min_value=0, max_value=1e9, allow_infinity=False, allow_nan=False).map(str),
        st.just(""),
        st.text(min_size=1, max_size=5).filter(lambda s: all(c.isprintable() and c not in '"\\' for c in s))
    ))
    # name: string or null, string can be empty or contain unicode
    name_val = draw(st.one_of(
        st.none(),
        st.text(min_size=0, max_size=10).filter(lambda s: all(c not in '"\\' for c in s))
    ))
    # status: one of the three strings, but sometimes uppercase or mixed case to test strict enum parsing
    status_val = draw(st.one_of(
        st.sampled_from(["active", "inactive", "unknown"]),
        st.sampled_from(["Active", "Inactive", "Unknown"]),
        st.sampled_from(["ACTIVE", "INACTIVE", "UNKNOWN"]),
    ))
    # tags: array of strings, empty or with elements, strings can be empty or contain spaces
    tags_list = draw(st.lists(
        st.text(min_size=0, max_size=8).filter(lambda s: all(c not in '"\\' for c in s)),
        max_size=5
    ))
    
    # Recursive child: either null or a nested record (one level only)
    def gen_child(level=0):
        if level > 0:
            # only one level deep recursion allowed
            return st.just("null")
        else:
            return st.one_of(
                st.just("null"),
                generated_json_child(level + 1)
            )
    
    @st.composite
    def generated_json_child(draw, level=1):
        id_c = draw(st.integers(min_value=0, max_value=2**31-1).map(str))
        amount_c = draw(st.one_of(
            st.decimals(min_value=0, max_value=1e9, allow_infinity=False, allow_nan=False).map(str),
            st.just(""),
            st.text(min_size=1, max_size=5).filter(lambda s: all(c.isprintable() and c not in '"\\' for c in s))
        ))
        name_c = draw(st.one_of(
            st.none(),
            st.text(min_size=0, max_size=10).filter(lambda s: all(c not in '"\\' for c in s))
        ))
        status_c = draw(st.one_of(
            st.sampled_from(["active", "inactive", "unknown"]),
            st.sampled_from(["Active", "Inactive", "Unknown"]),
            st.sampled_from(["ACTIVE", "INACTIVE", "UNKNOWN"]),
        ))
        tags_c = draw(st.lists(
            st.text(min_size=0, max_size=8).filter(lambda s: all(c not in '"\\' for c in s)),
            max_size=5
        ))
        child_c = "null"  # no further recursion
        
        # Compose JSON text for child record
        parts = [
            '"id":', id_c,
            ',"amount":"', amount_c, '"',
            ',"name":', 'null' if name_c is None else ('"' + name_c + '"'),
            ',"status":"', status_c, '"',
            ',"tags":[', ','.join('"' + t + '"' for t in tags_c), ']',
            ',"child":', child_c
        ]
        return "{" + "".join(parts) + "}"
    
    child_val = draw(gen_child())
    
    # Compose top-level JSON text
    parts = [
        '{',
        '"id":', id_str,
        ',"amount":"', amount_str, '"',
        ',"name":', 'null' if name_val is None else ('"' + name_val + '"'),
        ',"status":"', status_val, '"',
        ',"tags":[', ','.join('"' + t + '"' for t in tags_list), ']',
        ',"child":', child_val,
        '}'
    ]
    json_text = "".join(parts)
    return json_text.encode("utf-8")