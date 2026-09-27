from hypothesis import strategies as st

# Constants for fixed sets
STATUS_VALUES = ["active", "inactive", "unknown"]
# We allow only ASCII alphanum tags for simplicity
TAG_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789"

@st.composite
def generated_json(draw) -> bytes:
    # Helper: generate a JSON string literal with proper escaping of quotes and backslashes
    def json_string(s: str) -> str:
        # Escape backslash and quote for JSON string
        return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

    # id field: to trigger divergence on id decoding:
    # manual and built_value require int (no double),
    # json_serializable and freezed accept double and call toInt().
    # jsonDecode turns integer literals outside 64-bit range into double.
    # So generate either:
    # - a safe int within 64-bit range (all accept)
    # - an integer literal outside 64-bit range (parsed as double by jsonDecode)
    # - a double that is not integral (all reject)
    id_case = draw(st.sampled_from(["int64_safe", "int64_outside", "double_nonint"]))
    if id_case == "int64_safe":
        # 64-bit signed int range: -2**63 .. 2**63-1
        id_val = draw(st.integers(min_value=-(2**63), max_value=2**63-1))
        id_json = str(id_val)
    elif id_case == "int64_outside":
        # integer literal outside 64-bit range, e.g. 2**63 or -2**63-1
        # jsonDecode parses as double, so manual and built_value reject,
        # json_serializable and freezed accept and saturate to int64 min/max.
        id_val = draw(st.sampled_from([2**63, -(2**63)-1]))
        id_json = str(id_val)
    else:
        # double non-integer, e.g. 1.5 or -3.14
        # all reject on type mismatch
        id_val = draw(st.floats(min_value=-1e10, max_value=1e10, allow_infinity=False, allow_nan=False))
        # force non-integer
        if int(id_val) == id_val:
            id_val += 0.5
        id_json = repr(id_val)

    # amount: string, always present, non-null
    # We keep it simple: decimal strings or empty string
    amount_val = draw(st.one_of(
        st.just("0"),
        st.from_regex(r"^-?\d+(\.\d+)?$", fullmatch=True),
        st.just(""),
    ))
    amount_json = json_string(amount_val)

    # name: nullable string or null
    # We test presence with null or string
    name_val = draw(st.one_of(st.none(), st.text(min_size=0, max_size=10)))
    name_json = "null" if name_val is None else json_string(name_val)

    # status: one of the three allowed strings or an unrecognized string (all reject)
    # To maximize chance of divergence, mostly valid but sometimes invalid
    status_val = draw(st.one_of(
        st.sampled_from(STATUS_VALUES),
        st.text(min_size=1, max_size=10).filter(lambda s: s not in STATUS_VALUES)
    ))
    status_json = json_string(status_val)

    # tags: array of strings, always present or missing (missing triggers built_value accept with empty list,
    # others reject). To test divergence, sometimes omit tags field.
    tags_present = draw(st.booleans())
    if tags_present:
        # tags array: zero or more strings, each string simple ascii alphanum
        tags_list = draw(st.lists(st.text(alphabet=TAG_CHARS, min_size=1, max_size=5), max_size=5))
        tags_json = "[" + ",".join(json_string(t) for t in tags_list) + "]"
    else:
        tags_json = None  # omit field

    # child: nullable record or null
    # To keep recursion bounded, child is either null or a record with no child (child=null)
    child_present = draw(st.booleans())
    if child_present:
        # child record with no child (child=null)
        # Use simpler id for child: safe int64
        child_id = draw(st.integers(min_value=-(2**63), max_value=2**63-1))
        child_amount = draw(st.just("0"))
        child_name = draw(st.one_of(st.none(), st.text(min_size=0, max_size=5)))
        child_status = draw(st.sampled_from(STATUS_VALUES))
        child_tags = draw(st.lists(st.text(alphabet=TAG_CHARS, min_size=1, max_size=5), max_size=3))
        child_json = (
            '{'
            f'"id":{child_id},'
            f'"amount":{json_string(child_amount)},'
            f'"name":{"null" if child_name is None else json_string(child_name)},'
            f'"status":{json_string(child_status)},'
            f'"tags":[' + ",".join(json_string(t) for t in child_tags) + '],'
            f'"child":null'
            '}'
        )
    else:
        child_json = "null"

    # Compose top-level JSON object fields
    fields = [
        f'"id":{id_json}',
        f'"amount":{amount_json}',
        f'"name":{name_json}',
        f'"status":{status_json}',
    ]
    if tags_json is not None:
        fields.append(f'"tags":{tags_json}')
    # else omit tags field to test divergence

    fields.append(f'"child":{child_json}')

    json_text = "{" + ",".join(fields) + "}"

    return json_text.encode("utf-8")