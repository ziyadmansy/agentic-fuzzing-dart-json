from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic atomic fields with slight type fuzzing to induce divergence:
    # id: usually int, sometimes stringified int (should be int)
    id_val = draw(
        st.one_of(
            st.integers(min_value=0, max_value=1000),
            st.text(min_size=1, max_size=4).filter(lambda s: s.isdigit())
        )
    )
    # amount: usually string representing a number, sometimes a number (should be string)
    amount_val = draw(
        st.one_of(
            st.text(min_size=1, max_size=6).filter(lambda s: all(c in "0123456789." for c in s)),
            st.floats(min_value=0, max_value=10000).map(lambda f: str(round(f, 2))),
            st.integers(min_value=0, max_value=10000).map(str),
            st.floats(min_value=0, max_value=10000)  # raw float, not string
        )
    )
    # name: string or null, sometimes number or boolean to induce divergence
    name_val = draw(
        st.one_of(
            st.none(),
            st.text(min_size=0, max_size=10),
            st.integers(min_value=0, max_value=100),
            st.booleans()
        )
    )
    # status: one of the three strings, or a wrong string, or null
    status_val = draw(
        st.one_of(
            st.sampled_from(["active", "inactive", "unknown"]),
            st.text(min_size=1, max_size=7).filter(lambda s: s not in {"active", "inactive", "unknown"}),
            st.none()
        )
    )
    # tags: array of strings, or array of ints, or null, or empty array
    tags_val = draw(
        st.one_of(
            st.lists(st.text(min_size=1, max_size=5), min_size=0, max_size=3),
            st.lists(st.integers(min_value=0, max_value=10), min_size=0, max_size=3),
            st.none()
        )
    )

    # child: either null or a nested record with one level of recursion
    # To keep recursion bounded, child can be null or a record with child=null only
    def record_strategy(depth=0):
        if depth > 0:
            # child must be null at depth > 0
            return st.fixed_dictionaries({
                "id": st.integers(min_value=0, max_value=1000),
                "amount": st.text(min_size=1, max_size=6).filter(lambda s: all(c in "0123456789." for c in s)),
                "name": st.one_of(st.none(), st.text(min_size=0, max_size=10)),
                "status": st.sampled_from(["active", "inactive", "unknown"]),
                "tags": st.lists(st.text(min_size=1, max_size=5), min_size=0, max_size=3),
                "child": st.none()
            })
        else:
            # At top level, child can be null or nested record with child=null
            return st.one_of(
                st.none(),
                st.fixed_dictionaries({
                    "id": st.integers(min_value=0, max_value=1000),
                    "amount": st.text(min_size=1, max_size=6).filter(lambda s: all(c in "0123456789." for c in s)),
                    "name": st.one_of(st.none(), st.text(min_size=0, max_size=10)),
                    "status": st.sampled_from(["active", "inactive", "unknown"]),
                    "tags": st.lists(st.text(min_size=1, max_size=5), min_size=0, max_size=3),
                    "child": st.none()
                })
            )

    child_val = draw(record_strategy(depth=0))

    # Helper to serialize a Python value to JSON text (string concatenation)
    def to_json(val):
        if val is None:
            return "null"
        elif isinstance(val, bool):
            return "true" if val else "false"
        elif isinstance(val, int):
            return str(val)
        elif isinstance(val, float):
            # JSON floats use decimal point, no trailing .0 if possible
            s = repr(val)
            if "e" in s or "E" in s:
                # convert scientific notation to decimal if possible
                try:
                    f = float(s)
                    s = format(f, 'f')
                except Exception:
                    pass
            return s
        elif isinstance(val, str):
            # escape quotes and backslashes minimally
            esc = val.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{esc}"'
        elif isinstance(val, list):
            return "[" + ",".join(to_json(x) for x in val) + "]"
        elif isinstance(val, dict):
            items = []
            for k, v in val.items():
                items.append(to_json(k) + ":" + to_json(v))
            return "{" + ",".join(items) + "}"
        else:
            # fallback to string
            esc = str(val).replace("\\", "\\\\").replace('"', '\\"')
            return f'"{esc}"'

    # Compose the top-level dict with all fields
    top_level = {
        "id": id_val,
        "amount": amount_val,
        "name": name_val,
        "status": status_val,
        "tags": tags_val,
        "child": child_val
    }

    json_text = to_json(top_level)
    return json_text.encode("utf-8")