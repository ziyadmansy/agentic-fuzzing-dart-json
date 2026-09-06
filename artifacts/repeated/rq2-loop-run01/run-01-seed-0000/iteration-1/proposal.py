from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic primitives for fields
    id_strat = st.integers(min_value=-(2**31), max_value=2**31-1)
    # amount as string, but allow numeric strings, empty string, or weird numeric formats
    amount_strat = st.one_of(
        st.text(min_size=0, max_size=10),  # arbitrary string, possibly empty
        st.integers(min_value=-1000000, max_value=1000000).map(str),
        st.floats(allow_nan=False, allow_infinity=False).map(lambda f: format(f, 'g')),
    )
    # name: string or null, allow empty string, unicode, or null
    name_strat = st.one_of(st.none(), st.text(min_size=0, max_size=20))
    # status: one of the three strings exactly
    status_strat = st.sampled_from(["active", "inactive", "unknown"])
    # tags: array of strings, allow empty strings, unicode, duplicates, empty array
    tags_strat = st.lists(st.text(min_size=0, max_size=10), min_size=0, max_size=5)
    
    # Recursive record builder, bounded depth 2 (top + child)
    def record_strat(depth=0):
        if depth > 1:
            # At max depth, child is always null
            child_strat = st.just("null")
        else:
            # child is either null or a nested record (as JSON text)
            child_strat = st.one_of(st.just("null"), record_strat(depth + 1))
        
        # Compose fields as JSON text
        def build_record(id_, amount, name, status, tags, child_json):
            # JSON string escaper (minimal, only escape backslash and quotes)
            def jstr(s):
                # Escape backslash and double quotes and control chars minimally
                # Hypothesis text can contain any unicode, so escape control chars and quotes
                def esc(ch):
                    if ch == '\\':
                        return '\\\\'
                    elif ch == '"':
                        return '\\"'
                    elif ch == '\b':
                        return '\\b'
                    elif ch == '\f':
                        return '\\f'
                    elif ch == '\n':
                        return '\\n'
                    elif ch == '\r':
                        return '\\r'
                    elif ch == '\t':
                        return '\\t'
                    elif ord(ch) < 0x20:
                        # control char, use \u00XX
                        return '\\u%04x' % ord(ch)
                    else:
                        return ch
                return '"' + ''.join(esc(c) for c in s) + '"'
            
            # id: integer (no quotes)
            id_json = str(id_)
            # amount: string (quoted)
            amount_json = jstr(amount)
            # name: string or null
            name_json = "null" if name is None else jstr(name)
            # status: string (quoted)
            status_json = jstr(status)
            # tags: array of strings
            tags_json = "[" + ",".join(jstr(t) for t in tags) + "]"
            # child: JSON text or null (already JSON text)
            child_json_text = child_json
            
            # Compose full JSON object, fields in schema order
            json_obj = (
                "{" +
                '"id":' + id_json + "," +
                '"amount":' + amount_json + "," +
                '"name":' + name_json + "," +
                '"status":' + status_json + "," +
                '"tags":' + tags_json + "," +
                '"child":' + child_json_text +
                "}"
            )
            return json_obj
        
        return st.tuples(id_strat, amount_strat, name_strat, status_strat, tags_strat, child_strat).map(
            lambda tpl: build_record(*tpl)
        )
    
    # Generate top-level record JSON text
    json_text = draw(record_strat(0))
    return json_text.encode("utf-8")