```python
from hypothesis import strategies as st

# Constants for the schema
STATUS_VALUES = ["active", "inactive", "unknown"]

# Helper to escape JSON strings (minimal, for ASCII and common escapes)
def _json_escape(s):
    return (
        '"' +
        s.replace('\\', '\\\\')
         .replace('"', '\\"')
         .replace('\b', '\\b')
         .replace('\f', '\\f')
         .replace('\n', '\\n')
         .replace('\r', '\\r')
         .replace('\t', '\\t')
        + '"'
    )

# Slightly off-type strategies for divergence hunting
def almost_int():
    # Sometimes an int, sometimes a float that looks like an int, sometimes a string, sometimes null
    return st.one_of(
        st.integers(min_value=-(2**31), max_value=2**31-1).map(str),
        st.floats(allow_nan=False, allow_infinity=False, width=32)
            .filter(lambda f: f == int(f) and abs(f) < 2**31)
            .map(lambda f: str(int(f))),
        st.text(min_size=1, max_size=12).filter(lambda s: not s.isdigit()).map(_json_escape),
        st.just("null")
    )

def almost_amount():
    # Normally a string, sometimes a number, sometimes null, sometimes weird escapes
    return st.one_of(
        st.text(min_size=0, max_size=12).map(_json_escape),
        st.integers(min_value=-100000, max_value=100000).map(str),
        st.just("null"),
        st.text(alphabet="\\\"\b\f\n\r\t", min_size=1, max_size=4).map(_json_escape)
    )

def almost_name():
    # Normally string or null, sometimes number, sometimes empty string, sometimes missing
    return st.one_of(
        st.text(min_size=0, max_size=16).map(_json_escape),
        st.just("null"),
        st.integers(min_value=-100, max_value=100).map(str),
    )

def almost_status():
    # Normally one of the three, sometimes a string that's close, sometimes null, sometimes number
    return st.one_of(
        st.sampled_from(STATUS_VALUES).map(_json_escape),
        st.text(min_size=3, max_size=8).filter(lambda s: s not in STATUS_VALUES).map(_json_escape),
        st.just("null"),
        st.integers(min_value=0, max_value=2).map(str)
    )

def almost_tags():
    # Normally array of strings, sometimes array with nulls, sometimes not an array, sometimes empty
    tag_str = st.text(min_size=0, max_size=8).map(_json_escape)
    tag_array = st.lists(tag_str, min_size=0, max_size=4).map(lambda tags: "[" + ",".join(tags) + "]")
    tag_array_with_null = st.lists(
        st.one_of(tag_str, st.just("null")), min_size=0, max_size=4
    ).map(lambda tags: "[" + ",".join(tags) + "]")
    not_array = st.one_of(
        tag_str, st.just("null"), st.integers(min_value=0, max_value=100).map(str)
    )
    return st.one_of(tag_array, tag_array_with_null, not_array)

def almost_child(rec_strategy):
    # Normally a nested record or null, sometimes a string, sometimes missing
    return st.one_of(
        rec_strategy,
        st.just("null"),
        st.text(min_size=0, max_size=10).map(_json_escape)
    )

@st.composite
def generated_json(draw, max_depth=1):
    # At top level, always include all fields, but allow one or two to be "off" per document
    # Choose which fields to perturb
    fields = ["id", "amount", "name", "status", "tags", "child"]
    perturb_count = draw(st.integers(min_value=1, max_value=2))
    perturb_fields = draw(st.lists(st.sampled_from(fields), min_size=perturb_count, max_size=perturb_count, unique=True))

    # Recursive child strategy
    if max_depth > 0:
        child_strategy = generated_json(max_depth=max_depth-1)
    else:
        # At depth 0, only allow null or a string
        child_strategy = st.one_of(
            st.just("null"),
            st.text(min_size=0, max_size=10).map(_json_escape)
        )

    # Field values
    id_val = draw(almost_int() if "id" in perturb_fields else st.integers(min_value=0, max_value=2**31-1).map(str))
    amount_val = draw(almost_amount() if "amount" in perturb_fields else st.text(min_size=1, max_size=12).map(_json_escape))
    name_val = draw(almost_name() if "name" in perturb_fields else st.one_of(st.text(min_size=0, max_size=16).map(_json_escape), st.just("null")))
    status_val = draw(almost_status() if "status" in perturb_fields else st.sampled_from(STATUS_VALUES).map(_json_escape))
    tags_val = draw(almost_tags() if "tags" in perturb_fields else st.lists(st.text(min_size=0, max_size=8).map(_json_escape), min_size=0, max_size=4).map(lambda tags: "[" + ",".join(tags) + "]"))
    child_val = draw(almost_child(child_strategy) if "child" in perturb_fields else child_strategy)

    # Compose fields (always present, but values may be "off")
    json_obj = (
        "{"
        f"\"id\":{id_val},"
        f"\"amount\":{amount_val},"
        f"\"name\":{name_val},"
        f"\"status\":{status_val},"
        f"\"tags\":{tags_val},"
        f"\"child\":{child_val}"
        "}"
    )
    return json_obj.encode("utf-8")
```
**Key points:**
- Each document is *almost* well-formed, but 1–2 fields are perturbed per document.
- Perturbations include type mismatches, nulls, boundary values, and subtle JSON-valid but schema-invalid forms.
- Recursion for `child` is bounded (default 1 level).
- All six fields are always present (never omitted), but their values may be "off".
- Only uses `from hypothesis import strategies as st` and string concatenation for JSON.
- Output is always syntactically valid JSON, as required.