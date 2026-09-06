from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status enum
    statuses = ["active", "inactive", "unknown"]

    # Strategy for id: mostly integer as string (correct), sometimes stringified float or stringified negative int (wrong type)
    id_int = st.integers(min_value=0, max_value=2**31-1).map(str)
    id_float_str = st.floats(min_value=0, max_value=1e6, allow_infinity=False, allow_nan=False).map(lambda f: f"{f:.1f}")
    id_wrong_type = st.one_of(id_float_str, st.text(min_size=1, max_size=5)).filter(lambda s: not s.isdigit())
    id_strategy = st.one_of(id_int, id_wrong_type)

    # amount: string, mostly decimal numbers as strings, sometimes empty string or string with spaces (valid JSON string but maybe unexpected)
    amount_num_str = st.decimals(min_value=0, max_value=1e6, places=2).map(lambda d: format(d, 'f'))
    amount_empty = st.just("")
    amount_spaces = st.just("  ")
    amount_strategy = st.one_of(amount_num_str, amount_empty, amount_spaces)

    # name: string or null, but sometimes number or boolean as string (wrong type)
    name_null = st.just("null")
    name_str = st.text(min_size=0, max_size=10).map(lambda s: '"' + s.replace('"', '\\"') + '"')
    name_wrong = st.one_of(
        st.integers(min_value=0, max_value=100).map(str),
        st.sampled_from(["true", "false", "123", "null"])
    ).map(lambda s: '"' + s + '"')
    # Mix mostly correct or null, sometimes wrong type stringified
    name_strategy = st.one_of(name_null, name_str, name_wrong)

    # status: one of the three strings, sometimes uppercase or misspelled (wrong enum)
    status_correct = st.sampled_from(statuses).map(lambda s: '"' + s + '"')
    status_wrong = st.sampled_from(["Active", "INACTIVE", "unknwn", "invalid"]).map(lambda s: '"' + s + '"')
    status_strategy = st.one_of(status_correct, status_wrong)

    # tags: array of strings, sometimes empty array, sometimes array with null or numbers (wrong type)
    tag_str = st.text(min_size=1, max_size=5).map(lambda s: '"' + s.replace('"', '\\"') + '"')
    tag_null = st.just("null")
    tag_num = st.integers(min_value=0, max_value=100).map(str)
    tag_wrong = st.one_of(tag_null, tag_num)
    # tags array: mostly strings, sometimes one wrong element
    tags_correct = st.lists(tag_str, min_size=0, max_size=3).map(lambda lst: "[" + ",".join(lst) + "]")
    def tags_mixed():
        # Insert one wrong element at random position
        def build(lst):
            if not lst:
                return "[]"
            idx = draw(st.integers(min_value=0, max_value=len(lst)-1))
            wrong_elem = draw(tag_wrong)
            lst2 = lst[:idx] + [wrong_elem] + lst[idx+1:]
            return "[" + ",".join(lst2) + "]"
        return st.lists(tag_str, min_size=1, max_size=3).flatmap(lambda lst: st.just(build(lst)))
    tags_strategy = st.one_of(tags_correct, tags_mixed())

    # child: null or a nested record (one level only)
    # To avoid infinite recursion, child can be null or a record with all fields correct or with one field wrong
    def child_strategy():
        # child null or a record with one field off
        def record_fields():
            # id always integer string in child (to reduce complexity)
            id_c = st.integers(min_value=0, max_value=2**31-1).map(str)
            amount_c = st.decimals(min_value=0, max_value=1e6, places=2).map(lambda d: format(d, 'f'))
            name_c = st.one_of(st.just("null"), st.text(min_size=0, max_size=10).map(lambda s: '"' + s.replace('"', '\\"') + '"'))
            status_c = st.sampled_from(statuses).map(lambda s: '"' + s + '"')
            tags_c = st.lists(st.text(min_size=1, max_size=5).map(lambda s: '"' + s.replace('"', '\\"') + '"'), min_size=0, max_size=3).map(lambda lst: "[" + ",".join(lst) + "]")
            child_c = st.just("null")

            # Build JSON object string for child
            def build_child(idv, amountv, namev, statusv, tagsv, childv):
                return (
                    '{'
                    + '"id":' + idv + ','
                    + '"amount":"' + amountv + '",'
                    + '"name":' + namev + ','
                    + '"status":' + statusv + ','
                    + '"tags":' + tagsv + ','
                    + '"child":' + childv
                    + '}'
                )

            # Mostly all correct, sometimes one field wrong type (e.g. id as number, amount as number not string)
            # We'll produce a record with one field off or all correct
            # To do this, draw a flag for which field to corrupt or none
            corrupt_field = draw(st.one_of(st.just(None), st.sampled_from(["id", "amount", "name", "status", "tags", "child"])))
            idv = draw(id_c)
            amountv = draw(amount_c)
            namev = draw(name_c)
            statusv = draw(status_c)
            tagsv = draw(tags_c)
            childv = draw(child_c)

            if corrupt_field == "id":
                # id as number (no quotes)
                idv = draw(st.integers(min_value=0, max_value=2**31-1)).map(str).example()
            elif corrupt_field == "amount":
                # amount as number (no quotes)
                amountv = draw(st.decimals(min_value=0, max_value=1e6, places=2)).map(lambda d: format(d, 'f')).example()
            elif corrupt_field == "name":
                # name as number (no quotes)
                namev = draw(st.integers(min_value=0, max_value=100)).map(str).example()
            elif corrupt_field == "status":
                # status as invalid enum without quotes
                statusv = "invalid"
            elif corrupt_field == "tags":
                # tags as null (not array)
                tagsv = "null"
            elif corrupt_field == "child":
                # child as number (not null or object)
                childv = draw(st.integers(min_value=0, max_value=100)).map(str).example()

            return build_child(idv, amountv, namev, statusv, tagsv, childv)

        return st.one_of(st.just("null"), st.deferred(lambda: st.just(record_fields())))

    # Compose top-level record JSON string
    idv = draw(id_strategy)
    amountv = draw(amount_strategy)
    namev = draw(name_strategy)
    statusv = draw(status_strategy)
    tagsv = draw(tags_strategy)
    childv = draw(child_strategy())

    # Compose JSON string carefully
    # id is string but sometimes wrong type (so no quotes around id field value)
    # amount always string (with quotes)
    # name is either null or string (with quotes), but name_strategy returns raw JSON fragment (including quotes or null)
    # status always string (with quotes)
    # tags is JSON array string
    # child is JSON object string or null

    json_str = (
        '{'
        + '"id":' + idv + ','
        + '"amount":"' + amountv + '",'
        + '"name":' + namev + ','
        + '"status":' + statusv + ','
        + '"tags":' + tagsv + ','
        + '"child":' + childv
        + '}'
    )

    return json_str.encode("utf-8")