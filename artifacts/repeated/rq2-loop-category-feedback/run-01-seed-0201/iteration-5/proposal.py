```python
from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for enum and tags
    STATUS_VALUES = ["active", "inactive", "unknown"]
    # To increase chance of bad_enum, add some invalid enum strings sometimes
    BAD_STATUS_VALUES = ["active", "inactive", "unknown", "actve", "inactiv", "UNKNOWN", "123", "", "null"]

    # Helper: generate id near boundary or normal
    def id_strategy():
        # 53-bit boundary: 2**53 = 9007199254740992
        # 64-bit boundary: 2**63 = 9223372036854775808
        # Include some near boundaries, some normal small ints, some large ints beyond 64-bit
        boundary_near = st.one_of(
            st.integers(min_value=9007199254740990, max_value=9007199254741000),
            st.integers(min_value=9223372036854775800, max_value=9223372036854775810),
            st.integers(min_value=2**64, max_value=2**64 + 1000),
        )
        normal_small = st.integers(min_value=0, max_value=1000000)
        # Mix with some negative or zero to test rejection (not in schema but might cause divergence)
        negative = st.integers(min_value=-1000, max_value=-1)
        # 50% chance boundary near, 40% normal, 10% negative
        return st.one_of(boundary_near, normal_small, negative).map(int)

    # amount: string, but try normal decimal strings, empty string, or weird strings
    def amount_strategy():
        # normal decimal strings, possibly with leading zeros or +/-
        normal = st.one_of(
            st.decimals(min_value=0, max_value=1e9, allow_nan=False, allow_infinity=False).map(lambda d: format(d, 'f')),
            st.just("0"),
            st.just("000123.45"),
            st.just("+123.45"),
            st.just("-0.01"),
        )
        # weird strings that look like numbers but invalid: "1e9999", "NaN", "inf", "123abc"
        weird = st.sampled_from(["1e9999", "NaN", "inf", "123abc", "", " ", "0x123", "1_000"])
        # 80% normal, 20% weird
        return st.one_of(normal, weird)

    # name: string or null, but sometimes null override even if normally string
    def name_strategy():
        # normal string or null
        normal = st.one_of(st.none(), st.text(min_size=0, max_size=20))
        # sometimes empty string or whitespace only
        weird = st.sampled_from([None, "", " ", "\n", "\t"])
        # 70% normal, 30% weird
        return st.one_of(normal, weird)

    # status: mostly valid enum, sometimes bad enum string
    def status_strategy():
        # 80% valid, 20% invalid
        return st.one_of(
            st.sampled_from(STATUS_VALUES),
            st.sampled_from(BAD_STATUS_VALUES),
        )

    # tags: array of strings, sometimes empty, sometimes with null or wrong types
    def tags_strategy():
        # normal: list of 0-5 strings (ascii printable)
        normal = st.lists(st.text(min_size=0, max_size=10), min_size=0, max_size=5)
        # sometimes include null or wrong types (int, bool)
        weird_element = st.one_of(st.text(min_size=0, max_size=10), st.none(), st.integers(), st.booleans())
        weird = st.lists(weird_element, min_size=0, max_size=5)
        # 80% normal, 20% weird
        return st.one_of(normal, weird)

    # child: either null or a nested record (one level recursion normally)
    # To increase chance of divergence, sometimes go deeper (up to 3 levels)
    # or put null_override or missing fields inside child
    def child_strategy(depth=0):
        if depth >= 2:
            # max depth reached, only null or simple child
            return st.one_of(st.none(), st.just(None))
        else:
            # Either null or nested record
            # To increase chance of missing_field or null_override in child, sometimes omit fields or set null
            # But schema says all six fields always present in well-formed document,
            # so missing_field is unusual and might cause divergence
            # We produce syntactically valid JSON objects only, so missing_field means omit key entirely
            # We'll produce either full record or partial record with missing fields
            def record_fields():
                # id always present (to avoid structural reject)
                id_val = id_strategy()
                # amount always present
                amount_val = amount_strategy()
                # name sometimes null_override or missing
                name_val = st.one_of(name_strategy(), st.just(None))
                # status sometimes bad enum or missing
                status_val = status_strategy()
                # tags sometimes weird or missing
                tags_val = tags_strategy()
                # child nested one level deeper or null
                child_val = child_strategy(depth + 1)

                # Compose dict with all fields
                full_record = st.tuples(id_val, amount_val, name_val, status_val, tags_val, child_val)

                # To produce missing_field, randomly omit 0-2 keys (except id which is mandatory)
                def build_json_obj(tpl):
                    (id_v, amount_v, name_v, status_v, tags_v, child_v) = tpl
                    keys = ["id", "amount", "name", "status", "tags", "child"]
                    values = [id_v, amount_v, name_v, status_v, tags_v, child_v]
                    # id mandatory, so omit from omit list
                    omit_candidates = ["amount", "name", "status", "tags", "child"]
                    omit_count = draw(st.integers(min_value=0, max_value=2))
                    omit_keys = draw(st.sampled_from(omit_candidates).flatmap(lambda k: st.just([k]) if omit_count == 1 else st.lists(st.sampled_from(omit_candidates), min_size=omit_count, max_size=omit_count))) if omit_count > 0 else []
                    # flatten if list of lists
                    if isinstance(omit_keys, list) and any(isinstance(x, list) for x in omit_keys):
                        omit_keys = [item for sublist in omit_keys for item in sublist]
                    omit_keys = list(set(omit_keys))  # unique keys to omit

                    # Build JSON string manually
                    parts = []
                    for k, v in zip(keys, values):
                        if k in omit_keys:
                            continue
                        # Serialize value to JSON string
                        if k == "id":
                            # id is integer
                            parts.append(f'"id":{v}')
                        elif k == "amount":
                            # amount is string, escape quotes
                            s = v.replace('\\', '\\\\').replace('"', '\\"')
                            parts.append(f'"amount":"{s}"')
                        elif k == "name":
                            if v is None:
                                parts.append(f'"name":null')
                            else:
                                s = v.replace('\\', '\\\\').replace('"', '\\"')
                                parts.append(f'"name":"{s}"')
                        elif k == "status":
                            s = v.replace('\\', '\\\\').replace('"', '\\"')
                            parts.append(f'"status":"{s}"')
                        elif k == "tags":
                            # tags is array of strings, but may contain null or wrong types
                            # Serialize array manually
                            arr_parts = []
                            for e in v:
                                if e is None:
                                    arr_parts.append("null")
                                elif isinstance(e, bool):
                                    arr_parts.append("true" if e else "false")
                                elif isinstance(e, int):
                                    arr_parts.append(str(e))
                                else:
                                    # string
                                    s = e.replace('\\', '\\\\').replace('"', '\\"')
                                    arr_parts.append(f'"{s}"')
                            parts.append(f'"tags":[{",".join(arr_parts)}]')
                        elif k == "child":
                            if v is None:
                                parts.append(f'"child":null')
                            else:
                                # v is bytes from child_strategy(depth+1), decode to str
                                # But here v is a Hypothesis value, not bytes, so we must recursively build JSON string
                                # Actually, child_strategy returns bytes, so we must decode
                                # But we are inside build_json_obj, which is inside draw, so v is a Hypothesis value, not bytes
                                # So we must call child_strategy(depth+1) here to get bytes, but we can't call draw here
                                # Instead, we will produce child JSON string by calling a helper function
                                # To avoid complexity, we will produce child JSON string by calling draw(child_strategy(depth+1)) here
                                # But this is not allowed inside build_json_obj (not a @composite)
                                # So we must redesign: build_json_obj must be a @composite or we must produce child JSON string outside
                                # To fix this, we will produce child JSON string outside build_json_obj and pass it in as string
                                # So change full_record to produce child JSON string, not raw value
                                raise NotImplementedError("child serialization inside build_json_obj not supported")
                    return "{" + ",".join(parts) + "}"

                # Because of above complexity, we redesign: produce child JSON string first, then produce full record string

                return full_record

            # Compose full record with child JSON string
            # We must produce child JSON string first
            child_json = draw(st.one_of(st.just("null"), generated_json(depth=depth+1).map(lambda b: b.decode("utf-8")))) if depth < 2 else "null"

            # Now produce other fields
            id_v = draw(id_strategy())
            amount_v = draw(amount_strategy())
            name_v = draw(name_strategy())
            status_v = draw(status_strategy())
            tags_v = draw(tags_strategy())

            # To produce missing_field, randomly omit 0-2 keys except id
            omit_candidates = ["amount", "name", "status", "tags", "child"]
            omit_count = draw(st.integers(min_value=0, max_value=2))
            omit_keys = draw(st.lists(st.sampled_from(omit_candidates), min_size=omit_count, max_size=omit_count, unique=True)) if omit_count > 0 else []

            parts = []
            parts.append(f'"id":{id_v}')
            if "amount" not in omit_keys:
                s = amount_v.replace('\\', '\\\\').replace('"', '\\"')
                parts.append(f'"amount":"{s}"')
            if "name" not in omit_keys:
                if name_v is None:
                    parts.append(f'"name":null')
                else:
                    s = name_v.replace('\\', '\\\\').replace('"', '\\"')
                    parts.append(f'"name":"{s}"')
            if "status" not in omit_keys:
                s = status_v.replace('\\', '\\\\').replace('"', '\\"')
                parts.append(f'"status":"{s}"')
            if "tags" not in omit_keys:
                arr_parts = []
                for e in tags_v:
                    if e is None:
                        arr_parts.append("null")
                    elif isinstance(e, bool):
                        arr_parts.append("true" if e else "false")
                    elif isinstance(e, int):
                        arr_parts.append(str(e