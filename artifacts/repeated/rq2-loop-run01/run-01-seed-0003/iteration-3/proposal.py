from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants
    STATUS_VALUES = ['active', 'inactive', 'unknown']

    # Helper: JSON string escaper (minimal, escapes backslash and double quote)
    def json_string(s: str) -> str:
        return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

    # Recursive record generator with bounded depth (max 1 level of child)
    def record_strategy(depth=0):
        # id: integer
        id_strat = st.integers(min_value=0, max_value=2**31-1)

        # amount: string (including empty string)
        amount_strat = st.text(min_size=0, max_size=10)

        # name: string or null
        # To induce divergence, allow name to sometimes be a number or boolean (wrong type)
        # but only one or two fields off at a time, so we do this by mixing correct and incorrect types
        name_correct = st.one_of(st.none(), st.text(min_size=0, max_size=10))
        name_wrong = st.one_of(st.integers(), st.booleans())
        # 80% correct, 20% wrong to keep mostly valid with some off
        name_strat = st.one_of(
            name_correct,
            name_wrong
        ).filter(lambda v: True)  # no filter, just to keep type hint

        # status: one of the allowed strings, or sometimes a wrong string or null to induce divergence
        status_correct = st.sampled_from(STATUS_VALUES)
        status_wrong = st.one_of(
            st.text(min_size=1, max_size=10).filter(lambda s: s not in STATUS_VALUES),
            st.none(),
            st.integers(),
            st.booleans()
        )
        # 85% correct, 15% wrong
        status_strat = st.one_of(status_correct, status_wrong)

        # tags: array of strings
        # To induce divergence, sometimes tags is null or array with non-string elements
        tags_correct = st.lists(st.text(min_size=0, max_size=10), max_size=5)
        tags_wrong = st.one_of(
            st.none(),
            st.lists(st.one_of(st.integers(), st.booleans()), max_size=5),
            st.integers(),
            st.booleans()
        )
        tags_strat = st.one_of(tags_correct, tags_wrong)

        # child: either null or a record (only one level recursion)
        if depth == 0:
            child_strat = st.one_of(st.none(), record_strategy(depth=1))
        else:
            # At depth 1, child must be null (no deeper recursion)
            child_strat = st.none()

        # Compose record dict with all fields present
        # To induce divergence, sometimes omit a field by replacing with None and then omit in JSON text
        # But problem states all six fields always present in well-formed document,
        # so we keep all fields present but vary types/values.

        # Draw all fields
        id_v = draw(id_strat)
        amount_v = draw(amount_strat)
        name_v = draw(name_strat)
        status_v = draw(status_strat)
        tags_v = draw(tags_strat)
        child_v = draw(child_strat)

        # Build JSON text for each field, carefully encoding types and nulls

        def json_val(v):
            if v is None:
                return "null"
            elif isinstance(v, bool):
                return "true" if v else "false"
            elif isinstance(v, int):
                return str(v)
            elif isinstance(v, str):
                return json_string(v)
            elif isinstance(v, list):
                # list of strings or wrong types
                elems = [json_val(e) for e in v]
                return "[" + ",".join(elems) + "]"
            elif isinstance(v, dict):
                # nested record
                # Should not happen here, child_v is record dict or None
                # But we build child_v as JSON text already, so this case unused
                return "{}"
            else:
                # fallback: treat as string
                return json_string(str(v))

        # child_v is either None or a dict with same fields
        # But we built child_v as JSON text string, so we must build child JSON recursively here
        # Actually, child_v is the output of record_strategy(depth=1), so it's a JSON string bytes
        # We must draw child_v as JSON text string, so we must build child JSON text recursively

        # To fix this, change record_strategy to return JSON text string, not dict

        # So let's rewrite record_strategy to return JSON text string, not dict

    # Redefine record_strategy to return JSON text string (str), not dict

    def record_strategy(depth=0):
        id_strat = st.integers(min_value=0, max_value=2**31-1)
        amount_strat = st.text(min_size=0, max_size=10)

        name_correct = st.one_of(st.none(), st.text(min_size=0, max_size=10))
        name_wrong = st.one_of(st.integers(), st.booleans())
        name_strat = st.one_of(name_correct, name_wrong)

        status_correct = st.sampled_from(STATUS_VALUES)
        status_wrong = st.one_of(
            st.text(min_size=1, max_size=10).filter(lambda s: s not in STATUS_VALUES),
            st.none(),
            st.integers(),
            st.booleans()
        )
        status_strat = st.one_of(status_correct, status_wrong)

        tags_correct = st.lists(st.text(min_size=0, max_size=10), max_size=5)
        tags_wrong = st.one_of(
            st.none(),
            st.lists(st.one_of(st.integers(), st.booleans()), max_size=5),
            st.integers(),
            st.booleans()
        )
        tags_strat = st.one_of(tags_correct, tags_wrong)

        if depth == 0:
            child_strat = st.one_of(st.just("null"), record_strategy(depth=1))
        else:
            child_strat = st.just("null")

        @st.composite
        def build_record(draw_inner):
            id_v = draw_inner(id_strat)
            amount_v = draw_inner(amount_strat)
            name_v = draw_inner(name_strat)
            status_v = draw_inner(status_strat)
            tags_v = draw_inner(tags_strat)
            child_v = draw_inner(child_strat)

            def json_val(v):
                if v is None:
                    return "null"
                elif isinstance(v, bool):
                    return "true" if v else "false"
                elif isinstance(v, int):
                    return str(v)
                elif isinstance(v, str):
                    return json_string(v)
                elif isinstance(v, list):
                    elems = [json_val(e) for e in v]
                    return "[" + ",".join(elems) + "]"
                else:
                    # fallback to string
                    return json_string(str(v))

            # Compose JSON text for record fields
            parts = [
                '"id":' + str(id_v),
                '"amount":' + json_val(amount_v),
                '"name":' + json_val(name_v),
                '"status":' + json_val(status_v),
                '"tags":' + json_val(tags_v),
                '"child":' + child_v,
            ]
            return "{" + ",".join(parts) + "}"

        return build_record()

    # Draw top-level record JSON text string
    json_text = draw(record_strategy(depth=0))

    # Return bytes
    return json_text.encode("utf-8")