from hypothesis import strategies as st

# Helper: JSON string escaping for double quotes and backslashes only (minimal)
def json_escape(s: str) -> str:
    # minimal escaping for JSON strings: backslash and double quote
    return s.replace('\\', '\\\\').replace('"', '\\"')

@st.composite
def generated_json(draw) -> bytes:
    # We want to produce JSON objects with the given schema:
    # {
    #   "id": <integer>,
    #   "amount": <string>,
    #   "name": <string or null>,
    #   "status": <one of "active", "inactive", "unknown">,
    #   "tags": <array of strings>,
    #   "child": <Record or null, one level recursion normally>
    # }
    #
    # We want to bias towards:
    # - wrong_type (13 last iteration)
    # - extra_key (12 last iteration)
    # Also vary one or two things at a time.
    #
    # We will produce a JSON string (bytes) representing the object.
    #
    # We will do bounded recursion for child (max depth 2).
    #
    # We will sometimes produce wrong types for fields, or extra keys.
    #
    # We will produce syntactically valid JSON only.
    #
    # We will produce strings with minimal escaping.
    #
    # We will produce integers for id near boundaries sometimes.
    #
    # We will produce bad enum values sometimes.
    #
    # We will produce null overrides sometimes.
    #
    # We will produce extra keys sometimes.
    #
    # We will produce wrong types sometimes.
    #
    # We will produce deep nesting sometimes (up to 3 levels).
    #
    # We will produce missing fields rarely (not prioritized).
    #
    # We will produce arrays of strings for tags, sometimes empty.
    #
    # We will produce amount as string normally, but sometimes wrong type.
    #
    # We will produce name as string or null, sometimes wrong type.
    #
    # We will produce child as null or nested record, sometimes wrong type.
    #
    # We will produce status as enum string, sometimes bad enum string.
    #
    # We will produce extra keys sometimes.
    #
    # We will produce one or two anomalies per document.

    # Constants
    STATUSES = ["active", "inactive", "unknown"]
    BAD_STATUSES = ["", "ACTIVE", "inactiv", "null", "123", "act ive", "unknown "]

    # Helper to produce a JSON string literal from a Python string
    def json_str(s: str) -> str:
        return '"' + json_escape(s) + '"'

    # Helper to produce JSON array of strings
    def json_array_of_strings(strs):
        # strs is list of strings
        return '[' + ','.join(json_str(s) for s in strs) + ']'

    # Recursive record generator with depth limit
    def gen_record(depth: int):
        # Decide anomalies to apply (0,1 or 2 anomalies)
        anomalies = draw(st.lists(st.sampled_from([
            "wrong_type_id",
            "wrong_type_amount",
            "wrong_type_name",
            "wrong_type_status",
            "wrong_type_tags",
            "wrong_type_child",
            "bad_enum_status",
            "null_override_name",
            "null_override_child",
            "extra_key",
            "boundary_id",
            "deep_nesting",
        ]), max_size=2, unique=True))

        # id field
        if "wrong_type_id" in anomalies:
            # id as string or float or null instead of integer
            id_val = draw(st.one_of(
                st.text(min_size=1, max_size=5),
                st.floats(allow_nan=False, allow_infinity=False),
                st.none()
            ))
            if isinstance(id_val, float):
                id_json = str(id_val)
            elif id_val is None:
                id_json = "null"
            else:
                id_json = json_str(id_val)
        else:
            # integer id, sometimes near 53-bit boundary or 64-bit boundary
            boundary_choice = draw(st.sampled_from(["normal", "near_53bit", "near_64bit"]))
            if boundary_choice == "normal":
                id_val = draw(st.integers(min_value=0, max_value=10**9))
            elif boundary_choice == "near_53bit":
                # 2^53 = 9007199254740992
                id_val = draw(st.integers(min_value=9007199254740990, max_value=9007199254741000))
            else:
                # 2^63 = 9223372036854775808
                id_val = draw(st.integers(min_value=9223372036854775800, max_value=9223372036854775810))
            id_json = str(id_val)

        # amount field
        if "wrong_type_amount" in anomalies:
            # amount as number or null instead of string
            amount_val = draw(st.one_of(
                st.integers(min_value=-1000, max_value=1000),
                st.floats(allow_nan=False, allow_infinity=False),
                st.none()
            ))
            if amount_val is None:
                amount_json = "null"
            else:
                amount_json = str(amount_val)
        else:
            # amount as string, possibly numeric string or weird string
            amount_str = draw(st.one_of(
                st.text(min_size=1, max_size=10),
                st.from_regex(r"^-?\d+(\.\d+)?$", fullmatch=True),
            ))
            amount_json = json_str(amount_str)

        # name field
        if "wrong_type_name" in anomalies:
            # name as number or bool instead of string or null
            name_val = draw(st.one_of(
                st.integers(min_value=-1000, max_value=1000),
                st.booleans(),
            ))
            if isinstance(name_val, bool):
                name_json = "true" if name_val else "false"
            else:
                name_json = str(name_val)
        else:
            # name as string or null
            if "null_override_name" in anomalies:
                name_json = "null"
            else:
                name_str = draw(st.one_of(
                    st.none(),
                    st.text(min_size=0, max_size=10),
                ))
                if name_str is None:
                    name_json = "null"
                else:
                    name_json = json_str(name_str)

        # status field
        if "wrong_type_status" in anomalies:
            # status as number or bool instead of string enum
            status_val = draw(st.one_of(
                st.integers(min_value=0, max_value=10),
                st.booleans(),
            ))
            if isinstance(status_val, bool):
                status_json = "true" if status_val else "false"
            else:
                status_json = str(status_val)
        else:
            if "bad_enum_status" in anomalies:
                status_str = draw(st.sampled_from(BAD_STATUSES))
            else:
                status_str = draw(st.sampled_from(STATUSES))
            status_json = json_str(status_str)

        # tags field
        if "wrong_type_tags" in anomalies:
            # tags as string or number instead of array of strings
            tags_val = draw(st.one_of(
                st.text(min_size=0, max_size=10),
                st.integers(min_value=0, max_value=100),
                st.none(),
            ))
            if tags_val is None:
                tags_json = "null"
            elif isinstance(tags_val, int):
                tags_json = str(tags_val)
            else:
                tags_json = json_str(tags_val)
        else:
            # tags as array of strings, possibly empty
            tags_list = draw(st.lists(st.text(min_size=0, max_size=10), max_size=5))
            tags_json = json_array_of_strings(tags_list)

        # child field
        if "wrong_type_child" in anomalies:
            # child as string or number instead of record or null
            child_val = draw(st.one_of(
                st.text(min_size=0, max_size=10),
                st.integers(min_value=0, max_value=100),
                st.booleans(),
            ))
            if isinstance(child_val, bool):
                child_json = "true" if child_val else "false"
            elif isinstance(child_val, int):
                child_json = str(child_val)
            else:
                child_json = json_str(child_val)
        else:
            # child as null or nested record (depth limit 2 normally, but allow 3 if deep_nesting)
            if "null_override_child" in anomalies:
                child_json = "null"
            else:
                if depth >= 2 and "deep_nesting" not in anomalies:
                    # max depth reached, child null
                    child_json = "null"
                else:
                    # child is null or nested record
                    child_is_null = draw(st.booleans())
                    if child_is_null:
                        child_json = "null"
                    else:
                        # recurse with depth+1
                        child_json = gen_record(depth + 1)
                        # child_json is string, no quotes needed
        # Compose fields into JSON object string
        # Compose fields in order: id, amount, name, status, tags, child

        fields = [
            ('"id"', id_json),
            ('"amount"', amount_json),
            ('"name"', name_json),
            ('"status"', status_json),
            ('"tags"', tags_json),
            ('"child"', child_json),
        ]

        # Add extra key sometimes (only one extra key)
        if "extra_key" in anomalies:
            # extra key with random name and value
            extra_key_name = draw(st.text(min_size=1, max_size=5))
            extra_key_name_json = json_str(extra_key_name)
            # extra key value as string or number or null
            extra_key_val = draw(st.one_of(
                st.text(min_size=0, max_size=10),
                st.integers(min_value=-1000, max_value=1000),
                st.none(),
            ))
            if extra_key_val is None:
                extra_key_val_json = "null"
            elif isinstance(extra_key_val, int):
                extra_key_val_json = str(extra_key_val)
            else:
                extra_key_val_json = json_str(extra_key_val)
            fields.append((extra_key_name_json, extra_key_val_json))

        # Build JSON object string
        obj_str = '{' + ','.join(f'{k}:{v}' for k, v in fields) + '}'
        return obj_str

    # Generate top-level record with depth=0
    json_str_obj = gen_record(0)
    # Return bytes
    return json_str_obj.encode('utf-8')