from hypothesis import strategies as st

# Helper to escape JSON strings
def _escape_json_string(s):
    return (
        '"' +
        s.replace('\\', '\\\\')
         .replace('"', '\\"')
         .replace('\b', '\\b')
         .replace('\f', '\\f')
         .replace('\n', '\\n')
         .replace('\r', '\\r')
         .replace('\t', '\\t')
        + '"'
    )

# Generate a valid or slightly off-type value for a field
@st.composite
def _maybe_wrong(draw, correct, wrongs, p_wrong=0.15):
    """With probability p_wrong, draw from wrongs, else from correct."""
    if draw(st.booleans()) if draw(st.randoms()).random() < p_wrong else False:
        return draw(wrongs)
    else:
        return draw(correct)

# Generate a string that might be a valid number, or a string that looks like a number but isn't
@st.composite
def _amount_string(draw):
    # 80%: valid decimal string, 20%: "almost" valid or weird string
    if draw(st.booleans()) if draw(st.randoms()).random() < 0.2 else False:
        # Weird string: empty, whitespace, non-numeric, or with leading zeros, etc.
        weirds = [
            "",
            "  ",
            "NaN",
            "1e309",
            "1.2.3",
            "01.23",
            "-0",
            "+12",
            "1_000",
            "Infinity",
            "-Infinity",
            "null",
            "None",
            "0x10",
            "1,000",
            "1.0 ",
            " 1.0",
            "1.0\n",
        ]
        return _escape_json_string(draw(st.sampled_from(weirds)))
    else:
        # Valid decimal string
        n = draw(st.decimals(allow_nan=False, allow_infinity=False, places=2))
        return _escape_json_string(str(n))

# Generate a string or null for "name", but sometimes wrong type (number, bool, array, object)
@st.composite
def _name_field(draw):
    # 80%: correct (string or null), 20%: wrong type
    if draw(st.booleans()) if draw(st.randoms()).random() < 0.2 else False:
        wrong = draw(st.one_of(
            st.integers().map(str),
            st.floats(allow_nan=False, allow_infinity=False).map(str),
            st.booleans().map(lambda b: "true" if b else "false"),
            st.lists(st.text(min_size=0, max_size=3), max_size=2).map(
                lambda l: "[" + ",".join(_escape_json_string(x) for x in l) + "]"
            ),
            st.just("{}"),
        ))
        return wrong
    else:
        if draw(st.booleans()):
            return "null"
        else:
            s = draw(st.text(min_size=0, max_size=12))
            return _escape_json_string(s)

# Generate a status field, sometimes with wrong value or type
@st.composite
def _status_field(draw):
    # 85%: correct, 15%: wrong (wrong string, wrong type)
    if draw(st.booleans()) if draw(st.randoms()).random() < 0.15 else False:
        wrong = draw(st.one_of(
            st.text(min_size=0, max_size=8).filter(lambda s: s not in {"active", "inactive", "unknown"}).map(_escape_json_string),
            st.integers().map(str),
            st.just("null"),
            st.just("true"),
            st.just("false"),
            st.just("[]"),
            st.just("{}"),
        ))
        return wrong
    else:
        val = draw(st.sampled_from(["active", "inactive", "unknown"]))
        return _escape_json_string(val)

# Generate tags: array of strings, sometimes wrong type/contents
@st.composite
def _tags_field(draw):
    # 85%: correct (array of strings), 15%: wrong (wrong type, non-string elements, etc)
    if draw(st.booleans()) if draw(st.randoms()).random() < 0.15 else False:
        wrong = draw(st.one_of(
            st.just("null"),
            st.just("true"),
            st.just("false"),
            st.integers().map(str),
            st.text(min_size=0, max_size=8).map(_escape_json_string),
            st.lists(st.integers(), min_size=1, max_size=3).map(
                lambda l: "[" + ",".join(str(x) for x in l) + "]"
            ),
            st.lists(st.just("null"), min_size=1, max_size=2).map(
                lambda l: "[" + ",".join(l) + "]"
            ),
            st.just("{}"),
        ))
        return wrong
    else:
        tags = draw(st.lists(st.text(min_size=0, max_size=8).map(_escape_json_string), min_size=0, max_size=4))
        return "[" + ",".join(tags) + "]"

# Generate a child field: null or another record (with limited recursion)
def _child_field(depth):
    @st.composite
    def inner(draw):
        # 80%: null, 20%: nested record (with depth limit)
        if depth <= 0 or (draw(st.booleans()) if draw(st.randoms()).random() < 0.8 else False):
            return "null"
        else:
            # Recursively generate a record, but with depth-1
            rec = draw(_record(depth-1))
            return rec
    return inner()

# Generate the full record as a JSON object string
def _record(depth):
    @st.composite
    def inner(draw):
        # id: integer, but sometimes wrong type (string, float, bool, null)
        id_field = draw(_maybe_wrong(
            st.integers(min_value=0, max_value=2**31-1).map(str),
            st.one_of(
                st.text(min_size=0, max_size=8).map(_escape_json_string),
                st.floats(allow_nan=False, allow_infinity=False).map(str),
                st.just("null"),
                st.just("true"),
                st.just("false"),
                st.just("[]"),
                st.just("{}"),
            ),
            p_wrong=0.12
        ))
        amount_field = draw(_amount_string())
        name_field = draw(_name_field())
        status_field = draw(_status_field())
        tags_field = draw(_tags_field())
        child_field = draw(_child_field(depth))

        # Compose JSON object
        fields = [
            f'"id":{id_field}',
            f'"amount":{amount_field}',
            f'"name":{name_field}',
            f'"status":{status_field}',
            f'"tags":{tags_field}',
            f'"child":{child_field}',
        ]
        # Optionally permute field order to catch order-sensitivity bugs
        if draw(st.booleans()):
            draw(st.randoms()).shuffle(fields)
        obj = "{" + ",".join(fields) + "}"
        return obj
    return inner()

@st.composite
def generated_json(draw):
    # Limit recursion depth and total output size
    rec = draw(_record(depth=1))
    # Output as bytes
    return rec.encode("utf-8")