from hypothesis import strategies as st
import json

# We define a recursive strategy for the "child" field with bounded depth.
# The recursion depth is limited to 1 level as per the problem statement.

@st.composite
def generated_json(draw) -> bytes:
    # Basic field strategies:
    id_strat = st.integers(min_value=-(2**31), max_value=2**31-1)
    # amount is string, but we will sometimes produce numeric strings, empty strings, or strings with spaces
    amount_strat = st.one_of(
        st.text(min_size=1, max_size=10),  # arbitrary strings
        st.just(""),                      # empty string
        st.from_regex(r"^-?\d+(\.\d+)?$", fullmatch=True),  # numeric strings
        st.just(" 123 "),                 # string with spaces
    )
    # name can be string or null, but we will sometimes produce empty string, whitespace, or null
    name_strat = st.one_of(
        st.none(),
        st.text(min_size=0, max_size=20),
        st.just(""),  # empty string
        st.just(" "), # single space string
    )
    # status must be one of "active", "inactive", "unknown"
    # We will sometimes produce invalid strings or null to cause divergence
    status_valid = st.sampled_from(["active", "inactive", "unknown"])
    status_invalid = st.one_of(
        st.text(min_size=1, max_size=10).filter(lambda s: s not in {"active","inactive","unknown"}),
        st.none(),
        st.integers(min_value=0, max_value=10),
        st.just("ACTIVE"),  # uppercase variant
    )
    # tags is array of strings, but we will sometimes produce empty array, array with nulls, or array with non-string
    tag_str = st.text(min_size=1, max_size=10)
    tags_valid = st.lists(tag_str, min_size=0, max_size=5)
    tags_invalid = st.one_of(
        st.lists(st.one_of(tag_str, st.none(), st.integers()), min_size=0, max_size=5),
        st.none(),
        st.just("not an array"),
    )
    # child is either null or a nested record (one level only)
    # We will produce either null or a nested record with one field off to cause divergence
    # To do this, we define a helper function to produce a nested record with one field tweaked

    # First define a base record strategy without child (to avoid infinite recursion)
    def base_record():
        return st.fixed_dictionaries({
            "id": id_strat,
            "amount": amount_strat,
            "name": name_strat,
            "status": status_valid,
            "tags": tags_valid,
            "child": st.none(),
        })

    # Now define a nested record with one field tweaked to an invalid value
    def nested_record_with_one_off():
        # Pick one field to tweak
        field_to_tweak = draw(st.sampled_from(["id", "amount", "name", "status", "tags", "child"]))
        # Base valid record dict
        base = draw(base_record())
        # Tweak one field with invalid or borderline value
        if field_to_tweak == "id":
            # id normally int, tweak to string or float
            tweak_val = draw(st.one_of(st.text(min_size=1, max_size=5), st.floats(allow_nan=False, allow_infinity=False)))
            base["id"] = tweak_val
        elif field_to_tweak == "amount":
            # amount normally string, tweak to int or null
            tweak_val = draw(st.one_of(st.integers(), st.none()))
            base["amount"] = tweak_val
        elif field_to_tweak == "name":
            # name normally string or null, tweak to int or bool
            tweak_val = draw(st.one_of(st.integers(), st.booleans()))
            base["name"] = tweak_val
        elif field_to_tweak == "status":
            # status normally valid string, tweak to invalid string or null
            tweak_val = draw(status_invalid)
            base["status"] = tweak_val
        elif field_to_tweak == "tags":
            # tags normally list of strings, tweak to list with non-string or null
            tweak_val = draw(tags_invalid)
            base["tags"] = tweak_val
        elif field_to_tweak == "child":
            # child normally null or nested record, tweak to invalid type (string or int)
            tweak_val = draw(st.one_of(st.text(min_size=1, max_size=5), st.integers()))
            base["child"] = tweak_val
        return base

    # Now define the top-level record, mostly valid but with one or two fields tweaked to cause divergence
    # We pick one or two fields to tweak or leave valid

    # Start with a valid base record with child null or nested one-level record (valid or tweaked)
    child_choice = draw(st.one_of(
        st.none(),
        nested_record_with_one_off(),
        base_record(),
    ))

    # Now build the top-level record dict
    top_level = {}

    # id: mostly valid int, sometimes tweak to string or float
    if draw(st.booleans()):
        top_level["id"] = draw(id_strat)
    else:
        top_level["id"] = draw(st.one_of(st.text(min_size=1, max_size=5), st.floats(allow_nan=False, allow_infinity=False)))

    # amount: mostly valid string, sometimes tweak to int or null
    if draw(st.booleans()):
        top_level["amount"] = draw(amount_strat)
    else:
        top_level["amount"] = draw(st.one_of(st.integers(), st.none()))

    # name: mostly valid string or null, sometimes tweak to int or bool
    if draw(st.booleans()):
        top_level["name"] = draw(name_strat)
    else:
        top_level["name"] = draw(st.one_of(st.integers(), st.booleans()))

    # status: mostly valid enum string, sometimes tweak to invalid string or null
    if draw(st.booleans()):
        top_level["status"] = draw(status_valid)
    else:
        top_level["status"] = draw(status_invalid)

    # tags: mostly valid list of strings, sometimes tweak to list with non-string or null or string
    if draw(st.booleans()):
        top_level["tags"] = draw(tags_valid)
    else:
        top_level["tags"] = draw(tags_invalid)

    # child: use the chosen child (null, valid nested, or tweaked nested)
    top_level["child"] = child_choice

    # Serialize to JSON bytes
    json_bytes = json.dumps(top_level, separators=(",", ":")).encode("utf-8")
    return json_bytes