from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status field
    statuses = ["active", "inactive", "unknown"]

    # Helper: produce a JSON string literal with proper escaping of quotes and backslashes
    def json_string(s: str) -> str:
        # minimal escaping for " and \, no control chars for simplicity
        s = s.replace("\\", "\\\\").replace('"', '\\"')
        return '"' + s + '"'

    # Recursive generator for the "child" field, bounded to depth 1 (one level recursion)
    # We produce a JSON object string or "null"
    def gen_record(depth: int) -> st.SearchStrategy[str]:
        # At depth 1, child must be null (no further recursion)
        if depth > 1:
            return st.just("null")

        # id: integer, but we will sometimes produce wrong types or boundary values
        # amount: string, but sometimes wrong type or boundary strings
        # name: string or null, sometimes wrong type or missing
        # status: one of the three strings, sometimes wrong string or wrong type
        # tags: array of strings, sometimes empty, sometimes wrong type or wrong element types
        # child: record or null (one level recursion)

        # For each field, produce a strategy that sometimes produces a valid value,
        # sometimes an invalid variant to provoke divergence.

        # id: mostly integer, sometimes string or float or missing (missing means field omitted)
        id_strat = st.one_of(
            st.integers(min_value=-2**31, max_value=2**31-1).map(str),
            st.text(min_size=1, max_size=5).filter(lambda x: not x.isdigit()),  # invalid string
            st.floats(allow_infinity=False, allow_nan=False).map(lambda f: str(f)),
        )

        # amount: mostly string representing a decimal number, sometimes number or null or empty string
        amount_strat = st.one_of(
            st.text(min_size=1, max_size=10).filter(lambda s: all(c in "0123456789.-" for c in s)),
            st.integers(min_value=-10000, max_value=10000).map(str),
            st.just("null"),
            st.just(""),
        )

        # name: string or null, sometimes number or boolean or missing
        name_strat = st.one_of(
            st.none().map(lambda _: "null"),
            st.text(min_size=0, max_size=10).map(json_string),
            st.integers(min_value=0, max_value=100).map(str),
            st.sampled_from(["true", "false"]),
        )

        # status: mostly one of the three strings, sometimes wrong string or number or null
        status_strat = st.one_of(
            st.sampled_from(statuses).map(json_string),
            st.text(min_size=1, max_size=7).filter(lambda s: s not in statuses).map(json_string),
            st.integers(min_value=0, max_value=10).map(str),
            st.just("null"),
        )

        # tags: array of strings, sometimes array with non-string elements, sometimes null or empty array
        tags_strat = st.one_of(
            st.lists(st.text(min_size=1, max_size=5), min_size=0, max_size=5).map(
                lambda lst: "[" + ",".join(json_string(s) for s in lst) + "]"
            ),
            st.lists(st.integers(min_value=0, max_value=10).map(str), min_size=0, max_size=5).map(
                lambda lst: "[" + ",".join(lst) + "]"
            ),
            st.just("null"),
        )

        # child: either null or a nested record (depth+1)
        child_strat = st.one_of(
            st.just("null"),
            gen_record(depth + 1),
        )

        # Compose fields, sometimes omit one field to provoke missing field cases
        # We'll produce a dict of field_name -> json string (including quotes for strings)
        # Then serialize as JSON object string.

        # To provoke divergence, randomly omit one field or produce wrong type for one field.
        # But never omit more than one field at once.

        # Decide which field to "corrupt" or omit, or none
        corrupt_field = draw(st.one_of(
            st.just(None),
            st.sampled_from(["id", "amount", "name", "status", "tags", "child"]),
        ))

        # Draw all fields
        id_val = draw(id_strat)
        amount_val = draw(amount_strat)
        name_val = draw(name_strat)
        status_val = draw(status_strat)
        tags_val = draw(tags_strat)
        child_val = draw(child_strat)

        fields = {}

        # Helper to add field if not omitted
        def add_field(k, v):
            if corrupt_field != k:
                fields[k] = v

        # Add fields, except the corrupted one which we omit or replace with invalid
        if corrupt_field == "id":
            # omit or produce invalid id (already drawn invalid id_val)
            # Here omit means skip field entirely
            # To provoke divergence, sometimes omit, sometimes invalid type
            # We omit here by skipping add_field
            pass
        else:
            add_field("id", id_val)

        if corrupt_field == "amount":
            # omit or invalid amount_val (already drawn)
            pass
        else:
            add_field("amount", amount_val)

        if corrupt_field == "name":
            # omit or invalid name_val (already drawn)
            pass
        else:
            add_field("name", name_val)

        if corrupt_field == "status":
            # omit or invalid status_val
            pass
        else:
            add_field("status", status_val)

        if corrupt_field == "tags":
            # omit or invalid tags_val
            pass
        else:
            add_field("tags", tags_val)

        if corrupt_field == "child":
            # omit or invalid child_val
            pass
        else:
            add_field("child", child_val)

        # If we omitted a field, that's it.
        # If we want to produce an invalid value instead of omission, we can do that by
        # corrupt_field is set but we still add the field with invalid value.
        # To do that, we can randomly decide to omit or keep invalid.

        # But above we omit the field if corrupt_field == field name.
        # Let's instead sometimes omit, sometimes keep invalid.

        # Let's fix that logic: if corrupt_field is set, 50% chance omit, 50% chance keep invalid.

        if corrupt_field is not None:
            omit = draw(st.booleans())
            if omit:
                # Omit field: already done by skipping add_field above
                pass
            else:
                # Keep invalid value: add corrupted field with invalid value
                # We already drew invalid values for all fields except child (child is recursive)
                # So add corrupted field now:
                if corrupt_field == "id":
                    fields["id"] = id_val
                elif corrupt_field == "amount":
                    fields["amount"] = amount_val
                elif corrupt_field == "name":
                    fields["name"] = name_val
                elif corrupt_field == "status":
                    fields["status"] = status_val
                elif corrupt_field == "tags":
                    fields["tags"] = tags_val
                elif corrupt_field == "child":
                    fields["child"] = child_val

        # Compose JSON object string
        # Fields order fixed for consistency
        field_order = ["id", "amount", "name", "status", "tags", "child"]
        parts = []
        for f in field_order:
            if f in fields:
                parts.append(json_string(f) + ":" + fields[f])
        json_obj = "{" + ",".join(parts) + "}"

        return json_obj

    # Generate top-level record (depth 0)
    json_text = draw(gen_record(0))

    # Return bytes
    return json_text.encode("utf-8")