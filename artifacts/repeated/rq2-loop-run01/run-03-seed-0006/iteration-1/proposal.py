from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status enum
    statuses = ["active", "inactive", "unknown"]

    # Recursive definition of a Record JSON text
    # We produce syntactically valid JSON text representing the record,
    # with exactly these six fields always present.
    # We vary one or two fields to be slightly off-type or borderline,
    # to provoke divergence in deserializers.

    # To keep recursion bounded, we limit depth to 1 (child can be null or a record with child=null)
    def record_json(depth=0):
        # id: integer normally, but sometimes stringified integer or float to provoke divergence
        id_choice = draw(st.one_of(
            st.integers(min_value=0, max_value=2**31-1).map(str),
            st.text(min_size=1, max_size=5).filter(lambda s: not s.isdigit()),  # invalid string id
            st.floats(allow_nan=False, allow_infinity=False).map(lambda f: str(f)),
        ))
        # amount: string normally, but sometimes a number or null to provoke divergence
        amount_choice = draw(st.one_of(
            st.text(min_size=1, max_size=10).map(lambda s: '"' + s.replace('"', '\\"') + '"'),
            st.integers(min_value=0, max_value=100000).map(str),
            st.just("null"),
        ))

        # name: string or null normally, but sometimes a number or boolean or missing quotes to provoke divergence
        name_variant = draw(st.integers(min_value=0, max_value=4))
        if name_variant == 0:
            # null
            name_choice = "null"
        elif name_variant == 1:
            # string
            s = draw(st.text(min_size=0, max_size=10))
            # escape quotes inside string
            s = s.replace('"', '\\"')
            name_choice = '"' + s + '"'
        elif name_variant == 2:
            # number instead of string/null
            name_choice = str(draw(st.integers(min_value=-1000, max_value=1000)))
        elif name_variant == 3:
            # boolean instead of string/null
            name_choice = draw(st.sampled_from(["true", "false"]))
        else:
            # empty string without quotes (invalid JSON but we must produce valid JSON, so fallback)
            s = draw(st.text(min_size=0, max_size=10))
            s = s.replace('"', '\\"')
            name_choice = '"' + s + '"'

        # status: one of the three strings normally, but sometimes a wrong string or number or null
        status_variant = draw(st.integers(min_value=0, max_value=4))
        if status_variant == 0:
            status_choice = '"' + draw(st.sampled_from(statuses)) + '"'
        elif status_variant == 1:
            # wrong string
            status_choice = '"' + draw(st.text(min_size=1, max_size=10).filter(lambda s: s not in statuses)) + '"'
        elif status_variant == 2:
            # number instead of string
            status_choice = str(draw(st.integers(min_value=0, max_value=10)))
        elif status_variant == 3:
            # null instead of string
            status_choice = "null"
        else:
            # boolean instead of string
            status_choice = draw(st.sampled_from(["true", "false"]))

        # tags: array of strings normally, but sometimes empty array, array with non-string, or null
        tags_variant = draw(st.integers(min_value=0, max_value=3))
        if tags_variant == 0:
            # normal array of strings
            tag_list = draw(st.lists(st.text(min_size=0, max_size=5), min_size=0, max_size=5))
            # escape quotes in tags
            tag_list = ['"' + t.replace('"', '\\"') + '"' for t in tag_list]
            tags_choice = "[" + ",".join(tag_list) + "]"
        elif tags_variant == 1:
            # array with a non-string element (number)
            tag_list = draw(st.lists(st.text(min_size=0, max_size=5), min_size=0, max_size=4))
            tag_list = ['"' + t.replace('"', '\\"') + '"' for t in tag_list]
            # insert a number element randomly
            insert_pos = draw(st.integers(min_value=0, max_value=len(tag_list)))
            num_elem = str(draw(st.integers(min_value=0, max_value=100)))
            tag_list.insert(insert_pos, num_elem)
            tags_choice = "[" + ",".join(tag_list) + "]"
        elif tags_variant == 2:
            # empty array
            tags_choice = "[]"
        else:
            # null instead of array
            tags_choice = "null"

        # child: null or nested record (depth limited to 1)
        if depth >= 1:
            child_choice = "null"
        else:
            child_variant = draw(st.integers(min_value=0, max_value=2))
            if child_variant == 0:
                child_choice = "null"
            else:
                child_choice = record_json(depth=depth+1)

        # Compose JSON object text with all six fields always present
        # We shuffle field order to avoid assumptions about order
        fields = [
            ('"id"', id_choice),
            ('"amount"', amount_choice),
            ('"name"', name_choice),
            ('"status"', status_choice),
            ('"tags"', tags_choice),
            ('"child"', child_choice),
        ]
        # Shuffle fields order to avoid order assumptions
        draw(st.permutations(fields))  # just to consume draw, but we keep order stable for reproducibility
        # We keep stable order to avoid unnecessary complexity:
        # id, amount, name, status, tags, child

        json_text = (
            '{'
            + '"id":' + id_choice + ','
            + '"amount":' + amount_choice + ','
            + '"name":' + name_choice + ','
            + '"status":' + status_choice + ','
            + '"tags":' + tags_choice + ','
            + '"child":' + child_choice
            + '}'
        )
        return json_text

    # Draw the top-level record JSON text
    top_json = record_json(depth=0)
    # Return as bytes
    return top_json.encode("utf-8")