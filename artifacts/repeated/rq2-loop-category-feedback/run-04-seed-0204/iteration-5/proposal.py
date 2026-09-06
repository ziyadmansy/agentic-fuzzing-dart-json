from hypothesis import strategies as st

# Helper: JSON string escaping for a limited subset (no control chars, no quotes inside)
# We'll generate strings without quotes or backslashes to keep it simple and safe.
def json_string(s: str) -> str:
    # Escape backslash and quote if present (should not be present by construction)
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    return '"' + s + '"'

# Compose JSON array of strings
def json_array_of_strings(arr):
    return "[" + ",".join(json_string(s) for s in arr) + "]"

# Compose JSON object from dict of key: json_value (strings)
def json_object(d):
    # keys are always strings, values are strings representing JSON values
    return "{" + ",".join(json_string(k) + ":" + v for k, v in d.items()) + "}"

# Compose JSON null literal
json_null = "null"

# Compose JSON boolean literals
json_true = "true"
json_false = "false"

# Compose JSON number literal from int or str (assumed valid)
def json_number(n):
    return str(n)

# Compose JSON enum string for status
status_values = ["active", "inactive", "unknown"]

# Compose JSON string or null for name
# Compose JSON string for amount (string always)
# Compose JSON int for id (integer always)
# Compose JSON array of strings for tags (array of strings)
# Compose JSON object or null for child (one level recursion)

# We want to bias towards boundary_id (near 2^53 or 2^64 limits),
# also some null_override, bad_enum, wrong_type, missing_field (but missing_field is zero score)
# We want to keep all fields present (per schema) but vary types and values.

# id: integer near 2^53 boundary (9007199254740991) or 2^64 boundary (18446744073709551615)
id_boundary_values = [
    9007199254740990,  # 2^53 - 2
    9007199254740991,  # 2^53 - 1 (max safe int in JS)
    9007199254740992,  # 2^53 (unsafe in JS)
    18446744073709551614,  # 2^64 - 2
    18446744073709551615,  # 2^64 - 1 (max unsigned 64-bit)
]

# amount: string, but sometimes numeric string, sometimes empty, sometimes weird numeric formats
amount_strategies = st.one_of(
    st.text(min_size=1, max_size=10).filter(lambda s: all(c not in s for c in '"\\')),  # safe strings
    st.integers(min_value=0, max_value=10**10).map(str),
    st.just(""),  # empty string
    st.just("0"),
    st.just("-0"),
    st.just("1e10"),
    st.just("NaN"),  # string "NaN"
)

# name: string or null, sometimes empty string, sometimes "null" string
name_strategies = st.one_of(
    st.none(),
    st.just("null"),
    st.text(min_size=0, max_size=10).filter(lambda s: all(c not in s for c in '"\\')),
)

# status: valid enum or bad enum string (to trigger bad_enum)
status_strategies = st.one_of(
    st.sampled_from(status_values),
    st.text(min_size=1, max_size=10).filter(lambda s: s not in status_values and all(c not in s for c in '"\\')),
)

# tags: array of strings, sometimes empty, sometimes with empty string, sometimes with null or wrong type inside
tags_strategies = st.lists(
    st.one_of(
        st.text(min_size=1, max_size=10).filter(lambda s: all(c not in s for c in '"\\')),
        st.just(""),  # empty string tag
        # We do NOT want null or wrong type inside tags because schema says array of strings always
        # But we can try to insert wrong type as string "null" or "123"
    ),
    min_size=0,
    max_size=5,
)

# child: null or one level recursion (no deeper than one level)
# To avoid deep nesting, child.child is always null
# We can reuse the same strategies but limit recursion depth to 1

@st.composite
def record(draw, allow_null_child=True):
    # id near boundary or random int in safe range
    id_val = draw(st.one_of(
        st.sampled_from(id_boundary_values),
        st.integers(min_value=0, max_value=2**53 - 1),
    ))

    amount_val = draw(amount_strategies)
    name_val = draw(name_strategies)
    status_val = draw(status_strategies)
    tags_val = draw(tags_strategies)

    # child: null or record with child=null
    if allow_null_child:
        child_val = draw(st.one_of(
            st.none(),
            record(allow_null_child=False),
        ))
    else:
        child_val = None

    # Compose JSON text for each field, sometimes with wrong types or null overrides
    # Introduce some controlled wrong_type or null_override on some fields to cause divergence

    # id: always integer (no wrong type here to keep valid JSON)
    id_json = json_number(id_val)

    # amount: string, but sometimes inject wrong type (number or null) to cause divergence
    amount_json = draw(st.one_of(
        st.just(json_string(amount_val)),
        st.just(json_number(0)),  # wrong type: number instead of string
        st.just(json_null),       # null override
    ))

    # name: string or null, sometimes inject wrong type (number)
    name_json = draw(st.one_of(
        st.just(json_null) if name_val is None else st.just(json_string(name_val)),
        st.just(json_number(123)),  # wrong type number instead of string or null
    ))

    # status: string enum or bad enum string, sometimes inject null or wrong type boolean
    status_json = draw(st.one_of(
        st.just(json_string(status_val)),
        st.just(json_null),
        st.just(json_true),
        st.just(json_false),
    ))

    # tags: array of strings, sometimes inject null or wrong type inside array or whole field null
    # But schema says always array of strings, so null or wrong type whole field is divergence candidate
    # We'll sometimes replace tags with null or a number
    tags_json = draw(st.one_of(
        st.just(json_array_of_strings(tags_val)),
        st.just(json_null),
        st.just(json_number(42)),
    ))

    # child: null or record, sometimes inject wrong type (string or number) to cause divergence
    if child_val is None:
        child_json = draw(st.one_of(
            st.just(json_null),
            st.just(json_string("not_a_record")),
            st.just(json_number(0)),
        ))
    else:
        # child_val is a record with child=null
        child_json = child_val

    # Compose final JSON object string
    obj = {
        "id": id_json,
        "amount": amount_json,
        "name": name_json,
        "status": status_json,
        "tags": tags_json,
        "child": child_json,
    }
    return json_object(obj)

@st.composite
def generated_json(draw) -> bytes:
    # Generate top-level record JSON text
    rec_json = draw(record())
    # Return bytes
    return rec_json.encode("utf-8")