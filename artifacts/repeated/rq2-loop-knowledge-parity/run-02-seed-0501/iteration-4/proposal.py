from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status enum
    statuses = ["active", "inactive", "unknown"]

    # Strategy for id field:
    # To exploit difference in int vs num.toInt() acceptance,
    # generate either a true int or a float that is an integer value.
    # Also include out-of-64-bit-range integers as floats to test saturation.
    # But keep values in JSON number range.
    id_int = st.integers(min_value=-(2**63), max_value=2**63 - 1)
    # Large int outside 64-bit range, encoded as float (JSON number)
    id_large_float = st.one_of(
        st.floats(min_value=-(2**63)*10, max_value=-(2**63)-1, allow_infinity=False, allow_nan=False),
        st.floats(min_value=2**63, max_value=(2**63)*10, allow_infinity=False, allow_nan=False),
    )
    # Also allow normal floats that are integral (e.g. 1.0, 42.0)
    id_integral_float = st.floats(min_value=-(2**63), max_value=2**63 - 1, allow_infinity=False, allow_nan=False).filter(lambda f: f.is_integer())

    id_value = draw(st.one_of(
        id_int,
        id_integral_float,
        id_large_float,
    ))

    # amount: string, always present, non-null
    # Use non-empty strings and empty string to test boundaries
    amount_value = draw(st.text(min_size=0, max_size=10))

    # name: nullable string
    name_value = draw(st.one_of(st.none(), st.text(min_size=0, max_size=10)))

    # status: one of the known strings, or test unrecognized strings (should be rejected by all)
    # But since unrecognized status is rejected by all, no divergence there.
    # So only generate valid statuses here.
    status_value = draw(st.sampled_from(statuses))

    # tags: array of strings
    # To test missing tags (which built_value accepts silently but others reject),
    # we produce either present tags or missing tags.
    # But missing tags is a structural difference, not a type difference.
    # We want to test type differences too.
    # So generate either:
    # - tags present as array of strings (possibly empty)
    # - tags present but with wrong type (e.g. null or string instead of array)
    # - tags missing entirely (to test built_value acceptance)
    # We'll produce a union of these cases, but only one field off at a time.
    tags_present = st.lists(st.text(min_size=0, max_size=10), max_size=5)
    tags_wrong_type = st.one_of(st.none(), st.text(min_size=0, max_size=10), st.integers())
    tags_choice = draw(st.one_of(
        tags_present.map(lambda v: ("present", v)),
        tags_wrong_type.map(lambda v: ("wrong", v)),
        st.just(("missing", None)),
    ))

    # child: nullable Record (one level recursion)
    # To keep recursion bounded, define a helper for child record generation
    # with max depth 1 (child.child always null)
    def child_record():
        # child record fields, same schema but child always null
        id_c = draw(id_int)
        amount_c = draw(st.text(min_size=0, max_size=10))
        name_c = draw(st.one_of(st.none(), st.text(min_size=0, max_size=10)))
        status_c = draw(st.sampled_from(statuses))
        tags_c = draw(st.lists(st.text(min_size=0, max_size=10), max_size=3))
        # child is null here to avoid deeper recursion
        return {
            "id": id_c,
            "amount": amount_c,
            "name": name_c,
            "status": status_c,
            "tags": tags_c,
            "child": None,
        }

    # child present or null
    child_choice = draw(st.one_of(
        st.none(),
        st.just(child_record()),
    ))

    # Now build the base dict with all fields present except tags if missing
    base = {
        "id": id_value,
        "amount": amount_value,
        "name": name_value,
        "status": status_value,
        "child": child_choice,
    }

    # Insert tags field according to tags_choice
    tags_kind, tags_val = tags_choice
    if tags_kind == "present":
        base["tags"] = tags_val
    elif tags_kind == "wrong":
        base["tags"] = tags_val
    elif tags_kind == "missing":
        # omit tags field entirely
        pass

    # Now serialize base dict to JSON string manually, carefully:
    # We must produce syntactically valid JSON.
    # We cannot import json, so build JSON text by hand.

    # Helper to serialize JSON values:
    def json_escape_str(s: str) -> str:
        # minimal escaping for JSON string
        # escape backslash, double quote, control chars
        # Hypothesis strings are unicode, so escape control chars and quotes
        # We'll escape \, ", and control chars < 0x20
        res = []
        for c in s:
            o = ord(c)
            if c == '"':
                res.append('\\"')
            elif c == '\\':
                res.append('\\\\')
            elif o < 0x20:
                # control char, use \u00XX
                res.append('\\u%04x' % o)
            else:
                res.append(c)
        return '"' + ''.join(res) + '"'

    def json_serialize_value(v):
        if v is None:
            return "null"
        elif isinstance(v, bool):
            return "true" if v else "false"
        elif isinstance(v, int):
            return str(v)
        elif isinstance(v, float):
            # JSON floats must be finite
            # Use repr to get decimal notation
            # But repr can produce inf/nan, which is invalid JSON
            if v != v or v in (float('inf'), float('-inf')):
                # Should not happen due to filtering
                return "null"
            # Use format to avoid scientific notation for large ints as floats
            # but allow scientific notation for large floats
            # Use repr for simplicity
            return repr(v)
        elif isinstance(v, str):
            return json_escape_str(v)
        elif isinstance(v, list):
            return "[" + ",".join(json_serialize_value(x) for x in v) + "]"
        elif isinstance(v, dict):
            items = []
            for k, val in v.items():
                items.append(json_escape_str(k) + ":" + json_serialize_value(val))
            return "{" + ",".join(items) + "}"
        else:
            # Should not happen
            return "null"

    json_text = json_serialize_value(base)
    return json_text.encode("utf-8")