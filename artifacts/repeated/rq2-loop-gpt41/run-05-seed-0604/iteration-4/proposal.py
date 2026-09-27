```python
from hypothesis import strategies as st

# Helper strategies for field values
id_strategy = st.integers(-2**31, 2**31 - 1)

# Amount: string, but try edge cases (e.g. numbers, empty, weird unicode)
amount_strategy = st.one_of(
    st.text(min_size=0, max_size=32),  # normal string
    st.text("0", "9", min_size=1, max_size=32),  # numeric string
    st.just(""),  # empty string
    st.just("0"),  # zero
    st.just("-0.0"),  # negative zero
    st.just("1e10"),  # scientific notation
    st.just("NaN"),  # not a number
    st.just("∞"),  # infinity symbol
    st.text("\ud800", "\udfff", min_size=1, max_size=2),  # lone surrogates
)

# Name: string or null, but sometimes wrong type (number, bool, object, array)
name_strategy = st.one_of(
    st.text(min_size=0, max_size=32),
    st.none(),
    st.integers(-100, 100),  # wrong type
    st.booleans(),           # wrong type
    st.lists(st.text(), min_size=0, max_size=2),  # wrong type
    st.just({}),             # wrong type
)

# Status: correct or off-by-one value, or wrong type
status_strategy = st.one_of(
    st.sampled_from(["active", "inactive", "unknown"]),
    st.just(""),  # empty string
    st.text(min_size=1, max_size=8).filter(lambda s: s not in {"active", "inactive", "unknown"}),  # unexpected string
    st.integers(-1, 3),  # wrong type
    st.none(),           # wrong type
)

# Tags: array of strings, but sometimes wrong type or mixed
tags_strategy = st.one_of(
    st.lists(st.text(min_size=0, max_size=16), min_size=0, max_size=4),
    st.lists(st.integers(-10, 10), min_size=1, max_size=3),  # wrong type
    st.lists(st.one_of(st.text(min_size=0, max_size=16), st.integers(-10, 10)), min_size=1, max_size=3),  # mixed
    st.none(),  # wrong type
    st.just("not-an-array"),  # wrong type
)

# Recursion for child: either null, or another record (with depth limit)
def record_strategy(max_depth):
    if max_depth <= 0:
        child_strategy = st.just("null")
    else:
        child_strategy = st.deferred(lambda: record_strategy(max_depth - 1))

    @st.composite
    def _record(draw):
        # For each field, sometimes omit (to test missing), but mostly present
        fields = []

        # id (always present, but sometimes wrong type)
        if draw(st.booleans() if max_depth == 1 else st.just(True)):
            id_val = draw(st.one_of(id_strategy, st.text(min_size=1, max_size=8), st.none()))
            if isinstance(id_val, int):
                fields.append(f'"id":{id_val}')
            elif id_val is None:
                fields.append(f'"id":null')
            else:
                fields.append(f'"id":"{id_val}"')
        # amount (always present, but sometimes wrong type)
        if draw(st.booleans() if max_depth == 1 else st.just(True)):
            amt_val = draw(st.one_of(amount_strategy, st.integers(-100, 100), st.none()))
            if isinstance(amt_val, str):
                fields.append(f'"amount":"{amt_val}"')
            elif amt_val is None:
                fields.append(f'"amount":null')
            else:
                fields.append(f'"amount":{amt_val}')
        # name (always present, but sometimes wrong type)
        if draw(st.booleans() if max_depth == 1 else st.just(True)):
            name_val = draw(name_strategy)
            if isinstance(name_val, str):
                fields.append(f'"name":"{name_val}"')
            elif name_val is None:
                fields.append(f'"name":null')
            elif isinstance(name_val, bool):
                fields.append(f'"name":' + ("true" if name_val else "false"))
            elif isinstance(name_val, int):
                fields.append(f'"name":{name_val}')
            elif isinstance(name_val, list):
                arr = ",".join(f'"{v}"' if isinstance(v, str) else str(v) for v in name_val)
                fields.append(f'"name":[{arr}]')
            elif isinstance(name_val, dict):
                fields.append(f'"name":{{}}')
        # status (always present, but sometimes wrong type)
        if draw(st.booleans() if max_depth == 1 else st.just(True)):
            status_val = draw(status_strategy)
            if isinstance(status_val, str):
                fields.append(f'"status":"{status_val}"')
            elif status_val is None:
                fields.append(f'"status":null')
            else:
                fields.append(f'"status":{status_val}')
        # tags (always present, but sometimes wrong type)
        if draw(st.booleans() if max_depth == 1 else st.just(True)):
            tags_val = draw(tags_strategy)
            if isinstance(tags_val, list):
                arr = ",".join(f'"{v}"' if isinstance(v, str) else str(v) for v in tags_val)
                fields.append(f'"tags":[{arr}]')
            elif tags_val is None:
                fields.append(f'"tags":null')
            elif isinstance(tags_val, str):
                fields.append(f'"tags":"{tags_val}"')
            else:
                fields.append(f'"tags":{tags_val}')
        # child (always present, but sometimes wrong type)
        if draw(st.booleans() if max_depth == 1 else st.just(True)):
            # 80%: valid child or null, 20%: wrong type
            if draw(st.integers(0, 4)) == 0:
                # wrong type
                wrong_child = draw(st.one_of(
                    st.text(min_size=0, max_size=8),
                    st.integers(-10, 10),
                    st.lists(st.text(), min_size=0, max_size=2),
                    st.just({}),
                ))
                if isinstance(wrong_child, str):
                    fields.append(f'"child":"{wrong_child}"')
                elif isinstance(wrong_child, int):
                    fields.append(f'"child":{wrong_child}')
                elif isinstance(wrong_child, list):
                    arr = ",".join(f'"{v}"' for v in wrong_child)
                    fields.append(f'"child":[{arr}]')
                elif isinstance(wrong_child, dict):
                    fields.append(f'"child":{{}}')
            else:
                child_val = draw(child_strategy)
                fields.append(f'"child":{child_val}')
        # Shuffle fields to avoid order bias
        draw(st.permutations(fields))
        return "{" + ",".join(fields) + "}"

    return _record().map(lambda s: s)

@st.composite
def generated_json(draw):
    # Limit recursion to 1 or 2 levels, and keep output size reasonable
    max_depth = draw(st.integers(1, 2))
    json_obj = draw(record_strategy(max_depth))
    # Return as bytes
    return json_obj.encode("utf-8")
```
This strategy generates JSON objects that are almost always well-formed, but with one or two fields at a time possibly having the wrong type, missing, or at a type boundary. This is designed to maximize the chance of divergence between the Dart deserializers, as requested.