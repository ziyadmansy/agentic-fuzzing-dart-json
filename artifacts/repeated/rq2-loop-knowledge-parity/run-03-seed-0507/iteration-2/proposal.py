from hypothesis import strategies as st

# We build JSON text by hand, carefully controlling field presence and types.
# We exploit known divergences:
# - tags missing: built_value accepts, others reject
# - id as double (e.g. 1.0): manual and built_value reject, json_serializable and freezed accept
# - id as int64-out-of-range encoded as double: manual and built_value get int64 min/max, others get original double->toInt()
# - nullable fields missing accepted by all
# - extra unknown keys accepted by all (no divergence)
# - wrong type or null for non-nullable fields rejected by all (no divergence)
# We produce mostly well-formed documents with exactly one subtle divergence trigger per document.

# Helper to produce JSON string literals with proper escaping of quotes and backslashes
def json_string_literal(s: str) -> str:
    # Escape backslash and double quote
    s = s.replace('\\', '\\\\').replace('"', '\\"')
    return '"' + s + '"'

# Recursive record generator, bounded to one level of recursion for "child"
@st.composite
def record(draw, allow_missing_tags=False, allow_id_double=False, allow_id_out_of_range=False):
    # id field: int normally, but sometimes double (e.g. 1.0) or out-of-range double
    # manual and built_value require int, json_serializable and freezed accept double and convert to int
    # We produce either:
    # - int in safe range
    # - double with .0 fractional part (e.g. 42.0)
    # - double out of int64 range (e.g. 2**63 as double)
    # We'll produce a union of these cases controlled by flags
    if allow_id_out_of_range:
        # Produce a double outside int64 range, as a JSON number with fractional .0
        # int64 max = 2**63 -1 = 9223372036854775807
        # We'll produce 2**63 = 9223372036854775808.0 (double)
        id_val = 9223372036854775808.0
        id_json = str(id_val)
    elif allow_id_double:
        # Produce a double with .0 fractional part inside int64 range
        id_int = draw(st.integers(min_value=0, max_value=1000))
        id_json = str(float(id_int))  # e.g. "42.0"
    else:
        # Produce a normal int in safe int64 range
        id_int = draw(st.integers(min_value=0, max_value=1000))
        id_json = str(id_int)

    # amount: string, always present, non-null
    amount_str = draw(st.text(min_size=1, max_size=10))
    amount_json = json_string_literal(amount_str)

    # name: nullable string, missing or null accepted by all
    # We produce either null, string, or missing (missing only if allowed)
    name_choice = draw(st.sampled_from(["string", "null", "missing"]))
    if name_choice == "string":
        name_val = draw(st.text(min_size=0, max_size=10))
        name_json = json_string_literal(name_val)
        name_field = '"name":' + name_json
    elif name_choice == "null":
        name_field = '"name":null'
    else:
        name_field = None  # missing

    # status: one of "active", "inactive", "unknown"
    status_val = draw(st.sampled_from(["active", "inactive", "unknown"]))
    status_json = json_string_literal(status_val)

    # tags: array of strings, always present normally
    # But if allow_missing_tags=True, we omit tags field to trigger built_value acceptance divergence
    if allow_missing_tags:
        tags_field = None
    else:
        tags_list = draw(st.lists(st.text(min_size=0, max_size=5), min_size=0, max_size=3))
        # encode as JSON array of strings
        tags_json_items = [json_string_literal(t) for t in tags_list]
        tags_json = "[" + ",".join(tags_json_items) + "]"
        tags_field = '"tags":' + tags_json

    # child: nullable record, missing or null accepted by all
    # We produce either null or a nested record (one level only)
    child_choice = draw(st.sampled_from(["null", "record", "missing"]))
    if child_choice == "null":
        child_field = '"child":null'
    elif child_choice == "record":
        # nested record: no tags missing, no id double, no out-of-range id to keep complexity low
        nested = draw(record(allow_missing_tags=False, allow_id_double=False, allow_id_out_of_range=False))
        child_field = '"child":' + nested
    else:
        child_field = None  # missing

    # Compose fields, always include id, amount, status
    # Include name, tags, child if present
    fields = [
        '"id":' + id_json,
        '"amount":' + amount_json,
        '"status":' + status_json,
    ]
    if name_field is not None:
        fields.append(name_field)
    if tags_field is not None:
        fields.append(tags_field)
    if child_field is not None:
        fields.append(child_field)

    # Shuffle fields order to avoid positional bias
    # Hypothesis does not have a shuffle strategy, so we do a simple random permutation
    fields = draw(st.permutations(fields))

    json_obj = "{" + ",".join(fields) + "}"
    return json_obj

@st.composite
def generated_json(draw) -> bytes:
    # We produce documents that are syntactically valid JSON objects,
    # mostly well-formed except for exactly one subtle divergence trigger:
    # - missing tags field (built_value accepts, others reject)
    # - id as double with .0 fractional (manual and built_value reject, others accept)
    # - id as out-of-range double (manual and built_value saturate, others accept original)
    # - normal well-formed document (control)
    divergence_case = draw(st.sampled_from([
        "missing_tags",
        "id_double",
        "id_out_of_range_double",
        "normal"
    ]))

    if divergence_case == "missing_tags":
        # tags missing triggers built_value accept, others reject
        json_obj = draw(record(allow_missing_tags=True, allow_id_double=False, allow_id_out_of_range=False))
    elif divergence_case == "id_double":
        # id as double inside int64 range triggers manual and built_value reject, others accept
        json_obj = draw(record(allow_missing_tags=False, allow_id_double=True, allow_id_out_of_range=False))
    elif divergence_case == "id_out_of_range_double":
        # id as double outside int64 range triggers saturation difference
        json_obj = draw(record(allow_missing_tags=False, allow_id_double=False, allow_id_out_of_range=True))
    else:
        # normal well-formed document, no divergence trigger
        json_obj = draw(record(allow_missing_tags=False, allow_id_double=False, allow_id_out_of_range=False))

    # Return bytes as required
    return json_obj.encode("utf-8")