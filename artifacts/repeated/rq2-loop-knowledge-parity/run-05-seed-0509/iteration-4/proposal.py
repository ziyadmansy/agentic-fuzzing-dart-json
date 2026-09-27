from hypothesis import strategies as st

# Constants for fields
STATUS_VALUES = ['active', 'inactive', 'unknown']

# Helper to produce JSON string literals safely (no escapes needed for test)
def json_string(s: str) -> str:
    # minimal escaping for " and \
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

@st.composite
def generated_json(draw) -> bytes:
    """
    Generate syntactically valid JSON objects as bytes, matching the schema with
    subtle variations to trigger behavioral divergence between four Dart JSON deserializers.
    """

    # --- id field ---
    # id is integer in JSON normally, but jsonDecode can produce double for large ints.
    # We exploit this by generating either:
    # - a normal int within 64-bit range (accepted by all)
    # - a large int outside 64-bit range, encoded as a JSON number literal (which jsonDecode
    #   turns into a double), accepted by json_serializable and freezed but not manual/built_value
    #
    # We generate either:
    # 1) int in 0..2^53 (safe int range for JSON numbers)
    # 2) int in [2^63, 2^63+1000] (too large for 64-bit int, jsonDecode makes double)
    # 3) int in [-2^63-1000, -2^63] (too small for 64-bit int)
    #
    # This triggers divergence on id decoding.

    id_case = draw(st.integers(min_value=1, max_value=3))
    if id_case == 1:
        # safe int range
        id_val = draw(st.integers(min_value=0, max_value=2**53))
    elif id_case == 2:
        # large positive int outside 64-bit range
        id_val = draw(st.integers(min_value=2**63, max_value=2**63 + 1000))
    else:
        # large negative int outside 64-bit range
        id_val = draw(st.integers(min_value=-(2**63) - 1000, max_value=-(2**63)))

    # Encode id_val as JSON number literal (no quotes)
    id_json = str(id_val)

    # --- amount field ---
    # amount is string, non-nullable
    # We generate either a normal decimal string or a numeric string that looks like a number,
    # or an empty string, or a string with whitespace, to test subtle acceptance.
    amount_str = draw(
        st.one_of(
            st.decimals(min_value=0, max_value=1e9, allow_nan=False, allow_infinity=False)
            .map(lambda d: format(d, 'f').rstrip('0').rstrip('.') if '.' in format(d, 'f') else format(d, 'f')),
            st.text(min_size=0, max_size=10).filter(lambda s: all(c not in s for c in '"\\')),
            st.just(""),
            st.just(" 123 "),
        )
    )
    # JSON string literal for amount
    amount_json = json_string(amount_str)

    # --- name field ---
    # nullable string, missing allowed and accepted by all
    # We generate either:
    # - a string (possibly empty)
    # - null
    # - missing (to test acceptance)
    name_case = draw(st.integers(min_value=1, max_value=3))
    if name_case == 1:
        # present string
        name_val = draw(st.text(min_size=0, max_size=10).filter(lambda s: all(c not in s for c in '"\\')))
        name_json = json_string(name_val)
        name_present = True
    elif name_case == 2:
        # present null
        name_json = "null"
        name_present = True
    else:
        # missing
        name_present = False

    # --- status field ---
    # one of "active", "inactive", "unknown"
    # We generate either a valid status or an invalid string to test rejection
    status_case = draw(st.integers(min_value=1, max_value=3))
    if status_case == 1:
        status_val = draw(st.sampled_from(STATUS_VALUES))
    elif status_case == 2:
        # invalid status string (not recognized)
        status_val = draw(st.text(min_size=1, max_size=10).filter(lambda s: s not in STATUS_VALUES and all(c not in s for c in '"\\')))
    else:
        # valid status again to keep some valid cases
        status_val = draw(st.sampled_from(STATUS_VALUES))
    status_json = json_string(status_val)

    # --- tags field ---
    # array of strings, nullable? No, always present in well-formed documents.
    # Missing tags is accepted only by built_value (empty list), rejected by others.
    # We generate either:
    # - present array of strings (possibly empty)
    # - missing (to trigger divergence)
    tags_case = draw(st.integers(min_value=1, max_value=2))
    if tags_case == 1:
        # present array of strings
        tags_len = draw(st.integers(min_value=0, max_value=3))
        tags_vals = draw(st.lists(st.text(min_size=0, max_size=5).filter(lambda s: all(c not in s for c in '"\\')), min_size=tags_len, max_size=tags_len))
        tags_json = "[" + ",".join(json_string(t) for t in tags_vals) + "]"
        tags_present = True
    else:
        # missing tags field
        tags_present = False

    # --- child field ---
    # nullable Record or null or missing (missing accepted by all)
    # We generate either:
    # - null
    # - missing
    # - a shallow record (no recursion beyond one level)
    child_case = draw(st.integers(min_value=1, max_value=3))
    if child_case == 1:
        # null
        child_json = "null"
        child_present = True
    elif child_case == 2:
        # missing
        child_present = False
    else:
        # present shallow record with minimal valid fields (no recursion)
        # id: safe int
        c_id = draw(st.integers(min_value=0, max_value=2**53))
        c_id_json = str(c_id)
        # amount: string "0"
        c_amount_json = json_string("0")
        # name: null
        c_name_json = "null"
        # status: "unknown"
        c_status_json = json_string("unknown")
        # tags: empty array
        c_tags_json = "[]"
        # child: null
        c_child_json = "null"
        child_json = (
            "{" +
            f'"id":{c_id_json},'
            f'"amount":{c_amount_json},'
            f'"name":{c_name_json},'
            f'"status":{c_status_json},'
            f'"tags":{c_tags_json},'
            f'"child":{c_child_json}'
            "}"
        )
        child_present = True

    # Compose top-level JSON object fields
    fields = [
        f'"id":{id_json}',
        f'"amount":{amount_json}',
        f'"status":{status_json}',
    ]
    if name_present:
        fields.append(f'"name":{name_json}')
    if tags_present:
        fields.append(f'"tags":{tags_json}')
    if child_present:
        fields.append(f'"child":{child_json}')

    # Shuffle fields order to avoid positional bias
    # Hypothesis does not have a built-in shuffle for lists, so we do a simple random permutation
    fields = draw(st.permutations(fields))

    json_text = "{" + ",".join(fields) + "}"

    return json_text.encode("utf-8")