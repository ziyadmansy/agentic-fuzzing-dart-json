from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic building blocks for fields:
    # id: integer (always present)
    id_strat = st.integers(min_value=-(2**31), max_value=2**31-1)
    
    # amount: string, but we will sometimes produce non-string to cause divergence
    # Mostly strings, sometimes integers or null to cause divergence
    amount_strat = st.one_of(
        st.text(min_size=1, max_size=10),
        st.integers(min_value=-1000, max_value=1000).map(str),
        st.integers(min_value=-1000, max_value=1000),  # integer instead of string
        st.just(None),  # null instead of string
    )
    
    # name: string or null, sometimes missing or wrong type
    name_strat = st.one_of(
        st.none(),
        st.text(min_size=0, max_size=20),
        st.integers(min_value=0, max_value=1000),  # wrong type
    )
    
    # status: one of "active", "inactive", "unknown"
    # sometimes wrong string, sometimes null, sometimes integer
    status_strat = st.one_of(
        st.sampled_from(["active", "inactive", "unknown"]),
        st.text(min_size=1, max_size=10).filter(lambda s: s not in {"active","inactive","unknown"}),
        st.none(),
        st.integers(min_value=0, max_value=10),
    )
    
    # tags: array of strings, sometimes empty, sometimes null, sometimes array with non-string
    tags_strat = st.one_of(
        st.lists(st.text(min_size=0, max_size=10), max_size=5),
        st.lists(st.one_of(st.text(min_size=0, max_size=10), st.integers()), max_size=5),
        st.none(),
    )
    
    # child: either null or a nested record (one level only)
    # We build a nested record with the same schema but no further nesting (child=null)
    # To keep recursion bounded, child.child is always null.
    # We will sometimes produce wrong types or missing fields in child to cause divergence.
    
    # Helper to build a record JSON string from fields (all fields present)
    def record_json(idv, amountv, namev, statusv, tagsv, childv):
        # idv: int or something else
        # amountv: string or something else
        # namev: string or null or something else
        # statusv: string or something else
        # tagsv: list or null or something else
        # childv: string or null or something else (already JSON text)
        
        # id field: always output as number or something else
        if isinstance(idv, int):
            id_json = str(idv)
        elif idv is None:
            id_json = "null"
        elif isinstance(idv, str):
            # if string, quote it
            id_json = '"' + idv.replace('"', '\\"') + '"'
        else:
            # fallback: repr as string
            id_json = '"' + str(idv).replace('"', '\\"') + '"'
        
        # amount field: if string, quote; else output JSON null or number
        if isinstance(amountv, str):
            amount_json = '"' + amountv.replace('"', '\\"') + '"'
        elif amountv is None:
            amount_json = "null"
        elif isinstance(amountv, int):
            amount_json = str(amountv)
        else:
            amount_json = '"' + str(amountv).replace('"', '\\"') + '"'
        
        # name field: string or null or other
        if namev is None:
            name_json = "null"
        elif isinstance(namev, str):
            name_json = '"' + namev.replace('"', '\\"') + '"'
        elif isinstance(namev, int):
            name_json = str(namev)
        else:
            name_json = '"' + str(namev).replace('"', '\\"') + '"'
        
        # status field: string or null or other
        if statusv is None:
            status_json = "null"
        elif isinstance(statusv, str):
            status_json = '"' + statusv.replace('"', '\\"') + '"'
        elif isinstance(statusv, int):
            status_json = str(statusv)
        else:
            status_json = '"' + str(statusv).replace('"', '\\"') + '"'
        
        # tags field: list or null or other
        if tagsv is None:
            tags_json = "null"
        elif isinstance(tagsv, list):
            # each element string or int or other
            elems = []
            for e in tagsv:
                if isinstance(e, str):
                    elems.append('"' + e.replace('"', '\\"') + '"')
                elif isinstance(e, int):
                    elems.append(str(e))
                elif e is None:
                    elems.append("null")
                else:
                    elems.append('"' + str(e).replace('"', '\\"') + '"')
            tags_json = "[" + ",".join(elems) + "]"
        else:
            # fallback: string quoted
            tags_json = '"' + str(tagsv).replace('"', '\\"') + '"'
        
        # child field: either "null" or a JSON object string
        if childv is None:
            child_json = "null"
        else:
            child_json = childv
        
        # Compose full JSON object string
        json_text = (
            '{'
            + '"id":' + id_json + ','
            + '"amount":' + amount_json + ','
            + '"name":' + name_json + ','
            + '"status":' + status_json + ','
            + '"tags":' + tags_json + ','
            + '"child":' + child_json
            + '}'
        )
        return json_text
    
    # Draw fields for top-level record
    idv = draw(id_strat)
    amountv = draw(amount_strat)
    namev = draw(name_strat)
    statusv = draw(status_strat)
    tagsv = draw(tags_strat)
    
    # Draw child record or null
    # 50% chance null, else nested record with no further nesting (child=null)
    child_is_null = draw(st.booleans())
    if child_is_null:
        childv = None
    else:
        # Nested record fields, but with less chance of wrong types to keep bounded complexity
        cidv = draw(id_strat)
        camountv = draw(st.one_of(
            st.text(min_size=1, max_size=10),
            st.integers(min_value=-1000, max_value=1000).map(str),
            st.just(None),
        ))
        cnamev = draw(st.one_of(st.none(), st.text(min_size=0, max_size=20)))
        cstatusv = draw(st.sampled_from(["active", "inactive", "unknown"]))
        ctagsv = draw(st.lists(st.text(min_size=0, max_size=10), max_size=3))
        cchildv = "null"  # no further nesting
        
        childv = record_json(cidv, camountv, cnamev, cstatusv, ctagsv, cchildv)
    
    # Compose top-level JSON string
    json_str = record_json(idv, amountv, namev, statusv, tagsv, childv)
    
    return json_str.encode("utf-8")