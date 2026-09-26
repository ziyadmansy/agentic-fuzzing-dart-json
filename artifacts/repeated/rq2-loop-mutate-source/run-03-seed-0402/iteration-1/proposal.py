from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Constants
    statuses = ['"active"', '"inactive"', '"unknown"']

    # Helpers to produce JSON text for each field, with slight type variations to induce divergence

    # id: normally integer, but try also stringified integer or float to cause divergence
    id_val = draw(st.one_of(
        st.integers(min_value=0, max_value=2**31-1).map(str),
        st.integers(min_value=0, max_value=2**31-1).map(lambda i: f'"{i}"'),  # string instead of int
        st.floats(min_value=0, max_value=2**31-1, allow_nan=False, allow_infinity=False).map(lambda f: f'{f:.1f}')  # float instead of int
    ))

    # amount: string, but try normal decimal strings and also numeric strings with leading zeros or empty string
    amount_val = draw(st.one_of(
        st.decimals(min_value=0, max_value=1e6, places=2).map(lambda d: f'"{d}"'),
        st.text(min_size=0, max_size=0).map(lambda s: '""'),  # empty string
        st.text(min_size=1, max_size=5).filter(lambda s: all(c in '0123456789' for c in s)).map(lambda s: f'"{s}"'),  # numeric string, possibly with leading zeros
    ))

    # name: string or null, but also try empty string, whitespace string, or number as string to cause divergence
    name_val = draw(st.one_of(
        st.none().map(lambda _: 'null'),
        st.text(min_size=1, max_size=10).map(lambda s: '"' + s.replace('"', '\\"') + '"'),
        st.just('""'),  # empty string
        st.just('"   "'),  # whitespace string
        st.integers(min_value=0, max_value=100).map(lambda i: f'"{i}"'),  # numeric string
    ))

    # status: one of the three strings, but also try uppercase, misspelled, or number to cause divergence
    status_val = draw(st.one_of(
        st.sampled_from(statuses),
        st.sampled_from(['"Active"', '"INACTIVE"', '"Unknown"']),  # case variants
        st.sampled_from(['"actve"', '"inactiv"', '"unkown"']),  # misspellings
        st.integers(min_value=0, max_value=2).map(str),  # number instead of string
    ))

    # tags: array of strings, but also try empty array, array with null, array with numbers, or single string instead of array
    tags_val = draw(st.one_of(
        st.lists(st.text(min_size=1, max_size=5).filter(lambda s: '"' not in s), min_size=0, max_size=3).map(
            lambda lst: '[' + ','.join('"' + t + '"' for t in lst) + ']'),
        st.just('[]'),
        st.lists(st.one_of(
            st.text(min_size=1, max_size=5).filter(lambda s: '"' not in s).map(lambda s: '"' + s + '"'),
            st.just('null'),
            st.integers(min_value=0, max_value=100).map(str)
        ), min_size=1, max_size=3).map(lambda lst: '[' + ','.join(lst) + ']'),
        st.text(min_size=1, max_size=5).filter(lambda s: '"' not in s).map(lambda s: '"' + s + '"'),  # string instead of array
    ))

    # child: either null or a nested record (one level only)
    # To keep recursion bounded, child record fields are simpler and less variant
    def child_record():
        child_id = draw(st.integers(min_value=0, max_value=100).map(str))
        child_amount = draw(st.decimals(min_value=0, max_value=1000, places=2).map(lambda d: f'"{d}"'))
        child_name = draw(st.one_of(st.none().map(lambda _: 'null'), st.text(min_size=1, max_size=5).map(lambda s: '"' + s.replace('"', '\\"') + '"')))
        child_status = draw(st.sampled_from(statuses))
        child_tags = draw(st.lists(st.text(min_size=1, max_size=3).filter(lambda s: '"' not in s), min_size=0, max_size=2).map(
            lambda lst: '[' + ','.join('"' + t + '"' for t in lst) + ']'))
        # child of child is always null to avoid deep recursion
        return '{' + \
            f'"id":{child_id},' + \
            f'"amount":{child_amount},' + \
            f'"name":{child_name},' + \
            f'"status":{child_status},' + \
            f'"tags":{child_tags},' + \
            f'"child":null' + \
            '}'

    child_val = draw(st.one_of(
        st.just('null'),
        st.deferred(child_record)
    ))

    # Compose full JSON object text
    json_text = '{' + \
        f'"id":{id_val},' + \
        f'"amount":{amount_val},' + \
        f'"name":{name_val},' + \
        f'"status":{status_val},' + \
        f'"tags":{tags_val},' + \
        f'"child":{child_val}' + \
        '}'

    return json_text.encode('utf-8')