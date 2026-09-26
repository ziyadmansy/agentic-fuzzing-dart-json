from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status field
    statuses = ["active", "inactive", "unknown"]

    # Helper to produce a JSON string literal with proper escaping for " and \
    def json_string_literal(s: str) -> str:
        # minimal escaping for " and \ and control chars
        # Hypothesis strings are unicode, but we keep it simple:
        # escape backslash and double quote only
        s = s.replace("\\", "\\\\").replace("\"", "\\\"")
        # also escape control chars (U+0000 to U+001F)
        def escape_ctrl(c):
            if ord(c) < 0x20:
                return "\\u%04x" % ord(c)
            return c
        s = "".join(escape_ctrl(c) for c in s)
        return f"\"{s}\""

    # Compose a JSON value for "name" field: either null or string or a non-string type (for divergence)
    # We will produce mostly valid or slightly off types here to trigger divergence.
    # But since the hint says vary one or two things at a time, we do that at the record level.

    # Compose a JSON array of strings for "tags"
    # We produce an array of 0 to 3 strings, each string is simple ascii printable
    tags = draw(st.lists(st.text(min_size=0, max_size=10, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))), max_size=3))
    tags_json = "[" + ",".join(json_string_literal(t) for t in tags) + "]"

    # Compose "status" field: mostly valid, but sometimes a wrong string or wrong type
    # To maximize divergence, we produce either a valid status string or a wrong string or a number
    status_choice = draw(st.one_of(
        st.sampled_from(statuses),
        st.text(min_size=1, max_size=10).filter(lambda x: x not in statuses),
        st.integers(min_value=-10, max_value=10).map(str),
    ))
    status_json = json_string_literal(status_choice)

    # Compose "id" field: integer normally, but sometimes a string or float to cause divergence
    id_choice = draw(st.one_of(
        st.integers(min_value=0, max_value=1000000),
        st.text(min_size=1, max_size=10).filter(lambda s: not s.isdigit()),
        st.floats(allow_nan=False, allow_infinity=False).map(lambda f: f if f == int(f) else f),
    ))
    if isinstance(id_choice, int):
        id_json = str(id_choice)
    elif isinstance(id_choice, float):
        # floats must be serialized as JSON numbers
        id_json = repr(id_choice)
    else:
        # string
        id_json = json_string_literal(id_choice)

    # Compose "amount" field: string normally, but sometimes a number or null to cause divergence
    amount_choice = draw(st.one_of(
        st.text(min_size=0, max_size=15, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))),
        st.integers(min_value=-1000, max_value=1000).map(str),
        st.none(),
    ))
    if amount_choice is None:
        amount_json = "null"
    elif isinstance(amount_choice, str):
        # string
        amount_json = json_string_literal(amount_choice)
    else:
        # number as string
        amount_json = amount_choice

    # Compose "name" field: string or null or wrong type (number or bool)
    name_choice = draw(st.one_of(
        st.none(),
        st.text(min_size=0, max_size=20, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))),
        st.integers(min_value=-1000, max_value=1000),
        st.booleans(),
    ))
    if name_choice is None:
        name_json = "null"
    elif isinstance(name_choice, str):
        name_json = json_string_literal(name_choice)
    elif isinstance(name_choice, bool):
        name_json = "true" if name_choice else "false"
    else:
        # int
        name_json = str(name_choice)

    # Compose "child" field: either null or a nested record (one level only)
    # To keep recursion bounded, child record is always well-formed or slightly off with one field varied.
    # We use a helper to generate a child record JSON string.

    def child_record_json():
        # For child record, vary only one field from well-formed:
        # id: int
        cid = draw(st.integers(min_value=0, max_value=1000000))
        # amount: string
        camount = draw(st.text(min_size=0, max_size=15, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))))
        camount_json = json_string_literal(camount)
        # name: string or null
        cname = draw(st.one_of(st.none(), st.text(min_size=0, max_size=20, alphabet=st.characters(blacklist_categories=('Cs', 'Cc')))))
        cname_json = "null" if cname is None else json_string_literal(cname)
        # status: valid status string
        cstatus = draw(st.sampled_from(statuses))
        cstatus_json = json_string_literal(cstatus)
        # tags: array of strings
        ctags = draw(st.lists(st.text(min_size=0, max_size=10, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))), max_size=3))
        ctags_json = "[" + ",".join(json_string_literal(t) for t in ctags) + "]"
        # child: null (no recursion deeper)
        cchild_json = "null"
        # Compose child record JSON
        return (
            "{" +
            f"\"id\":{cid}," +
            f"\"amount\":{camount_json}," +
            f"\"name\":{cname_json}," +
            f"\"status\":{cstatus_json}," +
            f"\"tags\":{ctags_json}," +
            f"\"child\":{cchild_json}" +
            "}"
        )

    child_is_null = draw(st.booleans())
    if child_is_null:
        child_json = "null"
    else:
        child_json = child_record_json()

    # Compose the top-level JSON object
    json_obj = (
        "{" +
        f"\"id\":{id_json}," +
        f"\"amount\":{amount_json}," +
        f"\"name\":{name_json}," +
        f"\"status\":{status_json}," +
        f"\"tags\":{tags_json}," +
        f"\"child\":{child_json}" +
        "}"
    )

    return json_obj.encode("utf-8")