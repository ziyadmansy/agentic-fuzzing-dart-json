from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for fields
    STATUS_VALUES = ["active", "inactive", "unknown"]
    
    # Base valid fields strategies
    # id: int or double (to trigger divergence on id decoding)
    # manual and built_value require int, json_serializable and freezed accept double.toInt()
    # So we produce either an int or a double representing an int (or out-of-range double)
    # We'll produce int64-range ints and also doubles outside int64 range to trigger saturation
    
    # int64 range limits
    INT64_MIN = -2**63
    INT64_MAX = 2**63 - 1
    
    # Strategy for id as int64-range int
    id_int = st.integers(min_value=INT64_MIN, max_value=INT64_MAX)
    
    # Strategy for id as double that is an integer value (e.g. 42.0)
    # Use floats that are exactly representable as integers but as float type
    # Also include doubles outside int64 range to trigger saturation in toInt()
    # Hypothesis floats are double precision by default
    id_double_in_range = st.floats(min_value=float(INT64_MIN), max_value=float(INT64_MAX),
                                  allow_infinity=False, allow_nan=False).filter(lambda f: f.is_integer())
    id_double_out_of_range = st.one_of(
        st.floats(min_value=float(INT64_MAX)+1, max_value=1e20, allow_infinity=False, allow_nan=False),
        st.floats(min_value=-1e20, max_value=float(INT64_MIN)-1, allow_infinity=False, allow_nan=False)
    )
    id_double = st.one_of(id_double_in_range, id_double_out_of_range)
    
    # id field: either int or double (to trigger divergence)
    id_field = st.one_of(id_int, id_double)
    
    # amount: string, always present, non-null
    # Use simple decimal strings, including edge cases like "0", "0.0", "-0.0", "1e10"
    amount_field = st.one_of(
        st.text(min_size=1, max_size=10).filter(lambda s: all(c in "0123456789.-+eE" for c in s)),
        st.just("0"),
        st.just("0.0"),
        st.just("-0.0"),
        st.just("1e10"),
        st.just("-1e10"),
    )
    
    # name: nullable string
    name_field = st.one_of(st.none(), st.text(min_size=0, max_size=20))
    
    # status: one of the three valid strings
    status_field = st.sampled_from(STATUS_VALUES)
    
    # tags: array of strings, always present (empty array allowed)
    # To trigger divergence, sometimes omit tags field (built_value accepts, others reject)
    # But the problem states all six fields always present in well-formed document,
    # so we produce always present tags, but sometimes empty list to test behavior
    tags_field = st.lists(st.text(min_size=0, max_size=10), max_size=5)
    
    # child: nullable Record, one level recursion only
    # To avoid infinite recursion, child is either null or a record with child=null
    # We'll produce child as None or a record with child=None (no deeper)
    # Use st.deferred to allow recursion
    
    # Define record fields except child first
    def record_fields():
        return st.tuples(
            id_field,
            amount_field,
            name_field,
            status_field,
            tags_field,
        )
    
    @st.composite
    def record(draw, allow_child=True):
        idv, amountv, namev, statusv, tagsv = draw(record_fields())
        if allow_child:
            # child is either null or a record with child=null (no deeper recursion)
            childv = draw(st.one_of(st.none(), record(allow_child=False)))
        else:
            childv = None
        return {
            "id": idv,
            "amount": amountv,
            "name": namev,
            "status": statusv,
            "tags": tagsv,
            "child": childv,
        }
    
    # Draw the top-level record
    doc = draw(record())
    
    # Now serialize to JSON text manually, carefully:
    # - id: if int, output as integer literal
    #       if float, output as float literal with decimal point (e.g. 42.0)
    # - amount: string, output as JSON string with quotes, escape as needed
    # - name: null or string
    # - status: string
    # - tags: array of strings
    # - child: null or record (recursive)
    
    def json_escape_str(s: str) -> str:
        # Minimal JSON string escaping: backslash, quote, control chars
        # We'll replace backslash and quote and control chars with \uXXXX escapes
        res = []
        for c in s:
            o = ord(c)
            if c == '"':
                res.append('\\"')
            elif c == '\\':
                res.append('\\\\')
            elif o < 0x20:
                res.append('\\u%04x' % o)
            else:
                res.append(c)
        return '"' + ''.join(res) + '"'
    
    def serialize_value(v):
        if v is None:
            return "null"
        elif isinstance(v, bool):
            return "true" if v else "false"
        elif isinstance(v, int):
            return str(v)
        elif isinstance(v, float):
            # Output float with decimal point or exponent
            # Use repr to preserve precision, but ensure decimal point or exponent present
            s = repr(v)
            if "e" not in s and "." not in s:
                s += ".0"
            return s
        elif isinstance(v, str):
            return json_escape_str(v)
        elif isinstance(v, list):
            return "[" + ",".join(serialize_value(x) for x in v) + "]"
        elif isinstance(v, dict):
            # keys are strings
            items = []
            for k in ["id", "amount", "name", "status", "tags", "child"]:
                # Always output all six fields in order
                val = v.get(k)
                items.append(json_escape_str(k) + ":" + serialize_value(val))
            return "{" + ",".join(items) + "}"
        else:
            # Should not happen
            return "null"
    
    json_text = serialize_value(doc)
    return json_text.encode("utf-8")