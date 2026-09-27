from hypothesis import strategies as st

# Helper strategies for field values
status_values = st.sampled_from(["active", "inactive", "unknown"])

# For subtle divergence, we want to sometimes use "almost right" types:
# - amount: string, but sometimes a number or null
# - name: string or null, but sometimes a number or boolean
# - tags: array of strings, but sometimes array of numbers, or array with a null, or a string
# - child: object or null, but sometimes a string, array, or missing

def json_escape(s):
    # Minimal JSON string escaper for ASCII
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

@st.composite
def generated_json(draw, max_depth=1):
    # id: always present, usually int, sometimes float or string
    id_val = draw(
        st.one_of(
            st.integers(min_value=0, max_value=2**31-1).map(str),  # valid int
            st.floats(allow_nan=False, allow_infinity=False, width=32).filter(lambda f: not f.is_integer()).map(str),  # float as string
            st.text(min_size=1, max_size=8).filter(lambda s: not s.isdigit()).map(json_escape),  # string, not a number
        )
    )

    # amount: usually string, sometimes int, float, or null
    amount_val = draw(
        st.one_of(
            st.text(min_size=1, max_size=8).map(json_escape),  # valid string
            st.integers(min_value=-100000, max_value=100000).map(str),  # int (not quoted)
            st.floats(allow_nan=False, allow_infinity=False, width=32).map(str),  # float (not quoted)
            st.just("null"),
        )
    )

    # name: string or null, sometimes int or boolean
    name_val = draw(
        st.one_of(
            st.text(min_size=0, max_size=8).map(json_escape),
            st.just("null"),
            st.integers(min_value=-100, max_value=100).map(str),
            st.sampled_from(["true", "false"]),
        )
    )

    # status: valid enum, sometimes as a number or null
    status_val = draw(
        st.one_of(
            status_values.map(json_escape),
            st.integers(min_value=0, max_value=2).map(str),
            st.just("null"),
        )
    )

    # tags: array of strings, sometimes array of numbers, array with null, or a string
    tags_val = draw(
        st.one_of(
            st.lists(st.text(min_size=0, max_size=6).map(json_escape), min_size=0, max_size=4)
            .map(lambda lst: "[" + ",".join(lst) + "]"),
            st.lists(st.integers(min_value=-10, max_value=10).map(str), min_size=0, max_size=4)
            .map(lambda lst: "[" + ",".join(lst) + "]"),
            st.lists(
                st.one_of(
                    st.text(min_size=0, max_size=6).map(json_escape),
                    st.just("null"),
                ),
                min_size=1, max_size=4
            ).map(lambda lst: "[" + ",".join(lst) + "]"),
            st.text(min_size=0, max_size=12).map(json_escape),  # not an array
            st.just("null"),
        )
    )

    # child: object or null, sometimes string, array, or missing
    child_val = None
    child_field = ""
    child_choice = draw(
        st.sampled_from(
            ["object", "null", "string", "array", "missing"]
            if max_depth > 0 else ["null", "missing"]
        )
    )
    if child_choice == "object":
        # Recurse with max_depth-1
        child_json = draw(generated_json(max_depth=max_depth-1))
        child_field = f'"child":{child_json.decode("utf-8")}'
    elif child_choice == "null":
        child_field = '"child":null'
    elif child_choice == "string":
        child_field = '"child":' + json_escape(draw(st.text(min_size=0, max_size=8)))
    elif child_choice == "array":
        arr = draw(st.lists(st.integers(min_value=0, max_value=10).map(str), min_size=0, max_size=3))
        child_field = '"child":[' + ",".join(arr) + ']'
    elif child_choice == "missing":
        child_field = ""  # Omit the field

    # Compose the object, always include all fields except possibly child
    fields = [
        f'"id":{id_val}',
        f'"amount":{amount_val}',
        f'"name":{name_val}',
        f'"status":{status_val}',
        f'"tags":{tags_val}',
    ]
    if child_field:
        fields.append(child_field)
    json_obj = "{" + ",".join(fields) + "}"

    return json_obj.encode("utf-8")