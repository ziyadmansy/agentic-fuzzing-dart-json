from hypothesis import strategies as st

# Constants for enum values and field names
STATUS_VALUES = ['"active"', '"inactive"', '"unknown"']

# Helper to produce a JSON string literal with proper escaping of quotes and backslashes
def json_string_literal(s: str) -> str:
    # minimal escaping for quotes and backslash
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

@st.composite
def generated_json(draw) -> bytes:
    """
    Generate syntactically valid JSON objects matching the schema, but with
    variations that tend to cause divergence among four Dart JSON deserializers:
    - wrong_type fields (most common)
    - null_override fields (some)
    - bad_enum values (some)
    - boundary_id values near 53- or 64-bit integer boundaries (some)
    - extra_key occasionally
    - deep nesting up to 2 levels (one level normal, one level deeper)
    """

    # --- id field ---
    # Mostly integers in safe JS number range, sometimes boundary values or wrong types
    id_strategy = st.one_of(
        # normal int in safe range
        st.integers(min_value=0, max_value=2**53 - 1).map(str),
        # boundary values near 2^53 and 2^64
        st.sampled_from([
            str(2**53 - 1),
            str(2**53),
            str(2**53 + 1),
            str(2**64 - 1),
            str(2**64),
            str(2**64 + 1),
            "-1",
            "-9223372036854775808",  # min 64-bit signed int
            "9223372036854775807",   # max 64-bit signed int
        ]),
        # wrong type: string that looks like int but quoted (to cause confusion)
        st.text(min_size=1, max_size=10).filter(lambda x: x.isdigit()).map(lambda x: json_string_literal(x)),
        # wrong type: float as string
        st.floats(allow_nan=False, allow_infinity=False).map(lambda f: str(f)),
        # wrong type: boolean as string
        st.sampled_from(["true", "false"]),
    )
    id_val = draw(id_strategy)

    # --- amount field ---
    # amount is string, but sometimes null_override or wrong type
    # Mostly decimal strings, sometimes empty, sometimes null_override, sometimes number or bool
    amount_strategy = st.one_of(
        # normal decimal string
        st.decimals(min_value=0, max_value=1e9, allow_nan=False, allow_infinity=False).map(lambda d: json_string_literal(format(d, 'f'))),
        # empty string
        st.just('""'),
        # null_override (null instead of string)
        st.just("null"),
        # wrong type: number (not string)
        st.floats(allow_nan=False, allow_infinity=False).map(str),
        # wrong type: boolean
        st.sampled_from(["true", "false"]),
    )
    amount_val = draw(amount_strategy)

    # --- name field ---
    # string or null normally, but sometimes wrong type or null_override
    name_strategy = st.one_of(
        # normal string or null
        st.one_of(
            st.none().map(lambda _: "null"),
            st.text(min_size=0, max_size=20).map(json_string_literal),
        ),
        # wrong type: number
        st.floats(allow_nan=False, allow_infinity=False).map(str),
        # wrong type: boolean
        st.sampled_from(["true", "false"]),
        # wrong type: empty array
        st.just("[]"),
    )
    name_val = draw(name_strategy)

    # --- status field ---
    # enum string normally, sometimes bad_enum or null_override or wrong type
    status_strategy = st.one_of(
        st.sampled_from(STATUS_VALUES),
        # bad enum string
        st.text(min_size=1, max_size=10).filter(lambda s: s not in ['active', 'inactive', 'unknown']).map(json_string_literal),
        # null_override
        st.just("null"),
        # wrong type: number
        st.integers(min_value=0, max_value=10).map(str),
        # wrong type: boolean
        st.sampled_from(["true", "false"]),
    )
    status_val = draw(status_strategy)

    # --- tags field ---
    # array of strings normally, sometimes wrong type or null_override
    # tags array length 0 to 3, strings short
    tags_string = st.text(min_size=0, max_size=10).map(json_string_literal)
    tags_array = st.lists(tags_string, min_size=0, max_size=3).map(lambda lst: "[" + ",".join(lst) + "]")
    tags_strategy = st.one_of(
        tags_array,
        # null_override
        st.just("null"),
        # wrong type: string instead of array
        st.text(min_size=0, max_size=20).map(json_string_literal),
        # wrong type: number
        st.integers(min_value=0, max_value=100).map(str),
        # wrong type: boolean
        st.sampled_from(["true", "false"]),
    )
    tags_val = draw(tags_strategy)

    # --- child field ---
    # null or nested Record (one level normally), sometimes deeper nesting (2 levels)
    # or wrong type or null_override
    # To avoid infinite recursion, limit depth here to 2 max

    # Recursive helper to build child JSON string
    def child_record(depth: int) -> st.SearchStrategy[str]:
        if depth >= 2:
            # At max depth, child is null or null_override or wrong type
            return st.one_of(
                st.just("null"),
                # wrong type: string
                st.text(min_size=0, max_size=20).map(json_string_literal),
                # wrong type: number
                st.integers(min_value=0, max_value=100).map(str),
                # wrong type: boolean
                st.sampled_from(["true", "false"]),
            )
        else:
            # Build a nested record with fields similar to top-level but simpler
            # To keep it manageable, use simpler strategies for nested fields (mostly valid)
            nested_id = st.integers(min_value=0, max_value=1000).map(str)
            nested_amount = st.text(min_size=1, max_size=10).map(json_string_literal)
            nested_name = st.one_of(st.none().map(lambda _: "null"), st.text(min_size=0, max_size=10).map(json_string_literal))
            nested_status = st.sampled_from(STATUS_VALUES)
            nested_tags = st.lists(st.text(min_size=0, max_size=5).map(json_string_literal), min_size=0, max_size=2).map(lambda lst: "[" + ",".join(lst) + "]")
            # child of child is null or null (no deeper nesting)
            nested_child = st.just("null")

            nested_record = st.tuples(nested_id, nested_amount, nested_name, nested_status, nested_tags, nested_child).map(
                lambda t: (
                    '{'
                    + '"id":' + t[0] + ','
                    + '"amount":' + t[1] + ','
                    + '"name":' + t[2] + ','
                    + '"status":' + t[3] + ','
                    + '"tags":' + t[4] + ','
                    + '"child":' + t[5]
                    + '}'
                )
            )
            # Also allow null_override or wrong type for child field itself
            return st.one_of(
                nested_record,
                st.just("null"),
                st.text(min_size=0, max_size=20).map(json_string_literal),
                st.integers(min_value=0, max_value=100).map(str),
                st.sampled_from(["true", "false"]),
            )

    child_val = draw(child_record(0))

    # --- extra_key ---
    # Occasionally add an extra unexpected key to top-level object
    extra_key_chance = draw(st.floats(min_value=0, max_value=1))
    if extra_key_chance < 0.1:
        # Add extra key with random string or number or null
        extra_key_name = draw(st.text(min_size=1, max_size=10).filter(lambda s: s not in ['id','amount','name','status','tags','child']))
        extra_key_name_json = json_string_literal(extra_key_name)
        extra_key_value = draw(st.one_of(
            st.none().map(lambda _: "null"),
            st.text(min_size=0, max_size=10).map(json_string_literal),
            st.integers(min_value=0, max_value=100).map(str),
            st.sampled_from(["true", "false"]),
            st.lists(st.text(min_size=0, max_size=5).map(json_string_literal), min_size=0, max_size=2).map(lambda lst: "[" + ",".join(lst) + "]"),
        ))
        extra_key_str = f',{extra_key_name_json}:{extra_key_value}'
    else:
        extra_key_str = ""

    # Compose final JSON object string
    json_obj = (
        '{'
        + '"id":' + id_val + ','
        + '"amount":' + amount_val + ','
        + '"name":' + name_val + ','
        + '"status":' + status_val + ','
        + '"tags":' + tags_val + ','
        + '"child":' + child_val
        + extra_key_str
        + '}'
    )

    return json_obj.encode('utf-8')