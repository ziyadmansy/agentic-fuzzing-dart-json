from hypothesis import strategies as st

# We produce syntactically valid JSON objects as strings (bytes),
# with fields id, amount, name, status, tags, child.
# We vary one or two fields at a time from a valid baseline to induce divergences.
# We use bounded recursion for child (depth ≤ 1).
# We exploit known divergences:
# - tags missing accepted only by built_value
# - id as double accepted only by json_serializable/freezed, rejected by manual/built_value
# - name and child nullable, missing accepted by all
# - status must be one of three strings, else all reject
# - extra unknown keys accepted by all, no divergence
# - null for non-nullable fields rejected by all
# - id out-of-range int encoded as double saturates in json_serializable/freezed but rejected by manual/built_value
# We produce JSON text manually, no json module.

# Helpers to produce JSON text for values:
def json_string(s: str) -> str:
    # Escape minimal for JSON string: backslash and quote
    # Also escape control chars \b \f \n \r \t for safety
    # We keep it simple: replace \, ", and control chars with escapes
    esc = s.replace('\\', '\\\\').replace('"', '\\"')
    esc = esc.replace('\b', '\\b').replace('\f', '\\f').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
    return '"' + esc + '"'

def json_int(i: int) -> str:
    return str(i)

def json_double(d: float) -> str:
    # Use repr to get a JSON-compatible double representation
    # repr(float) always uses decimal or scientific notation
    return repr(d)

def json_null() -> str:
    return "null"

def json_array(elems: list[str]) -> str:
    return "[" + ",".join(elems) + "]"

def json_object(pairs: list[tuple[str, str]]) -> str:
    # pairs: list of (key, value) strings (key without quotes, value with quotes or literals)
    # keys must be quoted JSON strings
    return "{" + ",".join(json_string(k) + ":" + v for k, v in pairs) + "}"

@st.composite
def generated_json(draw) -> bytes:
    # Baseline valid values:
    # id: int64 in range [-2**53, 2**53] (safe for JSON numbers)
    # amount: string decimal, e.g. "123.45"
    # name: string or null
    # status: one of "active", "inactive", "unknown"
    # tags: array of strings (possibly empty)
    # child: null or one-level nested record (same schema but no further recursion)
    # We produce a dict as JSON text string, then encode utf-8 bytes.

    # To induce divergences, we pick one or two fields to vary from baseline:
    # 1) tags missing (only built_value accepts)
    # 2) id as double (json_serializable/freezed accept, manual/built_value reject)
    # 3) id as int out of 64-bit range encoded as double (same as above but edge)
    # 4) name missing (all accept, no divergence)
    # 5) child missing (all accept, no divergence)
    # 6) tags empty list (all accept)
    # 7) tags null (all reject)
    # 8) status invalid string (all reject)
    # 9) extra unknown key (all accept, no divergence)
    # 10) id null (all reject)
    # 11) amount null or wrong type (all reject)
    # 12) child present but null (all accept)
    # 13) child present with one-level nested record (vary child fields similarly but no recursion beyond one level)

    # We focus on 1,2,3 for divergences, plus baseline valid.

    # Define baseline valid fields:
    id_int = draw(st.integers(min_value=0, max_value=2**53))
    amount_str = draw(st.text(min_size=1).filter(lambda s: all(c in "0123456789." for c in s) and s.count('.') <= 1))
    # To avoid empty or invalid decimals, fallback to "123.45" if empty or invalid
    if not amount_str or amount_str == "." or amount_str.startswith(".") or amount_str.endswith("."):
        amount_str = "123.45"
    name_val = draw(st.one_of(st.none(), st.text(min_size=1, max_size=10)))
    status_val = draw(st.sampled_from(["active", "inactive", "unknown"]))
    tags_val = draw(st.lists(st.text(min_size=1, max_size=10), max_size=3))
    # child: null or one-level nested record with baseline values but no recursion beyond one level
    def gen_child():
        child_id = draw(st.integers(min_value=0, max_value=2**53))
        child_amount = draw(st.just("0.0"))
        child_name = draw(st.one_of(st.none(), st.text(min_size=1, max_size=5)))
        child_status = draw(st.sampled_from(["active", "inactive", "unknown"]))
        child_tags = draw(st.lists(st.text(min_size=1, max_size=5), max_size=2))
        # child.child is always null (no deeper recursion)
        child_obj = [
            ("id", json_int(child_id)),
            ("amount", json_string(child_amount)),
            ("name", json_null() if child_name is None else json_string(child_name)),
            ("status", json_string(child_status)),
            ("tags", json_array([json_string(t) for t in child_tags])),
            ("child", json_null()),
        ]
        return json_object(child_obj)

    child_val = draw(st.one_of(st.none(), gen_child()))

    # Now choose a variation mode to induce divergences or baseline valid:
    variation = draw(st.sampled_from([
        "baseline_valid",
        "tags_missing",
        "id_double",
        "id_double_out_of_range",
        "tags_null",
        "status_invalid",
        "id_null",
        "amount_null",
        "extra_unknown_key",
    ]))

    # Compose fields according to variation:
    # Start with baseline fields as JSON text:
    def id_as_int(i: int) -> str:
        return json_int(i)

    def id_as_double(i: int) -> str:
        # Encode int as double float
        # For out-of-range, use > 2**63 or < -2**63 to saturate behavior
        return json_double(float(i))

    # Out-of-range int for 64-bit: use 2**63 + 1000 (larger than max int64)
    out_of_range_int = 2**63 + 1000

    # Build fields dict (key -> JSON text value)
    fields = {}

    # id field:
    if variation == "id_double":
        # id as double within safe range
        fields["id"] = id_as_double(id_int)
    elif variation == "id_double_out_of_range":
        # id as double out of 64-bit range
        fields["id"] = id_as_double(out_of_range_int)
    elif variation == "id_null":
        fields["id"] = json_null()
    else:
        # baseline or other variations: id as int
        fields["id"] = id_as_int(id_int)

    # amount field:
    if variation == "amount_null":
        fields["amount"] = json_null()
    else:
        fields["amount"] = json_string(amount_str)

    # name field:
    # Always present (nullable), no missing name variation to avoid no divergence
    fields["name"] = json_null() if name_val is None else json_string(name_val)

    # status field:
    if variation == "status_invalid":
        # invalid string not in allowed set
        fields["status"] = json_string("invalid_status")
    else:
        fields["status"] = json_string(status_val)

    # tags field:
    if variation == "tags_missing":
        # omit tags field entirely
        pass
    elif variation == "tags_null":
        fields["tags"] = json_null()
    else:
        # present tags as array of strings (possibly empty)
        fields["tags"] = json_array([json_string(t) for t in tags_val])

    # child field:
    # Always present (nullable)
    fields["child"] = json_null() if child_val is None else child_val

    # extra unknown key variation:
    if variation == "extra_unknown_key":
        fields["extra_unknown"] = json_string("extra")

    # Compose JSON object text:
    # keys in stable order for reproducibility:
    keys_order = ["id", "amount", "name", "status", "tags", "child"]
    if "extra_unknown" in fields:
        keys_order.append("extra_unknown")

    pairs = [(k, fields[k]) for k in keys_order if k in fields]

    json_text = json_object(pairs)

    return json_text.encode("utf-8")