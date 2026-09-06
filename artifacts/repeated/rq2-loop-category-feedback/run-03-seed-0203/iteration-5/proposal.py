from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status enum
    statuses = ["active", "inactive", "unknown"]

    # Base valid field strategies
    id_strat = st.integers(min_value=0, max_value=2**31-1)
    amount_strat = st.text(min_size=0, max_size=10)  # string, can be empty
    # name can be string or null
    name_strat = st.one_of(st.none(), st.text(min_size=0, max_size=10))
    status_strat = st.sampled_from(statuses)
    # tags: array of strings, length 0-3, strings length 0-10
    tags_strat = st.lists(st.text(min_size=0, max_size=10), min_size=0, max_size=3)

    # To induce divergences, we will:
    # - sometimes replace a field with a wrong type (e.g. number instead of string)
    # - sometimes omit a field (though schema says all fields always present, some impls might tolerate missing)
    # - sometimes put null where not expected (e.g. tags=null)
    # - sometimes put empty string where enum expected
    # - sometimes put enum as uppercase or with trailing spaces (should be rejected)
    # - sometimes put child as null or a nested record (bounded recursion depth 1)
    # - sometimes put child as wrong type (string or number)
    # - sometimes put tags as null or a single string instead of array
    # - sometimes put amount as number instead of string

    # We will build a helper to generate a record at depth 0 or 1

    def record(depth):
        # At depth 1, child must be null (no deeper recursion)
        # We generate fields with a small chance of type errors or boundary values

        # id: mostly integer, sometimes string or null
        id_field = draw(
            st.one_of(
                id_strat.map(str),  # string instead of int (wrong type)
                id_strat,
                st.none(),
            )
        )

        # amount: mostly string, sometimes number or null
        amount_field = draw(
            st.one_of(
                amount_strat,
                st.integers(min_value=-1000, max_value=1000).map(str),  # numeric string
                st.integers(min_value=-1000, max_value=1000),  # number (wrong type)
                st.none(),
                st.just(""),  # empty string allowed
            )
        )

        # name: string or null, sometimes number or boolean (wrong type)
        name_field = draw(
            st.one_of(
                name_strat,
                st.integers(min_value=0, max_value=10),
                st.booleans(),
            )
        )

        # status: mostly correct enum, sometimes uppercase, trailing spaces, empty string, null, or number
        status_field = draw(
            st.one_of(
                status_strat,
                st.sampled_from([s.upper() for s in statuses]),
                status_strat.map(lambda s: s + " "),
                st.just(""),
                st.none(),
                st.integers(min_value=0, max_value=2),
            )
        )

        # tags: mostly list of strings, sometimes null, sometimes single string, sometimes number
        tags_field = draw(
            st.one_of(
                tags_strat,
                st.none(),
                st.text(min_size=0, max_size=10),
                st.integers(min_value=0, max_value=10),
            )
        )

        # child: at depth 0, can be null or a record at depth 1 or wrong type
        # at depth 1, must be null or wrong type (no deeper recursion)
        if depth == 0:
            child_field = draw(
                st.one_of(
                    st.none(),
                    record(1),
                    st.text(min_size=0, max_size=10),
                    st.integers(min_value=0, max_value=10),
                    st.booleans(),
                )
            )
        else:
            child_field = draw(
                st.one_of(
                    st.none(),
                    st.text(min_size=0, max_size=10),
                    st.integers(min_value=0, max_value=10),
                    st.booleans(),
                )
            )

        # Compose JSON text for this record
        # We must produce syntactically valid JSON objects only

        def json_str(val):
            # val can be None, int, bool, str, list, or dict (record)
            if val is None:
                return "null"
            elif isinstance(val, bool):
                return "true" if val else "false"
            elif isinstance(val, int):
                return str(val)
            elif isinstance(val, str):
                # Escape quotes and backslashes minimally
                esc = val.replace("\\", "\\\\").replace('"', '\\"')
                return f'"{esc}"'
            elif isinstance(val, list):
                inner = ",".join(json_str(v) for v in val)
                return f"[{inner}]"
            elif isinstance(val, dict):
                # dict with keys: id, amount, name, status, tags, child
                # keys always present, values are JSON text
                parts = []
                for k in ["id", "amount", "name", "status", "tags", "child"]:
                    parts.append(f'"{k}":{json_str(val[k])}')
                return "{" + ",".join(parts) + "}"
            else:
                # fallback: convert to string quoted
                return json_str(str(val))

        # Build dict for this record
        rec_dict = {
            "id": id_field,
            "amount": amount_field,
            "name": name_field,
            "status": status_field,
            "tags": tags_field,
            "child": child_field,
        }

        # If child is a record (dict), it is already a JSON string, so we must parse it to dict
        # But we built child_field as JSON string only at depth 1, so here child_field is a dict
        # Actually, child_field is a dict only if record() returned a dict, else a primitive
        # So we keep child_field as dict or primitive, no JSON string yet

        # So rec_dict is a dict with values as primitives or dicts or lists

        return rec_dict

    # Draw top-level record dict
    top_rec = draw(record(0))

    # Convert top_rec dict to JSON text string
    def json_str(val):
        if val is None:
            return "null"
        elif isinstance(val, bool):
            return "true" if val else "false"
        elif isinstance(val, int):
            return str(val)
        elif isinstance(val, str):
            esc = val.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{esc}"'
        elif isinstance(val, list):
            inner = ",".join(json_str(v) for v in val)
            return f"[{inner}]"
        elif isinstance(val, dict):
            parts = []
            for k in ["id", "amount", "name", "status", "tags", "child"]:
                parts.append(f'"{k}":{json_str(val[k])}')
            return "{" + ",".join(parts) + "}"
        else:
            return json_str(str(val))

    json_text = json_str(top_rec)
    return json_text.encode("utf-8")