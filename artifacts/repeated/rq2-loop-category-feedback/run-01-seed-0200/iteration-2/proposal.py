from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status field
    status_values = ["active", "inactive", "unknown"]

    # Helper: JSON string literal with proper escaping of " and \
    def json_string(s: str) -> str:
        # Minimal escaping for " and \ only, enough for this context
        return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

    # Recursive record generator with bounded depth (max 1 level of recursion)
    def record(depth: int) -> st.SearchStrategy[str]:
        # id: integer (try some edge cases and normal ints)
        id_strat = st.one_of(
            st.integers(min_value=-(2**31), max_value=2**31 - 1),
            st.just(0),
            st.just(1),
            st.just(-1),
        ).map(str)

        # amount: string (try empty, numeric strings, and some weird strings)
        amount_strat = st.one_of(
            st.text(min_size=0, max_size=5).filter(lambda s: all(c not in s for c in '"\\')),
            st.just("0"),
            st.just("123.45"),
            st.just("-0"),
            st.just(""),
        ).map(json_string)

        # name: string or null, including empty string, unicode, or null
        name_strat = st.one_of(
            st.none(),
            st.text(min_size=0, max_size=10).filter(lambda s: all(c not in s for c in '"\\')).map(json_string),
            # Also try a numeric string to test type confusion
            st.integers(min_value=-10, max_value=10).map(lambda i: json_string(str(i))),
        ).map(lambda v: "null" if v is None else v)

        # status: one of the allowed strings, plus some invalid strings to test rejection
        status_strat = st.one_of(
            st.sampled_from(status_values).map(json_string),
            # Inject some invalid strings to test divergence
            st.sampled_from(["active ", "inactive", "unknown", "invalid", ""]),
        )

        # tags: array of strings, including empty array, array with empty string, or array with null (invalid)
        tags_strat = st.one_of(
            st.lists(
                st.one_of(
                    st.text(min_size=0, max_size=5).filter(lambda s: all(c not in s for c in '"\\')).map(json_string),
                    # Also try null inside tags array (invalid by schema)
                    st.just("null"),
                ),
                max_size=3,
            ).map(lambda lst: "[" + ",".join(lst) + "]"),
            st.just("[]"),
        )

        # child: null or nested record (only one level deep)
        if depth > 0:
            child_strat = st.just("null")
        else:
            child_strat = st.one_of(
                st.just("null"),
                record(depth + 1).map(lambda s: s),
            )

        # Compose the record JSON string with one or two fields possibly off-type or missing
        # To induce divergence, randomly omit or malform one field at a time

        # Decide if we will omit a field or malform a field or keep all correct
        field_names = ["id", "amount", "name", "status", "tags", "child"]
        # Choose zero or one field to omit or malform
        fault_type = draw(st.sampled_from(["none", "omit", "malform"]))
        fault_field = None
        if fault_type != "none":
            fault_field = draw(st.sampled_from(field_names))

        # Generate each field normally or with fault
        def gen_field(name):
            if fault_type == "omit" and name == fault_field:
                # Omit this field entirely
                return None
            if fault_type == "malform" and name == fault_field:
                # Malform this field by producing a wrong type or invalid value
                if name == "id":
                    # id as string instead of integer
                    return '"id":' + json_string("not_an_int")
                elif name == "amount":
                    # amount as number (invalid, should be string)
                    return '"amount":123'
                elif name == "name":
                    # name as number (invalid, should be string or null)
                    return '"name":123'
                elif name == "status":
                    # status as number (invalid)
                    return '"status":123'
                elif name == "tags":
                    # tags as string (invalid, should be array)
                    return '"tags":"not_an_array"'
                elif name == "child":
                    # child as string (invalid, should be object or null)
                    return '"child":"not_an_object"'
                else:
                    # fallback, should not happen
                    return None
            else:
                # Normal generation
                if name == "id":
                    return '"id":' + draw(id_strat)
                elif name == "amount":
                    return '"amount":' + draw(amount_strat)
                elif name == "name":
                    return '"name":' + draw(name_strat)
                elif name == "status":
                    return '"status":' + draw(status_strat)
                elif name == "tags":
                    return '"tags":' + draw(tags_strat)
                elif name == "child":
                    return '"child":' + draw(child_strat)
                else:
                    return None

        fields = [gen_field(f) for f in field_names]
        # Remove omitted fields (None)
        fields = [f for f in fields if f is not None]

        json_obj = "{" + ",".join(fields) + "}"
        return json_obj

    # Draw the top-level record with depth 0
    json_text = draw(record(0))
    return json_text.encode("utf-8")