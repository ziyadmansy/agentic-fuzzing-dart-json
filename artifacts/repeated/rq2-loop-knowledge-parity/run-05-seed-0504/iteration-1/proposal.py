from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status
    statuses = ["active", "inactive", "unknown"]

    # Helper: JSON string escaping minimal (only backslash and quote)
    def json_string(s: str) -> str:
        # Escape backslash and double quote only
        return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

    # Recursive record generator with bounded depth (max 1 level recursion)
    def record(depth: int) -> st.SearchStrategy[str]:
        # id: integer or (for divergence) a double that .toInt() accepts (json_serializable/freezed)
        # We produce either an int literal or a double literal representing an int (e.g. 42.0)
        # or a double outside int64 range to trigger saturation in json_serializable/freezed
        def id_strat():
            # Choose one of three id representations:
            # 1) int literal in int64 range (accepted by all)
            # 2) double literal with .0 fractional part in int64 range (accepted by json_serializable/freezed, rejected by manual/built_value)
            # 3) double literal outside int64 range (to test saturation)
            int64_min = -2**63
            int64_max = 2**63 - 1

            choice = draw(st.integers(min_value=1, max_value=3))
            if choice == 1:
                # int literal in range
                v = draw(st.integers(min_value=int64_min, max_value=int64_max))
                return str(v)
            elif choice == 2:
                # double literal with .0 fractional part in range
                v = draw(st.integers(min_value=int64_min, max_value=int64_max))
                # Represent as float literal with .0
                return str(float(v))
            else:
                # double literal outside int64 range (e.g. int64_max+1000.0 or int64_min-1000.0)
                # Use float literal with .0 fractional part
                if draw(st.booleans()):
                    v = int64_max + draw(st.integers(min_value=1, max_value=10000))
                else:
                    v = int64_min - draw(st.integers(min_value=1, max_value=10000))
                return str(float(v))

        # amount: string, always present, non-null
        amount = draw(st.text(min_size=1, max_size=20))
        amount_json = json_string(amount)

        # name: string or null (nullable)
        name_val = draw(st.one_of(st.none(), st.text(max_size=20)))
        name_json = "null" if name_val is None else json_string(name_val)

        # status: one of known strings or (for divergence) an unknown string (to test rejection)
        # But unknown status is rejected by all, so no divergence there.
        # So only known statuses here.
        status_val = draw(st.sampled_from(statuses))
        status_json = json_string(status_val)

        # tags: array of strings, always present
        # To test divergence, sometimes omit tags field (built_value accepts, others reject)
        # But per hint, vary one or two things at a time, so sometimes omit tags
        omit_tags = draw(st.booleans())
        # tags array elements: strings, possibly empty array
        tags_list = draw(st.lists(st.text(max_size=10), max_size=5))
        tags_json = "[" + ",".join(json_string(t) for t in tags_list) + "]"

        # child: null or a record (one level recursion max)
        if depth >= 1:
            # At max depth, child must be null (to avoid deep recursion)
            child_json = "null"
        else:
            # child nullable: null or record(depth+1)
            child_val = draw(st.one_of(st.just(None), record(depth + 1)))
            child_json = "null" if child_val is None else child_val

        # Compose fields in a dict, possibly omitting tags to test divergence
        # Always include id, amount, name, status, child
        # tags omitted if omit_tags==True
        # Also, to test divergence on missing tags, omit tags only sometimes
        fields = []
        fields.append('"id":' + id_strat())
        fields.append('"amount":' + amount_json)
        fields.append('"name":' + name_json)
        fields.append('"status":' + status_json)
        if not omit_tags:
            fields.append('"tags":' + tags_json)
        fields.append('"child":' + child_json)

        # Shuffle fields order for variety
        # But Hypothesis does not have a shuffle for lists of strings directly,
        # so just keep order fixed for simplicity (order of keys in JSON object does not matter)
        obj_json = "{" + ",".join(fields) + "}"

        return obj_json

    # Draw the top-level record with depth=0
    json_text = draw(record(0))
    return json_text.encode("utf-8")