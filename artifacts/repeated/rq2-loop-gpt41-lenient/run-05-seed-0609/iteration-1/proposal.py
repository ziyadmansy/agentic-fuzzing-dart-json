from hypothesis import strategies as st

# Constants for field values
STATUSES = ["active", "inactive", "unknown"]

# Helper: JSON-escape a string (minimal, covers common cases)
def escape(s):
    return (
        s.replace('\\', '\\\\')
         .replace('"', '\\"')
         .replace('\b', '\\b')
         .replace('\f', '\\f')
         .replace('\n', '\\n')
         .replace('\r', '\\r')
         .replace('\t', '\\t')
    )

# Helper: JSON-encode a string
def jstr(s):
    return '"' + escape(s) + '"'

# Helper: JSON-encode an array of strings
def jarray_str(arr):
    return '[' + ','.join(jstr(x) for x in arr) + ']'

# Helper: JSON-encode a field (name, value)
def field(name, value):
    return jstr(name) + ':' + value

# Main record generator
@st.composite
def generated_json(draw, _recursion=0):
    # For divergence, we want to vary one or two fields at a time, mostly well-formed
    # Each field can be: correct, or have a subtle type/shape error, or be null (if allowed)
    # We'll randomly select 0-2 fields to "perturb" per record

    # Choose which fields to perturb
    fields = ["id", "amount", "name", "status", "tags", "child"]
    n_perturb = draw(st.integers(min_value=0, max_value=2))
    perturb_fields = draw(st.lists(st.sampled_from(fields), min_size=n_perturb, max_size=n_perturb, unique=True))

    # id: integer (required, never null)
    if "id" in perturb_fields:
        id_val = draw(
            st.one_of(
                # Wrong type: string, float, bool, null
                st.integers().map(lambda x: jstr(str(x))),
                st.floats(allow_nan=False, allow_infinity=False).map(str),
                st.booleans().map(lambda b: "true" if b else "false"),
                st.just("null"),
            )
        )
    else:
        id_val = str(draw(st.integers(min_value=-2**31, max_value=2**31-1)))

    # amount: string (required, never null)
    if "amount" in perturb_fields:
        amount_val = draw(
            st.one_of(
                # Wrong type: int, float, bool, null, array, object
                st.integers().map(str),
                st.floats(allow_nan=False, allow_infinity=False).map(str),
                st.booleans().map(lambda b: "true" if b else "false"),
                st.just("null"),
                st.lists(st.text(min_size=0, max_size=5), min_size=0, max_size=3).map(jarray_str),
                st.just("{}"),
            )
        )
    else:
        amount_val = jstr(draw(st.text(min_size=0, max_size=20)))

    # name: string or null
    if "name" in perturb_fields:
        name_val = draw(
            st.one_of(
                # Wrong type: int, float, bool, array, object
                st.integers().map(str),
                st.floats(allow_nan=False, allow_infinity=False).map(str),
                st.booleans().map(lambda b: "true" if b else "false"),
                st.lists(st.text(min_size=0, max_size=5), min_size=0, max_size=3).map(jarray_str),
                st.just("{}"),
                # "null" is valid, but let's try a string "null" too
                st.just(jstr("null")),
            )
        )
    else:
        name_val = draw(
            st.one_of(
                st.text(min_size=0, max_size=20).map(jstr),
                st.just("null"),
            )
        )

    # status: one of STATUSES (required, never null)
    if "status" in perturb_fields:
        status_val = draw(
            st.one_of(
                # Wrong type: int, bool, null, array, object
                st.integers().map(str),
                st.booleans().map(lambda b: "true" if b else "false"),
                st.just("null"),
                st.lists(st.text(min_size=0, max_size=5), min_size=0, max_size=3).map(jarray_str),
                st.just("{}"),
                # Wrong string
                st.text(min_size=1, max_size=10).filter(lambda s: s not in STATUSES).map(jstr),
            )
        )
    else:
        status_val = jstr(draw(st.sampled_from(STATUSES)))

    # tags: array of strings (required, never null)
    if "tags" in perturb_fields:
        tags_val = draw(
            st.one_of(
                # Wrong type: int, string, bool, null, object
                st.integers().map(str),
                st.text(min_size=0, max_size=20).map(jstr),
                st.booleans().map(lambda b: "true" if b else "false"),
                st.just("null"),
                st.just("{}"),
                # Array with wrong element types
                st.lists(
                    st.one_of(
                        st.integers().map(str),
                        st.just("null"),
                        st.booleans().map(lambda b: "true" if b else "false"),
                        st.text(min_size=0, max_size=5).map(jstr),
                    ),
                    min_size=0, max_size=3
                ).map(lambda arr: "[" + ",".join(arr) + "]"),
            )
        )
    else:
        tags_val = jarray_str(draw(st.lists(st.text(min_size=0, max_size=10), min_size=0, max_size=3)))

    # child: Record or null (one level recursion)
    if "child" in perturb_fields:
        child_val = draw(
            st.one_of(
                # Wrong type: int, string, bool, array
                st.integers().map(str),
                st.text(min_size=0, max_size=20).map(jstr),
                st.booleans().map(lambda b: "true" if b else "false"),
                st.lists(st.text(min_size=0, max_size=5), min_size=0, max_size=3).map(jarray_str),
                st.just("null"),
            )
        )
    else:
        # 60% null, 40% nested record (but only one level deep)
        if _recursion == 0:
            child_val = draw(
                st.one_of(
                    st.just("null"),
                    generated_json(_recursion=1).map(lambda b: b.decode("utf-8")),
                )
            )
        else:
            child_val = "null"

    # Compose the JSON object
    obj = (
        '{'
        + field("id", id_val) + ','
        + field("amount", amount_val) + ','
        + field("name", name_val) + ','
        + field("status", status_val) + ','
        + field("tags", tags_val) + ','
        + field("child", child_val)
        + '}'
    )

    # Return as bytes
    return obj.encode("utf-8")