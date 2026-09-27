from hypothesis import strategies as st

# Constants for schema
STATUS_VALUES = ["active", "inactive", "unknown"]

def json_escape(s):
    # Minimal JSON string escaper
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

@st.composite
def generated_json(draw):
    # Helper for generating a valid JSON string (or null)
    def string_or_null():
        # Sometimes null, sometimes a string, sometimes a string with odd content
        base = st.text(
            min_size=0,
            max_size=16,
            alphabet=st.characters(
                blacklist_categories=["Cs", "Cc"],
                blacklist_characters=['"', '\\']
            )
        )
        # Sometimes include edge cases: empty, whitespace, unicode, escapes
        edge = st.sampled_from([
            "",
            " ",
            "\u2028",
            "\u0000",
            "O'Reilly",
            "123",
            "NaN",
            "null",
            "true",
            "false",
            "1e10",
            "1.0",
            "0",
            "Infinity",
            "a\"b",
            "c\\d"
        ])
        return st.one_of(
            base,
            edge
        ).map(json_escape) | st.just("null")

    # Helper for generating a string that looks like a number, or not
    def amount_string():
        # Sometimes a valid number as string, sometimes not
        valid_num = st.integers(-999999, 999999).map(str)
        float_num = st.floats(
            allow_nan=False, allow_infinity=False, width=32
        ).map(lambda f: format(f, ".6g"))
        weird_num = st.sampled_from([
            "01", "-0", "+1", "1e10", "1E-5", "0.0", "1.", ".5", "1,000", "NaN", "Infinity", "-Infinity"
        ])
        not_num = st.sampled_from([
            "abc", "", " ", "null", "true", "false", "[]", "{}", "0x10"
        ])
        return st.one_of(valid_num, float_num, weird_num, not_num).map(json_escape)

    # Helper for generating tags array
    def tags_array():
        # Sometimes empty, sometimes with edge-case strings, sometimes with nulls or numbers
        tag_str = st.text(
            min_size=0,
            max_size=12,
            alphabet=st.characters(
                blacklist_categories=["Cs", "Cc"],
                blacklist_characters=['"', '\\']
            )
        ).map(json_escape)
        edge = st.sampled_from([
            json_escape(""), json_escape(" "), json_escape("null"), json_escape("true"),
            json_escape("false"), json_escape("0"), json_escape("1.0"), json_escape("a\"b"),
            json_escape("c\\d")
        ])
        # Sometimes insert a non-string (to test type handling)
        non_str = st.sampled_from(["null", "0", "1.0", "true", "false"])
        tag_elem = st.one_of(tag_str, edge, non_str)
        arr = st.lists(tag_elem, min_size=0, max_size=4)
        return arr.map(lambda elems: "[" + ", ".join(elems) + "]")

    # Helper for status field
    def status_field():
        # Sometimes valid, sometimes invalid, sometimes null
        valid = st.sampled_from(STATUS_VALUES).map(json_escape)
        invalid = st.sampled_from([
            json_escape("ACTIVE"), json_escape("inactive "), json_escape("unknowns"),
            json_escape(""), json_escape("null"), "null", "0", "true"
        ])
        return st.one_of(valid, invalid)

    # Helper for id field
    def id_field():
        # Sometimes integer, sometimes float, sometimes string, sometimes null
        valid = st.integers(-1000, 1000).map(str)
        floaty = st.floats(allow_nan=False, allow_infinity=False, width=32).map(lambda f: format(f, ".6g"))
        as_str = st.text(
            min_size=1, max_size=8, alphabet="0123456789"
        ).map(json_escape)
        weird = st.sampled_from(["null", "true", "false", json_escape("123")])
        return st.one_of(valid, floaty, as_str, weird)

    # Helper for child field (recursion, depth 1)
    def child_field(depth):
        # At depth 0, only allow null
        if depth == 0:
            return st.just("null")
        # Otherwise, sometimes null, sometimes a record
        nullish = st.just("null")
        recordish = record_strategy(depth - 1)
        return st.one_of(nullish, recordish)

    # Compose a record
    def record_strategy(depth):
        # For each field, sometimes use a valid value, sometimes an edge/invalid value
        id_val = id_field()
        amount_val = amount_string()
        name_val = string_or_null()
        status_val = status_field()
        tags_val = tags_array()
        child_val = child_field(depth)
        # Sometimes omit a field (to test missing fields)
        fields = [
            ("id", id_val),
            ("amount", amount_val),
            ("name", name_val),
            ("status", status_val),
            ("tags", tags_val),
            ("child", child_val)
        ]
        # Sometimes omit one field (but not more than one)
        omit_idx = draw(st.none() | st.integers(0, len(fields) - 1))
        field_strs = []
        for i, (k, strat) in enumerate(fields):
            if omit_idx is not None and i == omit_idx:
                continue
            v = draw(strat)
            field_strs.append(json_escape(k) + ": " + v)
        # Shuffle field order
        draw(st.permutations(field_strs))
        # Compose object
        return st.just("{" + ", ".join(field_strs) + "}")

    # Top-level: always depth 1 for child
    json_obj = draw(record_strategy(1))
    # Return as bytes
    return json_obj.encode("utf-8")