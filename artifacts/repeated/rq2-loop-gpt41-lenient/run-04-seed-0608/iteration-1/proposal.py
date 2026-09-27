from hypothesis import strategies as st

# Helper strategies for edge cases
def weird_ints():
    # Try values at boundaries and weird cases
    return st.one_of(
        st.integers(min_value=-(2**63), max_value=2**63-1),  # 64-bit boundaries
        st.just(0),
        st.just(-1),
        st.just(1),
        st.just(2**31-1),
        st.just(-2**31),
        st.just(2**53-1),  # JS safe int
        st.just(-2**53+1),
        st.integers(min_value=-10, max_value=10),
    )

def weird_strings():
    # Try empty, whitespace, numeric, unicode, escape chars, long, etc.
    return st.one_of(
        st.just(""),
        st.just(" "),
        st.just("\n"),
        st.just("0"),
        st.just("123"),
        st.just("-123"),
        st.just("null"),
        st.just("None"),
        st.just("NaN"),
        st.just("Infinity"),
        st.just("-Infinity"),
        st.just("true"),
        st.just("false"),
        st.just("ACTIVE"),
        st.just("inactive"),
        st.just("unknown"),
        st.just("a" * 1000),
        st.text(min_size=1, max_size=32),
        st.text(alphabet=st.characters(blacklist_categories=["Cs"]), min_size=1, max_size=32),
        st.text(alphabet=" \n\t\r", min_size=1, max_size=4),
        st.text(alphabet="0123456789", min_size=1, max_size=20),
        st.text(alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ", min_size=1, max_size=20),
        st.text(alphabet="!@#$%^&*()_+-=[]{}|;:',.<>/?", min_size=1, max_size=10),
    )

def weird_status():
    # Try valid and invalid status values
    return st.one_of(
        st.sampled_from(["active", "inactive", "unknown"]),
        st.just("ACTIVE"),
        st.just("Inactive"),
        st.just(""),
        st.just("null"),
        st.just("0"),
        st.just("1"),
        st.just("unknown "),
        weird_strings(),
    )

def weird_tags():
    # Try empty, long, nulls, numbers, etc.
    return st.one_of(
        st.lists(weird_strings(), min_size=0, max_size=5),
        st.lists(st.just(""), min_size=1, max_size=3),
        st.lists(st.just(None), min_size=1, max_size=1),
        st.lists(st.integers(), min_size=1, max_size=2),
        st.lists(st.just("null"), min_size=1, max_size=2),
    )

def weird_child(rec_strategy):
    # Try null, valid, missing fields, wrong types
    return st.one_of(
        st.just("null"),
        rec_strategy,
        st.just("{}"),
        st.just("[]"),
        st.just("0"),
        st.just("\"string\""),
    )

def maybe_null(strategy):
    return st.one_of(st.just("null"), strategy)

def maybe_missing(key, value):
    # Sometimes omit the field entirely
    return st.one_of(
        st.just(""),  # missing
        st.just(f'"{key}":{value}'),
    )

@st.composite
def generated_json(draw, max_depth=1):
    # For recursion, only allow child at depth 0
    def record(depth):
        # id: integer (but try string, float, null, etc.)
        id_val = draw(st.one_of(
            weird_ints().map(str),
            weird_strings().map(lambda s: f'"{s}"'),
            st.just("null"),
            st.just("0.0"),
        ))

        # amount: string (but try numbers, null, bool, etc.)
        amount_val = draw(st.one_of(
            weird_strings().map(lambda s: f'"{s}"'),
            weird_ints().map(str),
            st.just("null"),
            st.just("true"),
            st.just("false"),
        ))

        # name: string or null (try missing, numbers, bool, empty, etc.)
        name_val = draw(st.one_of(
            weird_strings().map(lambda s: f'"{s}"'),
            st.just("null"),
            st.just(""),
            st.just("0"),
            st.just("true"),
            st.just("false"),
        ))

        # status: enum (try invalid, null, numbers, etc.)
        status_val = draw(st.one_of(
            weird_status().map(lambda s: f'"{s}"'),
            st.just("null"),
            st.just("0"),
            st.just("true"),
        ))

        # tags: array of strings (try numbers, nulls, empty, etc.)
        tags_val = draw(st.one_of(
            weird_tags().map(lambda tags: "[" + ",".join(
                "null" if t is None else (str(t) if isinstance(t, int) else f'"{t}"') for t in tags
            ) + "]"),
            st.just("null"),
            st.just("[]"),
            st.just("[null]"),
            st.just("[0]"),
        ))

        # child: Record or null (try wrong types, missing, etc.)
        if depth < max_depth:
            child_val = draw(st.one_of(
                st.just("null"),
                record(depth + 1).map(lambda s: s),
                st.just("{}"),
                st.just("[]"),
                st.just("0"),
                st.just("\"string\""),
            ))
        else:
            child_val = draw(st.one_of(
                st.just("null"),
                st.just("{}"),
                st.just("[]"),
                st.just("0"),
                st.just("\"string\""),
            ))

        # Sometimes omit one field (but not all)
        fields = [
            ('id', id_val),
            ('amount', amount_val),
            ('name', name_val),
            ('status', status_val),
            ('tags', tags_val),
            ('child', child_val),
        ]
        # Omit at most one field, or none
        omit_idx = draw(st.integers(min_value=-1, max_value=5))
        obj_fields = []
        for i, (k, v) in enumerate(fields):
            if i == omit_idx:
                continue
            obj_fields.append(f'"{k}":{v}')
        return "{" + ",".join(obj_fields) + "}"

    # Top-level record
    json_str = record(0)
    # Return as bytes
    return json_str.encode("utf-8")