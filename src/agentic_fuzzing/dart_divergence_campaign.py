"""RQ2 campaign runner and summary (docs/dart-oracle-design.md Section 10).
Unlike RQ1's `dart_campaign.py` (which reuses the original project's
acceptance-rate `CampaignSummary` unchanged), RQ2's objective is cross-path
divergence, not acceptance -- so this module defines its own summary shape
and its own `build_refinement_prompt`/`run_refinement_loop`, following the
original's exact iteration-budget and error-handling pattern (handoff
Section 1.7) rather than forcing an unrelated metric through the reused one.
"""

from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Callable, Iterable

from .dart_runner import HarnessBatchResult, run_batch
from .proposal import GenerationError, proposal_inputs
from . import proposal_relaxed

_PATH_ORDER = ("A_manual", "B_json_serializable", "C_freezed", "D_built_value")

# `mutate_source`'s revert-on-regression guard (added after a held-out seed,
# artifacts/repeated/rq2-loop-mutate-source-smoke, showed the schema-evaluated
# fraction drop from 100% to ~70% starting iteration 3 and never recover --
# the proposer bolted a buggy branch onto its own prior generator and kept
# mutating forward from it rather than fixing or discarding it). A drop in
# schema-evaluated fraction larger than this, relative to the best fraction
# seen so far this run, reverts `last_source` to that best-known source for
# the next iteration instead of the just-produced (regressed) one.
_MUTATE_SOURCE_REGRESSION_THRESHOLD = 0.10


def run_campaign(
    executable: str,
    inputs: Iterable[bytes | GenerationError],
    output_path: Path,
    max_examples: int = 500,
    timeout_seconds: float = 5.0,
) -> Counter[str]:
    """Same batching strategy as `dart_campaign.run_campaign` (one harness
    invocation per campaign), but persists the *full* oracle result per line
    instead of collapsing it to accepted/rejected -- RQ2 needs the per-path
    breakdown, RQ1 does not."""
    counts: Counter[str] = Counter()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    items: list[bytes | GenerationError] = []
    for index, item in enumerate(inputs):
        if index >= max_examples:
            break
        items.append(item)

    data_items = [item for item in items if not isinstance(item, GenerationError)]
    if data_items:
        batch_timeout = max(30.0, timeout_seconds * len(data_items))
        batch = run_batch(executable, data_items, batch_timeout)
    else:
        batch = HarnessBatchResult(lines=[], timed_out=False, returncode=0)

    with output_path.open("w", encoding="utf-8") as output:
        response_iter = iter(batch.lines)
        for index, item in enumerate(items):
            if isinstance(item, GenerationError):
                counts["encoding_error"] += 1
                output.write(json.dumps(_generation_error_observation(index, item)) + "\n")
                continue

            response = next(response_iter, None)
            if response is None:
                status = "harness_timeout" if batch.timed_out else "harness_crash"
                counts[status] += 1
                output.write(
                    json.dumps(_harness_failure_observation(index, item, status, batch.returncode)) + "\n"
                )
                continue

            counts[response.get("status", "unknown")] += 1
            output.write(json.dumps(_observation(index, item, response)) + "\n")
    return counts


def _observation(index: int, data: bytes, response: dict) -> dict[str, object]:
    return {
        "index": index,
        "input_hex": data.hex(),
        "input_length": len(data),
        "harness_response": response,
    }


def _harness_failure_observation(
    index: int, data: bytes, status: str, returncode: int | None
) -> dict[str, object]:
    return {
        "index": index,
        "input_hex": data.hex(),
        "input_length": len(data),
        "harness_response": {"status": status, "returncode": returncode},
    }


def _generation_error_observation(index: int, error: GenerationError) -> dict[str, object]:
    return {
        "index": index,
        "input_hex": "",
        "input_length": 0,
        "harness_response": {"status": "encoding_error", "generation_error": error.error},
    }


@dataclass(frozen=True)
class DivergenceCampaignSummary:
    total: int
    top_level_counts: Counter[str]
    tier_b_counts: Counter[str]
    tier_c_accept_reject: int
    tier_c_value: int
    unique_divergence_signatures: int
    divergence_perturbation_categories: Counter[str]

    def as_dict(self) -> dict[str, object]:
        return {
            "total": self.total,
            "top_level_counts": dict(self.top_level_counts),
            "tier_b_counts": dict(self.tier_b_counts),
            "tier_c_accept_reject": self.tier_c_accept_reject,
            "tier_c_value": self.tier_c_value,
            "unique_divergence_signatures": self.unique_divergence_signatures,
            "divergence_perturbation_categories": dict(self.divergence_perturbation_categories),
        }


_SCHEMA_FIELDS = ("id", "amount", "name", "status", "tags", "child")
_NON_NULLABLE_FIELDS = ("id", "amount", "status", "tags")
_STATUS_VALUES = ("active", "inactive", "unknown")


def _classify_perturbations(document: object) -> set[str]:
    """Categorize what is unusual about a generated document, purely by
    inspecting its shape against the Section 3 schema -- independent of
    which generator (static or LLM-authored) produced it, since the LLM's
    own generator source is not something this pipeline can introspect.
    Used to feed the refined loop *categories* of perturbation associated
    with divergence, without naming the specific fields already known by
    hand (docs/dart-oracle-design.md Section 8's discipline for the
    original score-based prompt applies here too)."""
    categories: set[str] = set()
    if not isinstance(document, dict):
        return categories
    for field in _SCHEMA_FIELDS:
        if field not in document:
            categories.add("missing_field")
    for field in _NON_NULLABLE_FIELDS:
        if field in document and document[field] is None:
            categories.add("null_override")
    if "id" in document and document["id"] is not None and not isinstance(document["id"], int):
        categories.add("wrong_type")
    if "amount" in document and document["amount"] is not None and not isinstance(document["amount"], str):
        categories.add("wrong_type")
    if "name" in document and document["name"] is not None and not isinstance(document["name"], str):
        categories.add("wrong_type")
    if "tags" in document and document["tags"] is not None and not isinstance(document["tags"], list):
        categories.add("wrong_type")
    if "status" in document:
        status = document["status"]
        if isinstance(status, str) and status not in _STATUS_VALUES:
            categories.add("bad_enum")
        elif status is not None and not isinstance(status, str):
            categories.add("wrong_type")
    if "id" in document and isinstance(document["id"], int):
        magnitude = abs(document["id"])
        if magnitude >= 2**53 - 1024:
            categories.add("boundary_id")
    extra_keys = set(document.keys()) - set(_SCHEMA_FIELDS)
    if extra_keys:
        categories.add("extra_key")
    depth = 0
    node = document.get("child")
    while isinstance(node, dict):
        depth += 1
        node = node.get("child")
    if depth > 3:
        categories.add("deep_nesting")
    return categories


def _signature(response: dict) -> str | None:
    """A pattern string over the four paths' accept/reject status (e.g.
    'AARR'), with a ':value' suffix when all four accepted but disagreed on
    the decoded value -- otherwise an all-accept pattern ('AAAA') would be
    indistinguishable from a real value divergence. `None` for inputs that
    never reached the schema stage (nothing to diverge on)."""
    if response.get("status") != "schema_evaluated":
        return None
    by_path = {p["path"]: p for p in response["paths"]}
    pattern = "".join("A" if by_path[name]["status"] == "accepted" else "R" for name in _PATH_ORDER)
    if response.get("tier_c_divergence") == "value":
        pattern += ":value"
    return pattern


def summarize_records(records: Iterable[dict[str, object]]) -> DivergenceCampaignSummary:
    total = 0
    top_level_counts: Counter[str] = Counter()
    tier_b_counts: Counter[str] = Counter()
    tier_c_accept_reject = 0
    tier_c_value = 0
    signatures: set[str] = set()
    perturbation_categories: Counter[str] = Counter()
    for record in records:
        total += 1
        response = record["harness_response"]
        top_level_counts[str(response.get("status", "unknown"))] += 1
        if response.get("status") != "schema_evaluated":
            continue
        for path_name in response.get("tier_b_paths", []):
            tier_b_counts[path_name] += 1
        divergence = response.get("tier_c_divergence")
        if divergence == "accept_reject":
            tier_c_accept_reject += 1
        elif divergence == "value":
            tier_c_value += 1
        if divergence in ("accept_reject", "value"):
            input_hex = record.get("input_hex")
            if input_hex:
                try:
                    document = json.loads(bytes.fromhex(input_hex).decode("utf-8"))
                except (ValueError, UnicodeDecodeError):
                    document = None
                for category in _classify_perturbations(document):
                    perturbation_categories[category] += 1
        signature = _signature(response)
        if signature is not None:
            signatures.add(signature)
    return DivergenceCampaignSummary(
        total=total,
        top_level_counts=top_level_counts,
        tier_b_counts=tier_b_counts,
        tier_c_accept_reject=tier_c_accept_reject,
        tier_c_value=tier_c_value,
        unique_divergence_signatures=len(signatures),
        divergence_perturbation_categories=perturbation_categories,
    )


# Mirrors the original project's FEEDBACK_MODES/build_refinement_prompt
# (handoff Section 1.3) in shape, but the metric surface is divergence, not
# acceptance rate -- see docs/dart-oracle-design.md Section 10.
SCHEMA_DESCRIPTION = """Record schema (all six fields always present in a well-formed document):
{
  "id": <integer>,
  "amount": <string>,
  "name": <string or null>,
  "status": <one of "active", "inactive", "unknown">,
  "tags": <array of strings>,
  "child": <Record or null, one level of recursion normally>
}

Four independent Dart JSON deserializers are run against every document you
produce: hand-written manual parsing, and three codegen frameworks
(json_serializable, freezed, built_value). Your goal is to produce documents
that are syntactically valid JSON objects but make these four
implementations disagree with each other -- one accepting where another
rejects, or two accepting but decoding to different values -- or that make
any of them fail with an undocumented (private, unnameable) exception type
rather than a clear, catchable one."""


_IMPORT_INSTRUCTION_DEFAULT = (
    "The only import allowed is `from hypothesis import strategies as st` -- "
    "do not import `json` or anything else; build the JSON text yourself "
    "with string concatenation and Hypothesis `.map()`/`.flatmap()` transforms."
)
_IMPORT_INSTRUCTION_JSON_ALLOWED = (
    "The only imports allowed are `from hypothesis import strategies as st` "
    "and `import json` -- you may build a Python dict/list structure and "
    "serialize it with `json.dumps(...)` instead of hand-building JSON text."
)


# `knowledge_parity` arm (docs/dart-oracle-design.md Section 17): exactly what
# the static generator's designer knew before writing `dart_record_strategy.py`
# -- the three findings of the 13-case characterization
# (`harness/bin/characterize_exceptions.dart`, design doc Section 8) plus the
# `id` decoding difference read directly from the generated code -- stated as
# observations, with no generator code. Everything below predates the static
# generator; nothing learned from any campaign since is included.
_KNOWLEDGE_PARITY_SECTION = """What is already known about these four implementations, from a
hand-run characterization of them before any fuzzing (use it however you
see fit):
1. All four receive the output of one shared `jsonDecode` call. Invalid
   JSON syntax, or a top-level value that is not an object, is rejected
   identically before any of them runs, so it can never cause disagreement.
2. When the `tags` field is missing entirely, built_value accepts the
   document and silently uses an empty list, while manual, json_serializable
   and freezed reject it. Missing `id`, `amount` or `status` is rejected by
   all four.
3. A wrong JSON type for a field, or null for a non-nullable field, was
   rejected by all four in every case tried (manual, json_serializable and
   freezed throw a private `_TypeError`; built_value throws its own public
   `DeserializationError`). An unrecognized `status` string is rejected by
   all four. An extra unknown top-level key, or a missing nullable `name`
   or `child`, is accepted by all four.
4. `id` decoding differs in the generated code: manual (`json['id'] as int`)
   and built_value require a true Dart int, while json_serializable and
   freezed decode it as `(json['id'] as num).toInt()`, which also accepts a
   Dart double. `jsonDecode` turns an integer literal outside the 64-bit
   range into a double, and `toInt()` on an out-of-range double saturates to
   the int64 minimum/maximum instead of throwing."""


def build_refinement_prompt(
    summary: DivergenceCampaignSummary,
    previous_error: str | None = None,
    allow_json: bool = False,
    category_feedback: bool = False,
    previous_source: str | None = None,
    regression_note: str | None = None,
    knowledge_parity: bool = False,
) -> str:
    """**Revised 2026-09-06** after a confirmed, 3-seed finding
    (docs/dart-oracle-design.md Section 10, RQ2 status notes) that the prior
    version of this prompt -- which showed `tier_c_divergence` inside the
    same undifferentiated metrics blob as `tier_b_counts` -- reliably drove
    up per-path rejection counts but found *zero* cross-path divergence
    across 15 iteration-campaigns, while the static generator finds it in
    19.8% of a single batch. This version isolates `tier_c_divergence` as an
    explicit headline score, separate from the rest of the metrics, and adds
    a short methodological hint about *categories* of perturbation likely to
    matter -- not the specific fields/outcomes already found by hand, since
    naming those would make any resulting "finding" a foregone conclusion
    rather than genuine LLM-driven discovery.

    **Extended (structural follow-up, paper Future Work item 1)**: neither
    the score-only prompt nor `category_feedback` closed the RQ2 gap, and
    the latter did measurably worse (docs/dart-oracle-design.md Section 14)
    -- evidence the limiting factor is not that the proposer lacks
    information about what tends to work, but the harder difficulty of
    actually implementing an effective divergence-hunting generator in
    code. `previous_source`/`mutate_source` addresses that directly: instead
    of discarding the prior iteration's generator every round (as this loop
    has always done, unmodified from the original project), it is shown to
    the proposer with an instruction to revise it incrementally rather than
    write a new one from scratch.
    """
    score = summary.tier_c_accept_reject + summary.tier_c_value
    other_metrics = {
        key: value
        for key, value in summary.as_dict().items()
        if key not in ("tier_c_accept_reject", "tier_c_value", "divergence_perturbation_categories")
    }
    error_section = (
        f"\nThe previous iteration's proposal failed before producing usable data:\n{previous_error}\n"
        if previous_error
        else ""
    )
    source_section = (
        f"""
Your previous iteration's generator source, for you to revise:
```python
{previous_source}
```
"""
        if previous_source
        else ""
    )
    regression_section = f"\n{regression_note}\n" if regression_note else ""
    knowledge_section = f"\n{_KNOWLEDGE_PARITY_SECTION}\n" if knowledge_parity else ""
    if category_feedback and summary.divergence_perturbation_categories:
        counts = ", ".join(
            f"{name}: {count}"
            for name, count in summary.divergence_perturbation_categories.most_common()
        )
        strategy_hint = f"""Strategy hint: of the documents that scored last iteration, here is what
kind of thing was unusual about them, by category (a document can count in
more than one category): {counts}. Categories, in case any need
explanation: `missing_field` (a schema field absent entirely),
`null_override` (a normally-required field set to null), `wrong_type` (a
field present with the wrong JSON type), `bad_enum` (an unrecognized
`status` string), `boundary_id` (an `id` near or past a 53- or 64-bit
integer boundary), `extra_key` (an unexpected top-level key), `deep_nesting`
(more than 3 levels of `child` nesting). Weight your next batch of
documents toward whichever categories scored highest above, and still vary
one or two things about an otherwise valid document at a time rather than
maximizing how unusual any single document looks overall."""
    else:
        strategy_hint = """Strategy hint: implementations are more likely to disagree on documents that
are *almost* well-formed with one specific thing off (a field of the wrong
type, a field missing rather than present-but-wrong, a value at a type
boundary) than on documents that are broadly malformed in many ways at once
-- broad malformation tends to make every implementation reject identically,
which scores zero. Vary one or two things about an otherwise valid document
at a time, across many documents, rather than maximizing how unusual any
single document looks."""
    if previous_source:
        return_instruction = """Return the full, revised Python source defining
`@st.composite def generated_json(draw) -> bytes`. Start from your previous
iteration's source above and change only what the score and feedback above
suggest needs to change -- keep whatever part of it is already working
rather than rewriting the whole generator from scratch."""
    else:
        return_instruction = (
            "Return only Python source defining `@st.composite def generated_json(draw) -> bytes`."
        )
    return f"""You are refining a Hypothesis strategy to find behavioral divergence between four Dart JSON deserializers.

{SCHEMA_DESCRIPTION}
{knowledge_section}
YOUR SCORE (from the last iteration that produced usable data): {score} documents
out of {summary.total} where the four implementations disagreed with each other
({summary.tier_c_accept_reject} where one accepted and another rejected,
{summary.tier_c_value} where two accepted but decoded to different values).
Maximizing this score is the objective. A high rejection count on its own
(see tier_b_counts below) is not the goal by itself -- a document every
implementation rejects the same way scores zero, no matter how "malformed"
it looks.

Other metrics from that iteration, for context only:
{json.dumps(other_metrics, sort_keys=True)}
{error_section}
{regression_section}
{strategy_hint}
{source_section}
{return_instruction}
Emit syntactically valid JSON objects only (invalid JSON syntax is rejected
identically by all four paths before any of them run, so it cannot score).
Use bounded recursion and output sizes. The campaign runs at most 500
examples per iteration. {_IMPORT_INSTRUCTION_JSON_ALLOWED if allow_json else _IMPORT_INSTRUCTION_DEFAULT}
Do not use subprocesses, filesystem, network access, eval, exec, or
coverage instrumentation.
"""


def run_refinement_loop(
    executable: str,
    proposer: Callable[[str], str],
    artifact_dir: Path,
    iterations: int = 5,
    examples_per_iteration: int = 500,
    timeout_seconds: float = 5.0,
    allow_json: bool = False,
    category_feedback: bool = False,
    mutate_source: bool = False,
    knowledge_parity: bool = False,
) -> list[DivergenceCampaignSummary]:
    """Same bounded-iteration, persist-everything, fall-back-on-failure
    structure as the original project's `refinement.run_refinement_loop`
    (handoff Section 1.7), adapted to this module's summary type.

    ``allow_json=True`` selects the Section V-E ablation (paper Future Work
    item 1): the sandbox additionally permits `import json`, and the prompt
    says so, isolating whether refinement's RQ2 shortfall is generation
    overhead from hand-rolling JSON (Section IV-B) or a targeting gap that
    persists regardless. ``category_feedback=True`` selects the follow-up
    the ablation itself motivated (paper Future Work, revised after Section
    IV-C established the gap is a targeting problem): feed back which
    *categories* of perturbation (missing field, wrong type, boundary
    value, ...) were present in last iteration's divergence-causing
    documents, without naming the specific fields already known by hand.
    ``mutate_source=True`` selects the structural follow-up the
    category-feedback negative result motivated (docs/dart-oracle-design.md
    Section 14): show the proposer its own previous iteration's generator
    source and ask it to revise that incrementally, rather than -- as every
    prior arm including this one otherwise does -- discarding it and
    starting from a blank prompt each iteration. It also carries a
    revert-on-regression guard (`_MUTATE_SOURCE_REGRESSION_THRESHOLD`): if a
    revision's schema-evaluated fraction drops sharply from the best fraction
    seen so far this run, the *next* iteration mutates from that best-known
    source instead of the regressed one, with a note telling the proposer
    what regressed and that it is working from an earlier version again --
    otherwise a single buggy revision compounds for the rest of the run
    (observed directly in the held-out seed that motivated this guard). All
    three modes default to False, the main RQ2 comparison, unchanged.
    """
    summaries: list[DivergenceCampaignSummary] = []
    last_good = DivergenceCampaignSummary(0, Counter(), Counter(), 0, 0, 0, Counter())
    last_error: str | None = None
    last_source: str | None = None
    best_source: str | None = None
    best_schema_fraction: float = 0.0
    regression_note: str | None = None
    draw_inputs = proposal_relaxed.proposal_inputs if allow_json else proposal_inputs
    for iteration in range(min(iterations, 5)):
        prompt = build_refinement_prompt(
            last_good,
            last_error,
            allow_json=allow_json,
            category_feedback=category_feedback,
            previous_source=last_source if mutate_source else None,
            regression_note=regression_note if mutate_source else None,
            knowledge_parity=knowledge_parity,
        )
        proposal = proposer(prompt)
        regression_note = None
        iteration_dir = artifact_dir / f"iteration-{iteration + 1}"
        iteration_dir.mkdir(parents=True, exist_ok=True)
        (iteration_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
        (iteration_dir / "proposal.py").write_text(proposal, encoding="utf-8")
        result_path = iteration_dir / "results.jsonl"
        try:
            inputs = draw_inputs(proposal, min(examples_per_iteration, 500))
            run_campaign(
                executable,
                inputs,
                result_path,
                max_examples=min(examples_per_iteration, 500),
                timeout_seconds=timeout_seconds,
            )
        except Exception as error:
            error_text = f"{type(error).__name__}: {error}"
            (iteration_dir / "proposal_error.txt").write_text(error_text, encoding="utf-8")
            last_error = error_text
            if mutate_source and best_source is not None:
                regression_note = (
                    "Your previous revision crashed before producing usable data (see the "
                    "error above). Reverting to your last working version instead of "
                    "mutating the broken one further -- fix the underlying bug this time "
                    "rather than repeating the same change."
                )
                last_source = best_source
            if result_path.exists() and result_path.stat().st_size > 0:
                with result_path.open(encoding="utf-8") as result_file:
                    partial = summarize_records(json.loads(line) for line in result_file)
                last_good = partial
                summaries.append(partial)
            else:
                summaries.append(
                    DivergenceCampaignSummary(1, Counter({"proposal_rejected": 1}), Counter(), 0, 0, 0, Counter())
                )
            continue
        with result_path.open(encoding="utf-8") as result_file:
            summary = summarize_records(json.loads(line) for line in result_file)
        last_good = summary
        last_error = None
        summaries.append(summary)
        if mutate_source:
            schema_fraction = (
                summary.top_level_counts.get("schema_evaluated", 0) / summary.total if summary.total else 0.0
            )
            if best_source is None or schema_fraction >= best_schema_fraction - _MUTATE_SOURCE_REGRESSION_THRESHOLD:
                last_source = proposal
                if best_source is None or schema_fraction > best_schema_fraction:
                    best_source = proposal
                    best_schema_fraction = schema_fraction
            else:
                regression_note = (
                    f"Your previous revision dropped the fraction of syntactically valid "
                    f"documents from {best_schema_fraction:.1%} to {schema_fraction:.1%}. "
                    f"Reverting to the version before that change -- fix the underlying bug "
                    f"this time instead of repeating the same change."
                )
                last_source = best_source
    return summaries
