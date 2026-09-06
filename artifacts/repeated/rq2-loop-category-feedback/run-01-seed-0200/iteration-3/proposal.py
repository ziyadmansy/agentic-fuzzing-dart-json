from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants for status enum as strings
    statuses = st.sampled_from(['"active"', '"inactive"', '"unknown"'])
    # Tags array: array of strings, possibly empty
    tags = st.lists(st.text(min_size=0, max_size=10).map(lambda s: '"' + s.replace('"', '\\"') + '"'),
                    min_size=0, max_size=5).map(lambda lst: '[' + ','.join(lst) + ']')

    # To induce divergences, we allow "amount" to be either a string (normal) or a number (wrong type)
    # Also allow "id" to be either integer (normal) or string (wrong type)
    # "name" can be string or null, or sometimes a number (wrong type)
    # "status" can be correct enum string or a wrong string (to test enum parsing)
    # "tags" can be array of strings (normal) or array of numbers (wrong type)
    # "child" can be null or a nested record (one level recursion only)

    # Define a strategy for "amount" field: mostly string, sometimes number as string (wrong type)
    amount_str = st.text(min_size=0, max_size=20).map(lambda s: '"' + s.replace('"', '\\"') + '"')
    amount_wrong = st.one_of(st.integers(), st.floats(allow_nan=False, allow_infinity=False)).map(str)
    amount = st.one_of(amount_str, amount_wrong)

    # Define a strategy for "id" field: mostly integer, sometimes string (wrong type)
    id_int = st.integers(min_value=0, max_value=2**31-1).map(str)
    id_wrong = st.text(min_size=1, max_size=10).map(lambda s: '"' + s.replace('"', '\\"') + '"')
    id_field = st.one_of(id_int, id_wrong)

    # "name" field: string or null normally, sometimes number (wrong type)
    name_str = st.one_of(st.none(), st.text(min_size=0, max_size=20)).map(
        lambda v: "null" if v is None else '"' + v.replace('"', '\\"') + '"')
    name_wrong = st.one_of(st.integers(), st.floats(allow_nan=False, allow_infinity=False)).map(str)
    name_field = st.one_of(name_str, name_wrong)

    # "status" field: mostly correct enum string, sometimes wrong string
    status_correct = statuses
    status_wrong = st.text(min_size=1, max_size=10).filter(lambda s: s not in ['active', 'inactive', 'unknown']).map(
        lambda s: '"' + s.replace('"', '\\"') + '"')
    status_field = st.one_of(status_correct, status_wrong)

    # "tags" field: mostly array of strings, sometimes array of numbers (wrong type)
    tags_str = tags
    tags_wrong = st.lists(st.one_of(st.integers(), st.floats(allow_nan=False, allow_infinity=False)).map(str),
                         min_size=0, max_size=5).map(lambda lst: '[' + ','.join(lst) + ']')
    tags_field = st.one_of(tags_str, tags_wrong)

    # Recursive record for "child" field, one level only
    # We build a helper function to generate a record string (not bytes)
    def record_str():
        # Compose fields with the above strategies
        return st.deferred(lambda: st.tuples(
            id_field,
            amount,
            name_field,
            status_field,
            tags_field,
            st.one_of(st.just("null"), record_str())
        ).map(lambda t:
            '{'
            + '"id":' + t[0] + ','
            + '"amount":' + t[1] + ','
            + '"name":' + t[2] + ','
            + '"status":' + t[3] + ','
            + '"tags":' + t[4] + ','
            + '"child":' + t[5]
            + '}'
        ))

    # Generate top-level record string
    top_record = record_str()

    # Draw the string and encode as UTF-8 bytes
    s = draw(top_record)
    return s.encode('utf-8')