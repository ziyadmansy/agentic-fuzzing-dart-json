from hypothesis import strategies as st

# Helper: produce a JSON string literal from a Python string, escaping as needed.
# Minimal escaping: backslash, quote, control chars (U+0000..U+001F).
# Hypothesis strings are Unicode; we must escape properly.
def json_string_literal(s: str) -> str:
    def esc_char(c):
        o = ord(c)
        if c == '"':
            return r'\"'
        if c == '\\':
            return r'\\'
        if o <= 0x1F:
            # Control chars as \u00XX
            return '\\u%04x' % o
        # else normal char
        return c
    return '"' + ''.join(esc_char(c) for c in s) + '"'

# Compose JSON array of strings from Python list[str]
def json_array_of_strings(lst):
    # lst is list of strings, each already escaped as JSON string literal
    return '[' + ','.join(lst) + ']'

# Compose JSON object from dict of key->value strings (all keys and values are JSON text)
def json_object(d):
    # d keys are strings (field names), values are JSON text (strings, numbers, objects, arrays, literals)
    # keys must be JSON strings
    items = []
    for k, v in d.items():
        items.append(json_string_literal(k) + ':' + v)
    return '{' + ','.join(items) + '}'

@st.composite
def generated_json(draw) -> bytes:
    """
    Generate syntactically valid JSON objects matching the schema with small
    targeted deviations to provoke divergence between four Dart JSON deserializers:
    manual, json_serializable, freezed, built_value.

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
    - Generate mostly well-formed documents.
    - Introduce exactly one or two small deviations per document:
      * type errors on a single field (e.g. "id" as string instead of int)
      * null vs missing fields (missing fields are invalid but some impls may accept)
      * enum field with invalid string or null
      * array with wrong element types or empty array
      * child null vs child object vs child with one deviation inside
    - Limit recursion depth to 1 (child can be null or a record with no child)
    - Produce JSON text as bytes.
    """

    # Constants
    STATUS_ENUM = ["active", "inactive", "unknown"]

    # Helpers to produce JSON text for each field with possible deviations

    # id: normally integer, but sometimes string or float or null or missing
    def gen_id():
        # 80% int, 10% string int, 5% float, 5% null
        choice = draw(st.floats(min_value=0, max_value=1))
        if choice < 0.8:
            # int in range 0..1_000_000
            i = draw(st.integers(min_value=0, max_value=1_000_000))
            return str(i)
        elif choice < 0.9:
            # string decimal integer
            i = draw(st.integers(min_value=0, max_value=1_000_000))
            return json_string_literal(str(i))
        elif choice < 0.95:
            # float as number (not int)
            f = draw(st.floats(min_value=0, max_value=1_000_000, allow_infinity=False, allow_nan=False))
            # format float with decimal point to distinguish from int
            s = ('%.6f' % f).rstrip('0').rstrip('.')
            if '.' not in s:
                s += '.0'
            return s
        else:
            # null literal
            return 'null'

    # amount: normally string, but sometimes number or null or empty string
    def gen_amount():
        choice = draw(st.floats(min_value=0, max_value=1))
        if choice < 0.85:
            # string decimal number, possibly with currency symbol or spaces
            base = draw(st.decimals(min_value=0, max_value=1_000_000, places=2).map(str))
            # add optional currency symbol or spaces
            prefix = draw(st.sampled_from(['', '$', 'USD ', '€', '']))
            suffix = draw(st.sampled_from(['', ' USD', ' €', '']))
            s = prefix + base + suffix
            return json_string_literal(s)
        elif choice < 0.9:
            # number (int or float)
            n = draw(st.one_of(st.integers(min_value=0, max_value=1_000_000), st.floats(min_value=0, max_value=1_000_000, allow_infinity=False, allow_nan=False)))
            if isinstance(n, float):
                s = ('%.6f' % n).rstrip('0').rstrip('.')
                if '.' not in s:
                    s += '.0'
                return s
            else:
                return str(n)
        elif choice < 0.95:
            # null
            return 'null'
        else:
            # empty string
            return '""'

    # name: string or null, sometimes number or missing
    def gen_name():
        choice = draw(st.floats(min_value=0, max_value=1))
        if choice < 0.7:
            # string or null
            if draw(st.booleans()):
                # string
                s = draw(st.text(min_size=0, max_size=20))
                return json_string_literal(s)
            else:
                return 'null'
        elif choice < 0.85:
            # number instead of string/null
            n = draw(st.integers(min_value=0, max_value=10000))
            return str(n)
        else:
            # missing field (signal by returning None)
            return None

    # status: one of enum strings, or invalid string, or null, or missing
    def gen_status():
        choice = draw(st.floats(min_value=0, max_value=1))
        if choice < 0.8:
            s = draw(st.sampled_from(STATUS_ENUM))
            return json_string_literal(s)
        elif choice < 0.9:
            # invalid string
            s = draw(st.text(min_size=1, max_size=10).filter(lambda x: x not in STATUS_ENUM))
            return json_string_literal(s)
        elif choice < 0.95:
            return 'null'
        else:
            return None  # missing

    # tags: array of strings, sometimes empty array, sometimes array with non-string, sometimes null, sometimes missing
    def gen_tags():
        choice = draw(st.floats(min_value=0, max_value=1))
        if choice < 0.75:
            # array of strings (0..5 elements)
            n = draw(st.integers(min_value=0, max_value=5))
            elems = []
            for _ in range(n):
                s = draw(st.text(min_size=0, max_size=10))
                elems.append(json_string_literal(s))
            return '[' + ','.join(elems) + ']'
        elif choice < 0.85:
            # array with some non-string element
            n = draw(st.integers(min_value=1, max_value=5))
            elems = []
            for _ in range(n):
                if draw(st.booleans()):
                    s = draw(st.text(min_size=0, max_size=10))
                    elems.append(json_string_literal(s))
                else:
                    # number element
                    num = draw(st.integers(min_value=0, max_value=100))
                    elems.append(str(num))
            return '[' + ','.join(elems) + ']'
        elif choice < 0.9:
            # null
            return 'null'
        else:
            return None  # missing

    # child: null or record (one level recursion), sometimes malformed record or missing
    # To avoid infinite recursion, child record has child=null always.
    def gen_child():
        choice = draw(st.floats(min_value=0, max_value=1))
        if choice < 0.6:
            # null child
            return 'null'
        elif choice < 0.95:
            # child record with no child (child=null)
            # Generate a record with no deviations inside (to keep complexity low)
            child_id = draw(st.integers(min_value=0, max_value=1_000_000))
            child_amount = draw(st.text(min_size=1, max_size=10))
            child_name = draw(st.one_of(st.none(), st.text(min_size=0, max_size=10)))
            child_status = draw(st.sampled_from(STATUS_ENUM))
            child_tags_n = draw(st.integers(min_value=0, max_value=3))
            child_tags = [draw(st.text(min_size=0, max_size=10)) for _ in range(child_tags_n)]

            obj = {
                "id": str(child_id),
                "amount": json_string_literal(child_amount),
                "name": 'null' if child_name is None else json_string_literal(child_name),
                "status": json_string_literal(child_status),
                "tags": json_array_of_strings([json_string_literal(t) for t in child_tags]),
                "child": 'null'
            }
            return json_object(obj)
        else:
            # missing child field (signal by None)
            return None

    # Compose the top-level object fields, possibly omitting some fields (None)
    # We will always include "id" and "amount" to keep mostly valid, but sometimes omit others.
    id_val = gen_id()
    amount_val = gen_amount()
    name_val = gen_name()
    status_val = gen_status()
    tags_val = gen_tags()
    child_val = gen_child()

    fields = {}

    # Always include id and amount
    fields["id"] = id_val
    fields["amount"] = amount_val

    # Conditionally include name
    if name_val is not None:
        fields["name"] = name_val

    # Conditionally include status
    if status_val is not None:
        fields["status"] = status_val

    # Conditionally include tags
    if tags_val is not None:
        fields["tags"] = tags_val

    # Conditionally include child
    if child_val is not None:
        fields["child"] = child_val

    # Compose JSON text
    json_text = json_object(fields)

    # Return bytes
    return json_text.encode("utf-8")