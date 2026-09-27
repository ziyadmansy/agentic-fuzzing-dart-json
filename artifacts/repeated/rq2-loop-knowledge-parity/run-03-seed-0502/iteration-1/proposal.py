from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status field
    statuses = ["active", "inactive", "unknown"]

    # Helper to produce a JSON string literal with proper escaping of quotes and backslashes
    def json_string(s: str) -> str:
        # Minimal escaping: backslash and double quote
        s = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{s}"'

    # Helper to produce JSON array of strings
    def json_array_of_strings(lst):
        # lst is list of strings
        return "[" + ",".join(json_string(x) for x in lst) + "]"

    # Recursive record generator with bounded depth (max 1 level of recursion)
    # We produce a dict of fields as strings (already JSON encoded) to be joined later
    def gen_record(depth=0):
        # id: integer or double (to trigger divergence)
        # Manual and built_value require int; json_serializable and freezed accept double and call toInt()
        # We produce either an int literal or a double literal that jsonDecode will parse as double
        # To trigger divergence, produce a double that is an integer value (e.g. 42.0) or a double with fraction (e.g. 42.5)
        id_choice = draw(st.integers(min_value=-(2**63), max_value=2**63-1).flatmap(
            lambda i: st.one_of(
                st.just(str(i)),  # int literal
                # double literal with .0 to be parsed as double but equal to int
                st.just(f"{float(i):.1f}"),
                # double literal with fractional part (non-integer)
                st.just(f"{float(i) + 0.5:.1f}")
            )
        ))

        # amount: string, always present, non-nullable
        # Use ascii printable strings, non-empty, with some chance of special chars (to test escaping)
        amount_str = draw(st.text(min_size=1, max_size=10, alphabet=st.characters(blacklist_characters=['"', '\\'])))
        amount = json_string(amount_str)

        # name: nullable string or null, always present
        # Use either null or a string (possibly empty)
        name_val = draw(st.one_of(st.none(), st.text(max_size=10, alphabet=st.characters(blacklist_characters=['"', '\\']))))
        name = "null" if name_val is None else json_string(name_val)

        # status: one of the three allowed strings, always present
        status_val = draw(st.sampled_from(statuses))
        status = json_string(status_val)

        # tags: array of strings, always present or missing (to test missing tags)
        # We produce either:
        # - present with empty or non-empty array of strings
        # - missing (only for top-level record, to test built_value behavior)
        # But since child is nested, only top-level can omit tags to test missing tags
        # So here, for nested child, always present tags
        tags_list = draw(st.lists(st.text(min_size=0, max_size=5, alphabet=st.characters(blacklist_characters=['"', '\\'])), max_size=3))
        tags = json_array_of_strings(tags_list)

        # child: nullable record or null, one level of recursion max
        if depth == 0:
            # child can be null or a record with depth=1
            child_val = draw(st.one_of(st.none(), st.just("RECURSE")))
        else:
            # depth=1: child must be null (no deeper recursion)
            child_val = None

        if child_val == "RECURSE":
            child = gen_record(depth=1)
            child_json = "{" + ",".join(child) + "}"
        elif child_val is None:
            child_json = "null"
        else:
            # Should not happen
            child_json = "null"

        # Compose fields as strings "key":value
        # For top-level record, we will later decide to omit tags or not
        fields = [
            f'"id":{id_choice}',
            f'"amount":{amount}',
            f'"name":{name}',
            f'"status":{status}',
            f'"tags":{tags}',
            f'"child":{child_json}',
        ]
        return fields

    # Generate top-level record fields
    top_fields = gen_record(depth=0)

    # Now, to test missing tags at top-level, randomly omit "tags" field sometimes
    omit_tags = draw(st.booleans())
    if omit_tags:
        # Remove the tags field (index 4)
        top_fields = [f for f in top_fields if not f.startswith('"tags":')]

    # Compose JSON object string
    json_text = "{" + ",".join(top_fields) + "}"

    # Return as bytes
    return json_text.encode("utf-8")