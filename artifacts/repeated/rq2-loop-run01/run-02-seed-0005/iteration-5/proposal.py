from hypothesis import strategies as st

# Helper: produce JSON string literal from Python string (no escapes except \")
def json_string_literal(s: str) -> str:
    # minimal escaping: replace " and \ with \"
    # Hypothesis strings won't contain control chars by default, so minimal escaping is enough
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

@st.composite
def generated_json(draw) -> bytes:
    """
    Generate syntactically valid JSON objects matching the schema, but with
    exactly one or two subtle deviations from the schema to provoke divergence
    between four Dart JSON deserializers.

    Schema:
    {
      "id": <integer>,
      "amount": <string>,
      "name": <string or null>,
      "status": <one of "active", "inactive", "unknown">,
      "tags": <array of strings>,
      "child": <Record or null, one level recursion>
    }

    Strategy:
    - Generate a mostly valid record, then with small probability tweak 1 or 2 fields:
      - type off by one (int vs string, string vs null, array vs string, etc)
      - enum value off by one (e.g. "active" vs "activ")
      - missing field replaced by null or vice versa (but all fields always present per instructions)
      - subtle numeric boundary (e.g. id as string instead of int)
      - child null vs child present with subtle difference
    """

    # Constants
    STATUS_VALUES = ["active", "inactive", "unknown"]
    # To provoke divergence, we sometimes use a wrong enum value close to valid ones
    STATUS_NEAR_VALUES = ["active", "inactive", "unknown", "activ", "inactiv", "unknwn"]

    # Base valid primitives
    def gen_id():
        # id is integer, but sometimes produce stringified int to provoke divergence
        base_int = draw(st.integers(min_value=0, max_value=10000))
        # 85% chance valid int, 15% chance stringified int
        if draw(st.booleans().filter(lambda x: x)):  # 50% chance True
            # 50% of that True: valid int, else stringified int
            if draw(st.booleans()):
                return base_int, True  # valid int
            else:
                return str(base_int), False  # string instead of int
        else:
            return base_int, True

    def gen_amount():
        # amount is string, but sometimes produce number or null to provoke divergence
        base_str = draw(st.text(min_size=1, max_size=10))
        choice = draw(st.integers(min_value=0, max_value=9))
        if choice <= 6:
            return base_str, True  # valid string
        elif choice == 7:
            # number instead of string
            return draw(st.integers(min_value=0, max_value=10000)), False
        elif choice == 8:
            # null instead of string
            return None, False
        else:
            # empty string (valid)
            return "", True

    def gen_name():
        # name is string or null
        # sometimes produce number or boolean to provoke divergence
        base_str = draw(st.text(min_size=0, max_size=10))
        choice = draw(st.integers(min_value=0, max_value=9))
        if choice <= 6:
            # valid string or null
            if draw(st.booleans()):
                return base_str, True
            else:
                return None, True
        elif choice == 7:
            # number instead of string/null
            return draw(st.integers(min_value=0, max_value=1000)), False
        elif choice == 8:
            # boolean instead of string/null
            return draw(st.booleans()), False
        else:
            # empty string (valid)
            return "", True

    def gen_status():
        # status is one of three strings
        # sometimes produce invalid enum string or null to provoke divergence
        choice = draw(st.integers(min_value=0, max_value=9))
        if choice <= 7:
            # valid enum
            return draw(st.sampled_from(STATUS_VALUES)), True
        elif choice == 8:
            # invalid enum close to valid ones
            return draw(st.sampled_from(["activ", "inactiv", "unknwn"])), False
        else:
            # null instead of string
            return None, False

    def gen_tags():
        # tags is array of strings
        # sometimes produce array with non-string elements or string instead of array
        base_tags = draw(st.lists(st.text(min_size=1, max_size=5), min_size=0, max_size=5))
        choice = draw(st.integers(min_value=0, max_value=9))
        if choice <= 6:
            # valid array of strings
            return base_tags, True
        elif choice == 7:
            # array with one non-string element
            if base_tags:
                idx = draw(st.integers(min_value=0, max_value=len(base_tags)-1))
                base_tags[idx] = draw(st.integers(min_value=0, max_value=100))
                return base_tags, False
            else:
                # empty array is valid, so produce string instead
                return draw(st.text(min_size=1, max_size=5)), False
        elif choice == 8:
            # string instead of array
            return draw(st.text(min_size=1, max_size=5)), False
        else:
            # null instead of array
            return None, False

    # Recursive child record, max depth 1
    def gen_child(depth=0):
        # child is null or a record (one level recursion normally)
        # To keep bounded recursion, only recurse once
        choice = draw(st.integers(min_value=0, max_value=9))
        if depth >= 1 or choice <= 6:
            # null child
            return None, True
        else:
            # child record with subtle deviation (one field off)
            # Generate a record with one subtle deviation in one field
            # Pick one field to deviate
            fields = ["id", "amount", "name", "status", "tags"]
            deviate_field = draw(st.sampled_from(fields))

            # Generate all fields normally except deviate_field
            id_val, id_valid = gen_id()
            amount_val, amount_valid = gen_amount()
            name_val, name_valid = gen_name()
            status_val, status_valid = gen_status()
            tags_val, tags_valid = gen_tags()

            # Override one field with invalid variant
            if deviate_field == "id":
                # force id to string if valid int or int if string
                if id_valid:
                    id_val = str(id_val)
                    id_valid = False
                else:
                    try:
                        id_val = int(id_val)
                        id_valid = True
                    except Exception:
                        id_val = 0
                        id_valid = True
            elif deviate_field == "amount":
                # force amount to number if string, or null if string
                if amount_valid and isinstance(amount_val, str):
                    amount_val = draw(st.integers(min_value=0, max_value=1000))
                    amount_valid = False
                else:
                    amount_val = draw(st.text(min_size=1, max_size=5))
                    amount_valid = True
            elif deviate_field == "name":
                # force name to boolean if string/null
                if name_valid:
                    name_val = draw(st.booleans())
                    name_valid = False
                else:
                    name_val = draw(st.text(min_size=1, max_size=5))
                    name_valid = True
            elif deviate_field == "status":
                # force status to invalid enum or null
                if status_valid:
                    status_val = draw(st.sampled_from(["activ", "inactiv", "unknwn"]))
                    status_valid = False
                else:
                    status_val = draw(st.sampled_from(STATUS_VALUES))
                    status_valid = True
            elif deviate_field == "tags":
                # force tags to string or array with non-string
                if tags_valid:
                    tags_val = draw(st.text(min_size=1, max_size=5))
                    tags_valid = False
                else:
                    tags_val = draw(st.lists(st.text(min_size=1, max_size=5), min_size=0, max_size=3))
                    tags_valid = True

            # child cannot have child (depth limit)
            child_val = None

            # Compose child record JSON text
            # Compose fields in order: id, amount, name, status, tags, child
            def json_val(v):
                if v is None:
                    return "null"
                elif isinstance(v, bool):
                    return "true" if v else "false"
                elif isinstance(v, int):
                    return str(v)
                elif isinstance(v, str):
                    return json_string_literal(v)
                elif isinstance(v, list):
                    inner = ",".join(json_string_literal(x) if isinstance(x, str) else "null" for x in v)
                    return "[" + inner + "]"
                else:
                    # fallback
                    return json_string_literal(str(v))

            child_json = (
                '{'
                + '"id":' + json_val(id_val) + ','
                + '"amount":' + json_val(amount_val) + ','
                + '"name":' + json_val(name_val) + ','
                + '"status":' + json_val(status_val) + ','
                + '"tags":' + json_val(tags_val) + ','
                + '"child":null'
                + '}'
            )
            return child_json, False

    # Generate top-level record fields
    id_val, id_valid = gen_id()
    amount_val, amount_valid = gen_amount()
    name_val, name_valid = gen_name()
    status_val, status_valid = gen_status()
    tags_val, tags_valid = gen_tags()
    child_val, child_valid = gen_child(depth=0)

    # Compose JSON text for top-level record
    def json_val(v):
        if v is None:
            return "null"
        elif isinstance(v, bool):
            return "true" if v else "false"
        elif isinstance(v, int):
            return str(v)
        elif isinstance(v, str):
            return json_string_literal(v)
        elif isinstance(v, list):
            inner = ",".join(json_string_literal(x) if isinstance(x, str) else "null" for x in v)
            return "[" + inner + "]"
        else:
            # fallback
            return json_string_literal(str(v))

    child_json_text = child_val if isinstance(child_val, str) else "null"

    json_text = (
        '{'
        + '"id":' + json_val(id_val) + ','
        + '"amount":' + json_val(amount_val) + ','
        + '"name":' + json_val(name_val) + ','
        + '"status":' + json_val(status_val) + ','
        + '"tags":' + json_val(tags_val) + ','
        + '"child":' + child_json_text
        + '}'
    )

    return json_text.encode("utf-8")