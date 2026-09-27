from hypothesis import strategies as st

# Constants for schema
STATUS_VALUES = ["active", "inactive", "unknown"]

def json_escape(s):
    # Minimal JSON string escaper for ASCII
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

@st.composite
def generated_json(draw, max_depth=1):
    # Helper to generate a valid or slightly off-type value for each field
    def id_strategy():
        # id: integer, but sometimes as string or float
        base = st.integers(min_value=-(2**31), max_value=2**31-1)
        off_types = st.one_of(
            st.text(min_size=1, max_size=8).filter(lambda s: not s.isdigit()),  # non-numeric string
            st.floats(allow_nan=False, allow_infinity=False).filter(lambda f: not f.is_integer()),
        )
        return st.one_of(base, base.map(str), off_types)

    def amount_strategy():
        # amount: string, but sometimes as int, float, or null
        base = st.text(min_size=0, max_size=12)
        off_types = st.one_of(
            st.integers(min_value=-10000, max_value=10000),
            st.floats(allow_nan=False, allow_infinity=False),
            st.none(),
        )
        return st.one_of(base, off_types)

    def name_strategy():
        # name: string or null, but sometimes as int, empty array, or omitted
        base = st.one_of(
            st.text(min_size=0, max_size=16),
            st.none(),
        )
        off_types = st.one_of(
            st.integers(min_value=-10000, max_value=10000),
            st.lists(st.integers(), min_size=0, max_size=0),  # empty array
        )
        return st.one_of(base, off_types)

    def status_strategy():
        # status: one of three strings, but sometimes as int, null, or typo
        base = st.sampled_from(STATUS_VALUES)
        off_types = st.one_of(
            st.integers(min_value=0, max_value=2),
            st.none(),
            st.text(min_size=3, max_size=8).filter(lambda s: s not in STATUS_VALUES),
        )
        return st.one_of(base, off_types)

    def tags_strategy():
        # tags: array of strings, but sometimes as array of ints, null, or string
        base = st.lists(st.text(min_size=0, max_size=10), min_size=0, max_size=4)
        off_types = st.one_of(
            st.lists(st.integers(min_value=0, max_value=100), min_size=0, max_size=4),
            st.none(),
            st.text(min_size=0, max_size=20),
        )
        return st.one_of(base, off_types)

    def child_strategy(depth):
        # child: Record or null, but sometimes as int, string, or omitted
        if depth <= 0:
            base = st.none()
        else:
            base = st.one_of(
                st.none(),
                generated_json(max_depth=depth-1).map(lambda b: b.decode("utf-8")),
            )
        off_types = st.one_of(
            st.integers(min_value=-10000, max_value=10000),
            st.text(min_size=0, max_size=16),
        )
        return st.one_of(base, off_types)

    # Decide which fields to "omit" (simulate missing fields)
    # Only allow omitting one field at a time, and not always
    omit_field = draw(st.one_of(
        st.none(),
        st.sampled_from(["id", "amount", "name", "status", "tags", "child"])
    ).filter(lambda x: x is None or max_depth > 0 or x != "child"))  # don't omit child at top level

    # Draw values for each field
    id_val = draw(id_strategy())
    amount_val = draw(amount_strategy())
    name_val = draw(name_strategy())
    status_val = draw(status_strategy())
    tags_val = draw(tags_strategy())
    child_val = draw(child_strategy(max_depth))

    # Helper to render a value as JSON
    def render_json(val):
        if isinstance(val, str):
            return json_escape(val)
        elif val is None:
            return "null"
        elif isinstance(val, bool):
            return "true" if val else "false"
        elif isinstance(val, (int, float)):
            return str(val)
        elif isinstance(val, list):
            return "[" + ",".join(render_json(x) for x in val) + "]"
        elif isinstance(val, dict):
            return "{" + ",".join(
                json_escape(k) + ":" + render_json(v) for k, v in val.items()
            ) + "}"
        else:
            # For recursive child as stringified JSON
            return val if isinstance(val, str) else json_escape(str(val))

    # Build fields, omitting one if chosen
    fields = []
    if omit_field != "id":
        fields.append('"id":' + render_json(id_val))
    if omit_field != "amount":
        fields.append('"amount":' + render_json(amount_val))
    if omit_field != "name":
        fields.append('"name":' + render_json(name_val))
    if omit_field != "status":
        fields.append('"status":' + render_json(status_val))
    if omit_field != "tags":
        fields.append('"tags":' + render_json(tags_val))
    if omit_field != "child":
        fields.append('"child":' + render_json(child_val))

    # Shuffle field order to catch order-sensitive bugs
    fields = draw(st.permutations(fields)).copy()

    json_obj = "{" + ",".join(fields) + "}"
    return json_obj.encode("utf-8")