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
        # To increase divergence, sometimes serialize as integer-like float (e.g. 1.0)
        # or as a float with decimal point
        if id_choice.is_integer():
            id_json = f"{int(id_choice)}.0"
        else:
            id_json = repr(id_choice)
    else:
        # string
        id_json = json_string_literal(id_choice)

    # Compose "amount" field: string normally, but sometimes a number or null to cause divergence
    # To increase divergence, sometimes produce empty string or numeric string with leading zeros
    amount_choice = draw(st.one_of(
        st.text(min_size=0, max_size=15, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))),
        st.integers(min_value=-1000, max_value=1000).map(lambda i: f"{i:0>3}"),  # zero-padded numeric string
        st.none(),
        st.floats(allow_nan=False, allow_infinity=False).map(lambda f: f if f == int(f) else f),
    ))
    if amount_choice is None:
        amount_json = "null"
    elif isinstance(amount_choice, float):
        # serialize floats as JSON numbers
        amount_json = repr(amount_choice)
    elif isinstance(amount_choice, str):
        # string
        amount_json = json_string_literal(amount_choice)
    else:
        # fallback (should not happen)
        amount_json = json_string_literal(str(amount_choice))

    # Compose "name" field: string or null or wrong type (number or bool)
    # To increase divergence, sometimes produce empty string, or string with control chars
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
        # id: int or float (to increase divergence)
        cid = draw(st.one_of(
            st.integers(min_value=0, max_value=1000000),
            st.floats(allow_nan=False, allow_infinity=False).map(lambda f: f if f == int(f) else f),
        ))
        if isinstance(cid, int):
            cid_json = str(cid)
        else:
            if cid.is_integer():
                cid_json = f"{int(cid)}.0"
            else:
                cid_json = repr(cid)

        # amount: string or null or number (float or int)
        camount_choice = draw(st.one_of(
            st.text(min_size=0, max_size=15, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))),
            st.none(),
            st.integers(min_value=-1000, max_value=1000).map(str),
            st.floats(allow_nan=False, allow_infinity=False),
        ))
        if camount_choice is None:
            camount_json = "null"
        elif isinstance(camount_choice, float):
            camount_json = repr(camount_choice)
        elif isinstance(camount_choice, str):
            camount_json = json_string_literal(camount_choice)
        else:
            camount_json = str(camount_choice)

        # name: string or null or number or bool
        cname_choice = draw(st.one_of(
            st.none(),
            st.text(min_size=0, max_size=20, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))),
            st.integers(min_value=-1000, max_value=1000),
            st.booleans(),
        ))
        if cname_choice is None:
            cname_json = "null"
        elif isinstance(cname_choice, str):
            cname_json = json_string_literal(cname_choice)
        elif isinstance(cname_choice, bool):
            cname_json = "true" if cname_choice else "false"
        else:
            cname_json = str(cname_choice)

        # status: valid status string or invalid string or number (to increase divergence)
        cstatus_choice = draw(st.one_of(
            st.sampled_from(statuses),
            st.text(min_size=1, max_size=10).filter(lambda x: x not in statuses),
            st.integers(min_value=-10, max_value=10).map(str),
        ))
        cstatus_json = json_string_literal(cstatus_choice)

        # tags: array of strings (0 to 3)
        ctags = draw(st.lists(st.text(min_size=0, max_size=10, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))), max_size=3))
        ctags_json = "[" + ",".join(json_string_literal(t) for t in ctags) + "]"

        # child: null (no recursion deeper)
        cchild_json = "null"

        # Compose child record JSON
        return (
            "{" +
            f"\"id\":{cid_json}," +
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