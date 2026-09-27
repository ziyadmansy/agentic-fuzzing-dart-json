from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status field
    statuses = st.sampled_from(["active", "inactive", "unknown"])

    # id field: to trigger divergence, generate either int or double (float) JSON number
    # manual and built_value require int (no double), json_serializable and freezed accept double and convert to int.
    # jsonDecode parses JSON numbers as int or float automatically.
    # We generate either an integer literal or a floating-point literal representing an integer.
    # Also include edge cases near int64 boundaries to test saturation behavior.
    int64_min = -2**63
    int64_max = 2**63 - 1

    # Generate id as either int or float (with .0) representing an integer
    id_int = st.integers(min_value=int64_min, max_value=int64_max)
    # float with .0 suffix, same integer value but as float
    id_float = id_int.map(lambda x: float(x))

    # id choice: 50% int, 50% float
    id_value = st.one_of(id_int, id_float)

    # amount: string, always present, non-null
    # Use simple decimal strings, but also allow empty string to test edge cases
    amount = st.text(min_size=0, max_size=10).filter(lambda s: all(c.isdigit() or c in ".-" for c in s))

    # name: nullable string, can be null or string
    name = st.one_of(st.none(), st.text(min_size=0, max_size=20))

    # status: one of three strings, always present
    status = statuses

    # tags: array of strings, always present (to avoid built_value silent default)
    # To test missing tags, we can generate a separate strategy that sometimes omits tags,
    # but per instructions, missing tags is accepted only by built_value, rejected by others.
    # So we generate tags always present here, but later we can generate a variant with missing tags.
    # To maximize divergence, we generate tags sometimes missing.
    # We'll do this by generating a boolean to decide if tags is present or missing.
    tags_present = draw(st.booleans())
    if tags_present:
        tags = draw(st.lists(st.text(min_size=0, max_size=10), max_size=5))
    else:
        tags = None  # missing tags field

    # child: nullable Record or null
    # To avoid deep recursion, limit to one level of recursion.
    # We'll generate child as either null or a nested record with no child (child=null).
    # To keep it simple, generate child as null or a record with child=null.
    # We generate child record fields similarly but with child=null.
    def gen_record(child_allowed=True):
        # id
        id_val = draw(id_value)
        # amount
        amount_val = draw(amount)
        # name
        name_val = draw(name)
        # status
        status_val = draw(status)
        # tags present or missing
        tags_pres = draw(st.booleans())
        if tags_pres:
            tags_val = draw(st.lists(st.text(min_size=0, max_size=10), max_size=5))
        else:
            tags_val = None
        # child
        if child_allowed:
            # child is either null or a record with child=null
            child_is_null = draw(st.booleans())
            if child_is_null:
                child_val = None
            else:
                # child record with child=null (no further recursion)
                child_val = {
                    "id": draw(id_value),
                    "amount": draw(amount),
                    "name": draw(name),
                    "status": draw(status),
                    "tags": draw(st.lists(st.text(min_size=0, max_size=10), max_size=5)),
                    "child": None,
                }
        else:
            child_val = None

        # Build dict, omitting tags if tags_val is None (to test missing tags)
        d = {
            "id": id_val,
            "amount": amount_val,
            "name": name_val,
            "status": status_val,
            "child": child_val,
        }
        if tags_val is not None:
            d["tags"] = tags_val
        # else omit tags key

        return d

    # Generate top-level record with child allowed
    record = gen_record(child_allowed=True)

    # Now serialize record to JSON text manually, carefully formatting fields
    # We must produce syntactically valid JSON text with correct quoting and escaping.
    # We'll define helper functions to serialize JSON values.

    def json_escape_str(s: str) -> str:
        # Escape backslash, double quote, and control chars minimally
        # For simplicity, escape backslash and double quote only
        s = s.replace("\\", "\\\\").replace('"', '\\"')
        # Also replace control chars with \uXXXX escapes
        def esc_char(c):
            if ord(c) < 0x20:
                return "\\u%04x" % ord(c)
            else:
                return c
        s = "".join(esc_char(c) for c in s)
        return s

    def json_serialize_value(v):
        if v is None:
            return "null"
        elif isinstance(v, bool):
            return "true" if v else "false"
        elif isinstance(v, int):
            return str(v)
        elif isinstance(v, float):
            # Serialize float with decimal point, even if integral
            # Use repr to preserve precision, but ensure decimal point
            s = repr(v)
            if "e" in s or "E" in s:
                # Convert scientific notation to decimal notation if possible
                # But to keep it simple, leave as is
                return s
            if "." not in s:
                s += ".0"
            return s
        elif isinstance(v, str):
            return '"' + json_escape_str(v) + '"'
        elif isinstance(v, list):
            return "[" + ",".join(json_serialize_value(x) for x in v) + "]"
        elif isinstance(v, dict):
            # keys are strings
            items = []
            for k, val in v.items():
                items.append('"' + json_escape_str(k) + '":' + json_serialize_value(val))
            return "{" + ",".join(items) + "}"
        else:
            # Should not happen
            raise ValueError("Unsupported type for JSON serialization: %r" % type(v))

    json_text = json_serialize_value(record)

    # Return bytes as required
    return json_text.encode("utf-8")