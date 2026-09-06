from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base primitives as JSON text
    def json_str(s: str) -> str:
        # Minimal escaping for JSON string (only backslash and quote)
        esc = s.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{esc}"'

    def json_int(i: int) -> str:
        return str(i)

    def json_null() -> str:
        return "null"

    def json_array(elems: list[str]) -> str:
        return "[" + ",".join(elems) + "]"

    def json_obj(pairs: list[tuple[str, str]]) -> str:
        # pairs: list of (key, json_value_text)
        # keys must be strings, no escaping needed as keys are fixed schema keys
        return "{" + ",".join(f'"{k}":{v}' for k, v in pairs) + "}"

    # id: integer, but to induce divergence, sometimes encode as string or float string
    # amount: string normally, but sometimes null or number string
    # name: string or null, sometimes number or boolean to induce divergence
    # status: one of "active", "inactive", "unknown", but sometimes null or other string
    # tags: array of strings, sometimes empty, sometimes array with null or numbers
    # child: null or nested record (one level recursion only)

    # To induce divergence, we vary types subtly:
    # - id: int or stringified int or float string
    # - amount: string or number or null
    # - name: string or null or number or boolean
    # - status: correct enum string or null or unknown string
    # - tags: array of strings or array with null or numbers or empty
    # - child: null or nested record (one level only)

    # Limit recursion depth to 1
    def gen_record(depth: int) -> st.SearchStrategy[str]:
        # id field
        id_int = st.integers(min_value=0, max_value=10000)
        id_as_int = id_int.map(json_int)
        id_as_str = id_int.map(lambda i: json_str(str(i)))
        id_as_float_str = id_int.map(lambda i: json_str(f"{float(i)}"))

        id_choice = st.one_of(id_as_int, id_as_str, id_as_float_str)

        # amount field: normally string, but sometimes number string or null
        amount_str = st.text(min_size=1, max_size=10).map(json_str)
        amount_num_str = st.floats(allow_nan=False, allow_infinity=False).map(lambda f: json_str(str(f)))
        amount_null = st.just(json_null())
        amount_choice = st.one_of(amount_str, amount_num_str, amount_null)

        # name field: string or null or number or boolean
        name_str = st.one_of(st.none(), st.text(min_size=0, max_size=10)).map(
            lambda v: json_null() if v is None else json_str(v)
        )
        name_num = st.integers(min_value=-100, max_value=100).map(json_int)
        name_bool = st.booleans().map(lambda b: "true" if b else "false")
        # name_bool returns JSON boolean as text (not quoted)
        name_choice = st.one_of(name_str, name_num, name_bool)

        # status field: correct enum or null or unknown string
        status_enum = st.sampled_from(["active", "inactive", "unknown"]).map(json_str)
        status_null = st.just(json_null())
        status_other_str = st.text(min_size=1, max_size=10).filter(lambda s: s not in {"active", "inactive", "unknown"}).map(json_str)
        status_choice = st.one_of(status_enum, status_null, status_other_str)

        # tags field: array of strings, sometimes with null or numbers or empty
        tag_str = st.text(min_size=0, max_size=10).map(json_str)
        tag_null = st.just(json_null())
        tag_num = st.integers(min_value=-10, max_value=10).map(json_int)
        tag_elem = st.one_of(tag_str, tag_null, tag_num)
        tags_arr = st.lists(tag_elem, min_size=0, max_size=5).map(json_array)

        # child field: null or nested record (depth limit)
        if depth > 0:
            child_null = st.just(json_null())
            child_rec = gen_record(depth - 1)
            child_choice = st.one_of(child_null, child_rec)
        else:
            child_choice = st.just(json_null())

        # Compose record fields
        return st.tuples(id_choice, amount_choice, name_choice, status_choice, tags_arr, child_choice).map(
            lambda fields: json_obj([
                ("id", fields[0]),
                ("amount", fields[1]),
                ("name", fields[2]),
                ("status", fields[3]),
                ("tags", fields[4]),
                ("child", fields[5]),
            ])
        )

    # Generate top-level record with depth=1 recursion
    json_text = draw(gen_record(depth=1))
    return json_text.encode("utf-8")