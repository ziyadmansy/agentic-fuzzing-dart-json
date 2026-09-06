"""Schema-aware value generator for RQ2/RQ3 (docs/dart-oracle-design.md
Section 10). Unlike `json_strategy.py` (arbitrary grammar-valid JSON, used
for RQ1's pipeline-portability check), this always emits syntactically valid
JSON shaped like the harness's Record schema (`harness/lib/schema`, Section
3) and perturbs *values* -- dropping fields, wrong types, out-of-enum
strings, null-for-non-nullable, extra keys, deep recursion -- because Tier C
divergence can only be found at the schema level, never the syntax level
(Section 8, finding 1: all four paths share one `jsonDecode` gate).

Same `@st.composite def generated_json(draw) -> bytes` contract as the
original project (handoff Section 1.4) and this project's `json_strategy.py`,
so `proposal.py`'s `load_strategy`/`proposal_inputs` need no changes to drive
either one.
"""

import json

from hypothesis import strategies as st

STATUS_VALUES = ("active", "inactive", "unknown")

# Base generator's normal recursion cap vs. the perturbation layer's forced-
# deeper cap (Section 10, item 2: "an undiscovered Tier C variant the manual
# study didn't cover" -- do any of the four paths have a different effective
# depth limit than the others?).
_BASE_MAX_CHILD_DEPTH = 3
_FORCED_MAX_CHILD_DEPTH = 12

# Biased toward the magnitudes where Section 5's confirmed finding lives
# (double's 2^53 exact-integer boundary, 64-bit int boundaries, and well
# beyond both) rather than uniformly over a huge range, so the campaign
# spends its budget where json_serializable/freezed's `.toInt()` saturation
# is actually exercised, not on magnitudes too small to trigger it.
_id_strategy = st.one_of(
    st.integers(min_value=-1_000_000, max_value=1_000_000),
    st.integers(min_value=2**53 - 4, max_value=2**53 + 4),
    st.integers(min_value=2**63 - 4, max_value=2**63 + 4),
    st.integers(min_value=-(2**63) - 4, max_value=-(2**63) + 4),
    st.integers(min_value=-(10**30), max_value=10**30),
)

_valid_status = st.sampled_from(STATUS_VALUES)
_invalid_status = st.text(min_size=1, max_size=16).filter(lambda s: s not in STATUS_VALUES)

_wrong_type_scalar = st.one_of(
    st.integers(min_value=-1000, max_value=1000),
    st.text(max_size=20),
    st.booleans(),
    st.none(),
    st.lists(st.integers(min_value=-10, max_value=10), max_size=3),
    st.fixed_dictionaries({}),
)

_FIELD_NAMES = ("id", "amount", "name", "status", "tags", "child")


def _valid_record(draw: st.DrawFn, depth: int) -> dict:
    child = None
    if depth > 0 and draw(st.booleans()):
        child = draw(_record_dict(depth - 1))
    return {
        "id": draw(_id_strategy),
        "amount": draw(st.text(min_size=0, max_size=12)),
        "name": draw(st.one_of(st.none(), st.text(max_size=40))),
        "status": draw(_valid_status),
        "tags": draw(st.lists(st.text(max_size=20), max_size=5)),
        "child": child,
    }


@st.composite
def _record_dict(draw: st.DrawFn, depth: int = _BASE_MAX_CHILD_DEPTH) -> dict:
    return _valid_record(draw, depth)


def _perturb(draw: st.DrawFn, record: dict) -> dict:
    """Apply zero or more schema-level perturbations, each independently
    probable, per docs/dart-oracle-design.md Section 10 item 2. Independence
    (rather than picking exactly one) matters: the strongest confirmed
    finding so far (RQ2's `tags`-dropped/built_value divergence) is a single-
    field drop, but real API responses often have more than one thing wrong
    at once, and the campaign should not systematically under-sample that."""
    result = dict(record)

    if draw(st.booleans()) and draw(st.integers(min_value=0, max_value=4)) == 0:
        # drop a field entirely -- the single highest-value perturbation
        # (found the tags/built_value divergence), kept well-represented
        field = draw(st.sampled_from(_FIELD_NAMES))
        result.pop(field, None)

    if draw(st.integers(min_value=0, max_value=6)) == 0:
        field = draw(st.sampled_from(_FIELD_NAMES))
        if field in result:
            result[field] = draw(_wrong_type_scalar)

    if draw(st.integers(min_value=0, max_value=6)) == 0:
        field = draw(st.sampled_from(_FIELD_NAMES))
        if field in result:
            result[field] = None

    if draw(st.integers(min_value=0, max_value=8)) == 0:
        result["status"] = draw(_invalid_status)

    if draw(st.integers(min_value=0, max_value=8)) == 0:
        extra_key = draw(st.text(min_size=1, max_size=10).filter(lambda s: s not in _FIELD_NAMES))
        result[extra_key] = draw(_wrong_type_scalar)

    if draw(st.integers(min_value=0, max_value=10)) == 0:
        # force a deeper recursion chain than the base generator's normal cap
        # -- see the module docstring's note on effective depth limits
        depth = draw(st.integers(min_value=_BASE_MAX_CHILD_DEPTH + 1, max_value=_FORCED_MAX_CHILD_DEPTH))
        result["child"] = draw(_record_dict(depth))

    return result


@st.composite
def generated_json(draw: st.DrawFn) -> bytes:
    """The RQ2/RQ3 baseline strategy: a schema-shaped record, independently
    perturbed. Contract matches the original project's `generated_json`
    exactly (handoff Section 1.4) so the refinement loop's proposer is asked
    to produce a drop-in replacement for this function, not a different one.
    """
    record = draw(_record_dict())
    record = _perturb(draw, record)
    return json.dumps(record, ensure_ascii=False).encode("utf-8")
