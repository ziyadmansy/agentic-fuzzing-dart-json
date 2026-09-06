# Technical Handoff: Agentic Grammar Fuzzing Methodology (for reuse on a new target)

This document is a self-contained technical handoff from the `agentic-grammar-fuzzing`
project (a black-box, LLM-guided grammar fuzzer originally targeting the cJSON C
parser, plus a second-target generalization run against parson) written so a second
paper can reuse the same methodology against a *different* target. The receiving
reader has no access to the original repository or conversation — everything needed
is inlined below: real code, real file layout, real numbers, and real paper text.

---

## 1. LLM-REFINEMENT LOOP ARCHITECTURE

### 1.1 Overview of the code path

The loop lives in one file, `src/agentic_fuzzing/refinement.py`. The call chain per
experiment run is:

```
scripts/run_refinement.py (CLI entry point)
  -> agentic_fuzzing.seeding.seed_everything(seed)     # deterministic Hypothesis draws
  -> agentic_fuzzing.refinement.run_refinement_loop(...)
       for iteration in range(min(iterations, 5)):        # hard cap: 5 iterations
         prompt = build_refinement_prompt(grammar, last_good, last_error, feedback_mode)
         proposal = proposer(prompt)                       # -> OpenAIProposer.__call__
         inputs = agentic_fuzzing.proposal.proposal_inputs(proposal, N)  # validates + draws
         agentic_fuzzing.campaign.run_campaign(executable, inputs, result_path, ...)
         summary = summarize_records(jsonl_lines)           # -> CampaignSummary
         # summary becomes `last_good` fed into next iteration's prompt
```

Feedback signals are computed in two places:

1. **Per-input classification** — `src/agentic_fuzzing/runner.py::run_input()` runs the
   candidate bytes as a bounded subprocess against the sanitizer-instrumented target
   binary and classifies the outcome as one of `accepted`, `rejected`, `crash`,
   `timeout`, or `signal:<name>`.
2. **Per-input structural fingerprint** — `src/agentic_fuzzing/campaign.py::_structure()`
   computes a coverage-free shape proxy (see 1.2) for every input, valid or not.
3. **Per-campaign aggregation** — `src/agentic_fuzzing/refinement.py::summarize_records()`
   folds every JSONL record of one campaign (up to 500 inputs) into a single
   `CampaignSummary`: outcome counts, count of distinct input lengths, count of distinct
   structural fingerprints, count of distinct rejection signatures, and total inputs run.

### 1.2 The coverage-free proxy signal (exact definitions)

No coverage instrumentation is used anywhere in the pipeline. Three signals, computed
purely from classified process outcomes, are the entire feedback surface:

- **Acceptance rate** — fraction of inputs classified `accepted` by the harness (its
  stdout begins with a fixed sentinel line, see 1.5). A generator accepting near 0% of
  its own output is testing only the rejection path, not the parser's structural
  handling of valid input.
- **Structural diversity** — count of distinct *structural fingerprints*. A fingerprint
  maps each byte of an input to one of six symbols and truncates at 256 characters:

  ```python
  def _structure(data: bytes) -> str:
      """Return a stable, parser-independent shape fingerprint for diversity metrics."""
      categories = []
      for byte in data:
          if byte in b"{}[]:,":
              categories.append(chr(byte))
          elif byte in b" \t\r\n":
              categories.append("_")
          elif 48 <= byte <= 57:
              categories.append("#")
          elif byte == 34:
              categories.append('"')
          else:
              categories.append("x")
      return "".join(categories[:256])
  ```
  Two inputs with the same first-256-byte shape collapse to one fingerprint. **This is
  format-specific** — the six literal symbols (`{}[]:,`) and the digit/quote/whitespace
  buckets are JSON's structural tokens. For a new target format you must redesign this
  function around that format's actual delimiter/token alphabet (see Section 6).
- **Rejection signatures** — the harness's stdout line for a rejected input (e.g.
  `status=rejected offset=<n>`) is used directly as the dedup key (see 1.6); the count
  of distinct such strings across a campaign tells the proposer which malformed shapes
  are already well covered vs. unexplored.

These three counts, plus outcome counts and unique input lengths, are packaged into a
`CampaignSummary` dataclass:

```python
@dataclass(frozen=True)
class CampaignSummary:
    counts: Counter[str]
    unique_lengths: int
    unique_structures: int
    unique_rejections: int
    total: int
```

### 1.3 Prompt construction (exact function, exact template)

```python
FEEDBACK_MODES = {
    "counts": ("counts", "total"),
    "counts+rejections": ("counts", "total", "unique_rejections"),
    "full": ("counts", "total", "unique_lengths", "unique_structures", "unique_rejections"),
}
DEFAULT_FEEDBACK_MODE = "full"


def build_refinement_prompt(
    grammar: str,
    summary: CampaignSummary,
    previous_error: str | None = None,
    feedback_mode: str = DEFAULT_FEEDBACK_MODE,
) -> str:
    fields = FEEDBACK_MODES[feedback_mode]
    metrics = {key: value for key, value in summary.as_dict().items() if key in fields}
    error_section = (
        f"\nThe previous iteration's proposal failed before producing usable data:\n{previous_error}\n"
        if previous_error
        else ""
    )
    return f"""You are refining a Hypothesis strategy for black-box JSON parser fuzzing.

Grammar:
{grammar}

Observed campaign metrics (from the last iteration that produced usable data):
{json.dumps(metrics, sort_keys=True)}
{error_section}
Return only Python source defining `@st.composite def generated_json(draw) -> bytes`.
Use bounded `st.recursive` or `@st.composite`, preserve valid and near-valid cases,
and keep recursion and output sizes bounded. The campaign runs at most 500 examples
per iteration. Do not use subprocesses, filesystem,
network access, eval, exec, or coverage instrumentation.
"""
```

A real captured first-iteration prompt (metrics all zero because there is no prior
campaign yet):

```
You are refining a Hypothesis strategy for black-box JSON parser fuzzing.

Grammar:
grammar JSON;

json : value EOF ;
...
WS : [ \t\n\r]+ -> skip ;

Observed campaign metrics (from the last iteration that produced usable data):
{"counts": {}, "total": 0, "unique_lengths": 0, "unique_rejections": 0, "unique_structures": 0}

Return only Python source defining `@st.composite def generated_json(draw) -> bytes`.
Use bounded `st.recursive` or `@st.composite`, preserve valid and near-valid cases,
and keep recursion and output sizes bounded. The campaign runs at most 500 examples
per iteration. Do not use subprocesses, filesystem,
network access, eval, exec, or coverage instrumentation.
```

Note the prompt is entirely static text plus one inlined JSON metrics blob — no
few-shot examples, no chain-of-thought scaffolding, no prior proposal source is
re-shown to the model (only the numeric summary and, on failure, the exception text).

**Ablation implementation**: `feedback_mode` is a single string flag threaded through
CLI (`--feedback {counts,counts+rejections,full}`) → `run_refinement_loop` →
`build_refinement_prompt`. It is **not** separate code paths or branches — the loop,
campaign runner, and proposer are byte-identical across modes; only the `fields`
tuple used to filter `summary.as_dict()` differs. This was a deliberate design choice
so the ablation could not accidentally introduce a confound.

### 1.4 What the LLM must produce, and how it's applied

The LLM is asked to produce **one full, self-contained Python function** each round —
not a diff/patch and not a set of individual helper functions. Contract:

- Must define `generated_json`, a callable decorated with (or acting as)
  `@st.composite`, taking a Hypothesis `draw` function and returning `bytes`.
- Must use only `hypothesis.strategies` combinators (`st.*`) plus ordinary Python.
- No prior code is carried forward — each iteration's proposal replaces the previous
  one wholesale; there is no accumulation of a diff chain. (This means the model is
  effectively asked to rewrite the whole generator from scratch each time, informed
  only by the numeric summary of what the last generator produced.)

The proposer implementation (`src/agentic_fuzzing/llm.py`) is a thin, swappable
OpenAI wrapper — the loop itself only depends on `Callable[[str], str]`:

```python
class OpenAIProposer:
    def __init__(self, client: Any, model: str = "gpt-4.1-mini") -> None:
        self.client = client
        self.model = model

    def __call__(self, prompt: str) -> str:
        response = self.client.responses.create(
            model=self.model,
            input=prompt,
            temperature=0.2,
            max_output_tokens=2500,
        )
        text = getattr(response, "output_text", None)
        if not text:
            raise RuntimeError("LLM response did not contain output_text")
        return _strip_code_fence(text)


def _strip_code_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        lines = cleaned.splitlines()
        return "\n".join(lines[1:-1]).strip()
    return cleaned
```

Model used for all official numbers: `gpt-4.1-mini`, `temperature=0.2`,
`max_output_tokens=2500`. The second-target generalization run (parson) substituted a
human reasoning over the identical prompt/summary in the proposer's role — same
validation, same execution path — to test pipeline portability without an API key.

### 1.5 Validation and sandboxing of LLM output

Every proposal passes through `src/agentic_fuzzing/proposal.py::load_strategy()`
before it ever touches the target binary:

```python
def load_strategy(source: str):
    """Load a generated ``generated_json`` strategy after lightweight validation."""
    try:
        tree = ast.parse(source, mode="exec")
    except SyntaxError as error:
        raise ProposalError(f"proposal has invalid Python: {error}") from error

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = {alias.name for alias in node.names}
            if isinstance(node, ast.ImportFrom) and node.module == "hypothesis":
                names.discard("strategies")
            if names or (isinstance(node, ast.ImportFrom) and node.module != "hypothesis"):
                raise ProposalError("proposal imports are restricted to hypothesis.strategies")
        if isinstance(node, (ast.Call,)) and isinstance(node.func, ast.Name):
            if node.func.id in {"eval", "exec", "open", "compile", "__import__"}:
                raise ProposalError(f"proposal uses forbidden call: {node.func.id}")

    def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "hypothesis" and fromlist == ("strategies",):
            return builtins.__import__(name, globals, locals, fromlist, level)
        raise ProposalError("proposal imports are restricted to hypothesis.strategies")

    _BLOCKED_BUILTINS = frozenset({
        "eval", "exec", "compile", "__import__", "open", "input",
        "breakpoint", "exit", "quit", "help",
        "globals", "locals", "vars", "getattr", "setattr", "delattr",
    })
    safe_builtins = {n: v for n, v in vars(builtins).items() if n not in _BLOCKED_BUILTINS}
    safe_builtins["__import__"] = safe_import
    namespace = {"st": st, "__builtins__": safe_builtins}
    exec(compile(tree, "<generated-strategy>", "exec"), namespace, namespace)
    strategy = namespace.get("generated_json")
    if strategy is None or not callable(strategy):
        raise ProposalError("proposal must define callable generated_json")
    try:
        example = strategy().example()
    except Exception as error:
        raise ProposalError(f"generated_json is not a Hypothesis strategy: {error}") from error
    if not isinstance(example, bytes):
        raise ProposalError("generated_json must emit bytes")
    return strategy
```

Design note baked into the code as a comment (worth carrying forward verbatim): this
is a **blocklist, not a whitelist** — an earlier whitelist-of-safe-names version
turned into unbounded whack-a-mole against ordinary Python. The blocklist denies named
entry points that grant code execution, I/O, or process control, and allows everything
else. It is explicitly documented as a filter against *accidental* misuse of
non-adversarial LLM output, **not a real security sandbox** — Python's object model
(e.g. `().__class__.__base__.__subclasses__()`) can reach dangerous functionality
without naming a blocked builtin; a real boundary needs process/container isolation.

Once validated, `proposal_inputs(source, n)` draws up to `n` example byte-strings from
the strategy, tolerating individual draw failures (`GenerationError`) without aborting
the whole batch — a stray unpaired UTF-16 surrogate in one draw must not kill the
other 499.

### 1.6 Harness contract that outcome classification depends on

```c
// harness/cjson_harness.c (abridged)
document = cJSON_ParseWithLengthOpts((const char *)input, length + 1, &parse_end, 1);
if (document == NULL) {
    size_t offset = parse_end == NULL ? 0 : (size_t)(parse_end - (const char *)input);
    printf("status=rejected offset=%zu\n", offset);
    free(input);
    return 0;
}
puts("status=accepted");
```

Classification (`src/agentic_fuzzing/runner.py::run_input`), in priority order:
`timeout` (process exceeds the bound) → `signal:<name>` (killed by fatal signal) →
`crash` (non-zero exit code OR stderr contains `AddressSanitizer`/
`UndefinedBehaviorSanitizer`) → `accepted` (stdout starts with `status=accepted`) →
else `rejected`. **For a new target, the harness's stdout sentinel convention
(`status=accepted` / `status=rejected offset=N`) is the only contract the rest of the
pipeline depends on** — everything downstream (runner, campaign, refinement) is
otherwise target-agnostic.

### 1.7 Stopping criteria / iteration budget / convergence checks

There is **no adaptive convergence check** — the loop is a fixed, hard-capped budget:

- `min(iterations, 5)` iterations per run (5 is a hard ceiling baked into the loop,
  not just a CLI default — `run_refinement_loop` clamps even if the caller passes
  more).
- Up to 500 examples executed per iteration (`min(examples_per_iteration, 500)`,
  also hard-capped in code, not just default).
- No early-stop on "good enough" acceptance rate, diversity plateau, or any other
  metric — every run always executes exactly `min(iterations, 5)` prompt/proposal/
  campaign cycles (a proposal that fails validation still consumes an iteration slot;
  it just produces `proposal_rejected` in the counts and zero campaign data for that
  slot).
- Failure handling: if a proposal raises anything (bad code from the LLM, encoding
  errors mid-batch, etc.), the exception text is captured into `proposal_error.txt`
  and fed back into the *next* prompt's `previous_error` slot so the model sees what
  broke; `last_good` (what's actually shown as metrics) only advances on an iteration
  that produced real data — a total-rejection iteration falls back to whatever the
  last real campaign was, possibly several iterations back, rather than resetting the
  chain to zero.

Relevant excerpt (the "why" comments are load-bearing — keep them if you port this):

```python
# `last_good` is what actually gets shown in the next prompt: it only moves
# forward on an iteration that produced real campaign data (full or partial),
# so a total rejection (no data at all) falls back to whatever the last real
# campaign was -- possibly several iterations back -- instead of resetting
# the refinement chain. `last_error` carries the previous failure's exact
# exception text into the next prompt so the proposer knows what broke.
last_good = CampaignSummary(Counter(), 0, 0, 0, 0)
last_error: str | None = None
for iteration in range(min(iterations, 5)):
    ...
```

Every iteration's `prompt.txt`, `proposal.py`, `results.jsonl`, `summary.json`, and
(on failure) `proposal_error.txt` are persisted to disk under
`artifact_dir/iteration-N/` — nothing is thrown away, which is what makes the whole
pipeline auditable after the fact.

---

## 2. GRAMMAR AUTHORING PATTERN

### 2.1 Grammar source and directory layout

```
grammar/JSON.g4      # single file: vendored, unmodified ANTLR grammars-v4 JSON.g4
```

That's the entire "grammar definitions" directory — one grammar, one file, vendored
verbatim from the upstream `antlr/grammars-v4` project (not regenerated, not
hand-edited). Full content:

```antlr
grammar JSON;

json : value EOF ;

obj : '{' pair (',' pair)* '}' | '{' '}' ;

pair : STRING ':' value ;

arr : '[' value (',' value)* ']' | '[' ']' ;

value
    : STRING
    | NUMBER
    | obj
    | arr
    | 'true'
    | 'false'
    | 'null'
    ;

STRING : '"' (ESC | SAFECODEPOINT)* '"' ;

fragment ESC : '\\' (["\\/bfnrt] | UNICODE) ;
fragment UNICODE : 'u' HEX HEX HEX HEX ;
fragment HEX : [0-9a-fA-F] ;
fragment SAFECODEPOINT : ~["\\ -] ;

NUMBER : '-'? INT ('.' [0-9]+)? EXP? ;
fragment INT : '0' | [1-9] [0-9]* ;
fragment EXP : [Ee] [+-]? [0-9]+ ;

WS : [ \t\n\r]+ -> skip ;
```

### 2.2 The mapping process (grammar → Hypothesis strategy): manual, not tooled

**There is no automated ANTLR-to-Hypothesis translator or code generator in this
repo.** The translation from the `.g4` grammar to the baseline `st.*` strategy was
done entirely by hand, by reading the grammar's productions and writing the
structurally corresponding Hypothesis combinators one production at a time:

| Grammar production | Hand-written Hypothesis equivalent |
|---|---|
| `value : STRING \| NUMBER \| obj \| arr \| 'true' \| 'false' \| 'null'` | `st.one_of(st.none(), st.booleans(), st.integers(...), st.floats(...), st.text(...))` as the recursion base case |
| `obj : '{' pair (',' pair)* '}' \| '{' '}'` | `st.dictionaries(st.text(max_size=40), children, max_size=8)` |
| `arr : '[' value (',' value)* ']' \| '[' ']'` | `st.lists(children, max_size=8)` |
| recursive `value` (obj/arr containing `value`) | `st.recursive(json_scalar, lambda children: st.one_of(lists, dicts), max_leaves=32)` |
| `NUMBER` (no NaN/Infinity token) | `st.floats(allow_nan=False, allow_infinity=False, width=64)` — a grammar/implementation mismatch was checked here: cJSON's number parser cannot produce or accept NaN/Infinity either, so this exclusion is doubly justified, not just a grammar artifact |
| serialization to bytes | reuse Python's own `json.dumps(value, ensure_ascii=False, separators=(",", ":"))` rather than hand-rolling a serializer, since the grammar's terminals (STRING/NUMBER literal syntax) are exactly what `json.dumps` already emits |

Full baseline strategy (`src/agentic_fuzzing/json_strategy.py`):

```python
"""Bounded JSON strategies derived from grammar/JSON.g4."""

import json
from hypothesis import strategies as st

json_scalar = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-10**12, max_value=10**12),
    st.floats(allow_nan=False, allow_infinity=False, width=64),
    st.text(max_size=80),
)

json_value = st.recursive(
    json_scalar,
    lambda children: st.one_of(
        st.lists(children, max_size=8),
        st.dictionaries(st.text(max_size=40), children, max_size=8),
    ),
    max_leaves=32,
)

@st.composite
def baseline_json(draw: st.DrawFn) -> bytes:
    """Generate bounded, grammar-valid JSON documents as UTF-8 bytes."""
    value = draw(json_value)
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

@st.composite
def near_valid_json(draw: st.DrawFn) -> bytes:
    """Create a small malformed neighbor of a grammar-valid document."""
    document = draw(baseline_json())
    mutation = draw(st.sampled_from((b",", b"]", b"}", b" trailing", b"\x00")))
    return document + mutation
```

`near_valid_json` is a deliberate second strategy (not grammar-derived) that appends
a small malformed suffix to an otherwise valid document, specifically to probe the
accept/reject boundary — the baseline campaign alternates between `baseline_json` and
`near_valid_json` on even/odd indices (see `scripts/run_baseline.py`'s
`input_stream()`).

### 2.3 What was manual vs. automated, explicitly

- **Manual**: reading the `.g4` file and choosing the corresponding `st.*` combinator
  for each production; choosing size/recursion bounds (`max_size=8`, `max_leaves=32`)
  to keep generation bounded; identifying and encoding the three grammar/implementation
  mismatches (NaN/Infinity exclusion, duplicate-key tolerance, full-buffer-consumption
  entry point choice) as either strategy constraints or harness-level choices.
  Discovering the mismatches was itself manual: they were found empirically (by
  generating inputs in that grammar region and observing the parser's real behavior),
  not derived from reading the grammar or the parser source ahead of time, then
  confirmed by source inspection afterward.
- **Automated**: nothing. There is no script that parses `JSON.g4` and emits Python.
  The `.g4` file's only two roles in the running pipeline are (1) documentation of the
  grammar the harness is supposed to accept, and (2) raw text embedded verbatim into
  every refinement prompt (Section 1.3) so the LLM has the same formal spec a human
  author would have used.

**Implication for porting to a new target**: budget real analyst time to read the new
target's grammar (or write one, if none exists in ANTLR grammars-v4 or similar) and
hand-translate it into a `baseline_<format>` / `near_valid_<format>` pair, following
the pattern above. There is no shortcut tool in this codebase to lean on.

---

## 3. EXPERIMENT METHODOLOGY (as implemented)

### 3.1 Seed structure for the n=15-per-arm cJSON comparison

- Two arms: **baseline** (grammar-only, no LLM, exactly 1 iteration) and **refined**
  (LLM refinement loop, up to 5 iterations).
- 15 independent seeds per arm: `seed = 0, 1, ..., 14`. What varies between seeds/runs
  is **only** the Hypothesis draw stream — `seed_everything(seed)` reseeds both
  Python's `random` module and Hypothesis's private `_hypothesis_global_random`
  (see `src/agentic_fuzzing/seeding.py`) once, before any strategy is drawn, so run N
  is a fully independent, reproducible draw sequence. Everything else (target binary,
  grammar, iteration/example budgets, model, feedback mode) is held fixed across runs.
- Baseline run *N* uses `--seed 0 --runs 15`, which internally computes
  `seed = base_seed + run_index`, i.e. run 1 uses seed 0, run 2 uses seed 1, etc.
  Same convention for the refined arm.
- On-disk run naming: `run-{run_index+1:02d}-seed-{seed:04d}/`, e.g.
  `run-01-seed-0000/`, produced by `src/agentic_fuzzing/experiment.py::run_directory()`.
  A run directory that already has results refuses to be overwritten unless
  `--overwrite` is passed (which deletes and recreates it, to avoid leftover stale
  iteration directories from a previous, longer run).

Directory layout for one arm (`experiment.py` + `refinement.py::run_refinement_loop`
write these):

```
artifacts/repeated/cjson-refined-n15/
  run-01-seed-0000/
    manifest.json              # seed, hypothesis/python versions, platform, model, feedback_mode, CLI args
    iteration-1/
      prompt.txt
      proposal.py
      results.jsonl            # one JSON record per input executed
      summary.json             # CampaignSummary.as_dict()
      proposal_error.txt       # only present if the proposal failed validation/execution
    iteration-2/ ... iteration-5/
  run-02-seed-0001/
    ...
  reproducibility.json / .md   # environment provenance for the whole experiment (compiler, harness sha256, git commit, ...)
  aggregate.csv / aggregate.json   # written by scripts/aggregate_runs.py
  comparison.csv / comparison.md   # written by scripts/compare_experiments.py, into the refined arm's directory
  figures/                     # written by scripts/make_figures.py (per-iteration + across-runs PNG/PDF)
```

Exact CLI commands used for the official n=15 result:

```sh
PYTHONPATH=src .venv/bin/python scripts/run_baseline.py \
    --artifact-dir artifacts/repeated/cjson-baseline-n15 --runs 15 --examples 500 --seed 0
PYTHONPATH=src .venv/bin/python scripts/run_refinement.py \
    --artifact-dir artifacts/repeated/cjson-refined-n15 --runs 15 --iterations 5 \
    --examples 500 --seed 0 --model gpt-4.1-mini
.venv/bin/python scripts/aggregate_runs.py artifacts/repeated/cjson-baseline-n15
.venv/bin/python scripts/aggregate_runs.py artifacts/repeated/cjson-refined-n15
.venv/bin/python scripts/compare_experiments.py \
    artifacts/repeated/cjson-baseline-n15 artifacts/repeated/cjson-refined-n15
.venv/bin/python scripts/make_paper_figure.py \
    --baseline-dir artifacts/repeated/cjson-baseline-n15 \
    --refined-dir artifacts/repeated/cjson-refined-n15
```

### 3.2 Aggregation logic (exact code, `scripts/aggregate_runs.py`)

Reads **only** `manifest.json` and each `iteration-*/summary.json` — never
re-parses `results.jsonl`, since every field the aggregate needs is already in the
summary. One row per run:

```python
def collect_run(run_dir: Path) -> dict[str, Any]:
    manifest, problems = _read_manifest(run_dir)
    totals = dict.fromkeys(("accepted", "rejected", "encoding_errors", "crashes"), 0)
    totals.update(structural_fingerprints=0, rejection_signatures=0, executed=0)
    iterations = iteration_dirs(run_dir)
    with_data = 0
    rejected_iterations = 0
    for iteration_dir in iterations:
        summary = json.loads((iteration_dir / "summary.json").read_text())
        counts = dict(summary["counts"])
        total = int(summary["total"])
        if "proposal_rejected" in counts:
            rejected_iterations += 1
            continue          # contributes no campaign observations
        with_data += 1
        totals["accepted"] += int(counts.get("accepted", 0))
        totals["rejected"] += int(counts.get("rejected", 0))
        totals["encoding_errors"] += int(counts.get("encoding_error", 0))
        totals["crashes"] += sum(v for k, v in counts.items()
                                  if k not in {"accepted", "rejected", "encoding_error", "proposal_rejected"})
        totals["structural_fingerprints"] += int(summary["unique_structures"])
        totals["rejection_signatures"] += int(summary["unique_rejections"])
        totals["executed"] += total
    executed = totals["executed"]
    return {
        "run": run_dir.name, "seed": manifest.get("seed"), ...,
        "iterations": len(iterations), "iterations_with_data": with_data,
        "iterations_rejected": rejected_iterations,
        **totals,
        "acceptance_percentage": round(100.0 * totals["accepted"] / executed, 3) if executed else None,
        "problems": problems,
    }
```

**Important convention** (repeated verbatim in the paper and README so both stay
consistent): fingerprint and rejection-signature counts are **summed across a run's
iterations**, not de-duplicated across iterations — this is stated explicitly as an
*upper bound* on a run's distinct shapes, not a true de-duplicated total, because
cross-iteration de-duplication is not recoverable from `summary.json` alone (each
iteration's `unique_structures`/`unique_rejections` is only unique *within* that
iteration's 500 examples).

`summarize(rows)` then computes mean/sample-stdev/min/max per metric over "usable"
runs (`row["executed"] > 0`), using Python's `statistics` module — no `numpy`,
no `scipy`.

### 3.3 The exact statistical test (what it actually is — read carefully)

**There is no `scipy.stats` call, no library function, and no script that computes
this p-value.** The number `p ≈ 1.29×10⁻⁸` reported in the paper is a **closed-form
combinatorial calculation done by hand**, not the output of any code in this repo. A
`grep` across the codebase confirms this — no occurrence of `scipy`, `fisher`,
`binom`, or `mannwhitney` anywhere in `scripts/` or `src/`.

The reasoning: with 15 runs per arm (30 total observations), *every* refined-arm run's
acceptance rate exceeded *every* baseline-arm run's acceptance rate — complete rank
separation between the two groups. Under the null hypothesis that arm labels are
exchangeable (i.e., a permutation/exact test null: the 30 acceptance-rate values are
a fixed multiset and the 15/15 arm split is uninformative), the number of ways to
choose which 15 of the 30 observations get the "high" label is `C(30, 15)`. Exactly
2 of those partitions produce complete separation in either direction (all-refined-
above or all-refined-below), so the two-sided exact permutation p-value is:

```
p = 2 / C(30, 15) = 2 / 155,117,520 ≈ 1.29 × 10⁻⁸
```

This is mathematically equivalent to what an exact two-sided Wilcoxon–Mann–Whitney
(rank-sum) test, or `scipy.stats.mannwhitneyu(..., method="exact")`, would report for
a dataset with complete separation and no ties at n=15/15 — but it was derived
directly from the combinatorial definition rather than invoked through a library. If
you port this to a new target and want library-backed numbers instead of a hand
derivation (recommended for a second paper, since it removes any doubt about the
by-hand math and generalizes automatically past the complete-separation edge case),
use `scipy.stats.mannwhitneyu(refined_rates, baseline_rates, alternative="two-sided",
method="exact")` on the per-run acceptance-rate arrays; in the complete-separation
case it will reproduce the same `2/C(n,n)` value.

Inputs to the test: the 15 per-run **acceptance rates** (a scale-free ratio,
`accepted / total` per run) for each arm — nothing else. The paper is explicit that
**only** acceptance rate is tested statistically; structural-fingerprint and
rejection-signature *counts* are reported descriptively only, because the two arms
execute different total numbers of inputs (baseline: fixed 500 per run; refined:
~1,533 on average, since it runs up to 5 iterations of up to 500 each and some
iterations end early on a rejected LLM proposal) — count-based metrics are not
comparable across unequal budgets, only rate-based ones are. `compare_experiments.py`
enforces this by design: it reports means and absolute/relative differences with an
explicit docstring/footer stating "no hypothesis test is performed and no
significance is claimed" — the actual significance claim lives only in the paper
text, computed by hand, not in any script output.

### 3.4 Unique-crash / rejection-signature deduplication

**Crash deduplication** (`src/agentic_fuzzing/triage.py`):

```python
_ADDRESS = re.compile(r"0x[0-9a-fA-F]+")
_SOURCE_LINE = re.compile(r"(\S+):(\d+)")

def sanitizer_signature(stderr: bytes) -> str:
    """Normalize volatile addresses and retain the first useful report frames."""
    text = stderr.decode("utf-8", errors="replace")
    lines = []
    for line in text.splitlines():
        if "SUMMARY:" in line or line.lstrip().startswith("#"):
            normalized = _ADDRESS.sub("0xADDR", line.strip())
            normalized = _SOURCE_LINE.sub(r"\1:LINE", normalized)
            lines.append(normalized)
    if not lines:
        lines = [line.strip() for line in text.splitlines() if line.strip()][:3]
    return "\n".join(lines) or "unknown"

def signature_id(stderr: bytes) -> str:
    return hashlib.sha256(sanitizer_signature(stderr).encode("utf-8")).hexdigest()[:16]
```

Method: keep only the sanitizer's `SUMMARY:` line and numbered stack frames
(`#0`, `#1`, ...), normalize out volatile addresses (`0x...` → `0xADDR`) and
source line numbers (`file.c:123` → `file.c:LINE`), join, then SHA-256 and truncate
to 16 hex chars. Records sharing this 16-char `crash_id` are treated as one root
cause. If stderr has no recognizable sanitizer frames, fall back to the first 3
non-blank lines.

**Rejection-signature deduplication** is much simpler and target-specific: the
harness's own stdout line for a rejection is used directly as the signature string
(for cJSON, `status=rejected offset=<n>`, so signatures differ by rejection *offset*,
which in practice buckets rejections by roughly where in the input the parser gave
up). Uniqueness is just `set()` membership on that string per campaign —
`refinement.py::summarize_records()`:

```python
if record["status"] == "rejected":
    rejections.add(str(record.get("rejection_signature", "")))
```

There is no normalization step for rejection signatures analogous to
`sanitizer_signature` — this is worth reconsidering for a new target if its rejection
messages embed something noisier than a simple integer offset (e.g. a full error
string with a byte range that varies wildly run to run for semantically identical
failures), since without normalization that would inflate the "unique rejections"
count in a misleading way.

### 3.5 Feedback-signal ablation: config flag, not separate code paths

Already shown in Section 1.3 — reiterated here because the user's methodology
question specifically asked how this is implemented: it's one dict
(`FEEDBACK_MODES: dict[str, tuple[str, ...]]`) and one string parameter
(`feedback_mode`) threaded through `run_refinement_loop` → `build_refinement_prompt`.
The loop, campaign runner, sandboxing, and proposer call are **identical** across
modes — only the set of `CampaignSummary` fields serialized into the prompt's JSON
metrics blob differs. This was a deliberate choice to make the three ablation arms
differ in exactly one controlled variable.

Ablation experimental design: 5 seeded trials per mode (seeds 0–4), same cJSON
build, same `gpt-4.1-mini` proposer, same 5-iteration/500-example budget as the main
refined arm. Results (n=4 usable trials per mode after excluding 1 trial per mode
where every iteration's proposal failed sandbox validation):

| Feedback mode | Acceptance rate | Fingerprints (sum/run) | Rejection sigs (sum/run) |
|---|---:|---:|---:|
| `counts` | 92.58% | 505.5 | 6.5 |
| `counts+rejections` | 96.42% | 457.3 | 26.8 |
| `full` | 95.53% | 503.5 | 34.8 |

Reported descriptively only — n=4 per condition, no separation between conditions, no
significance test performed or implied (unlike the n=15 acceptance-rate comparison in
3.3, which does have complete separation).

---

## 4. REPO STRUCTURE

### 4.1 Full directory tree with purpose

```
agentic-fuzzing/
├── grammar/
│   └── JSON.g4                    # single vendored ANTLR grammar (see Section 2)
├── harness/
│   ├── cjson_harness.c            # stdin -> cJSON_ParseWithLengthOpts -> status=accepted/rejected
│   └── parson_harness.c           # same contract, second target
├── src/agentic_fuzzing/           # the actual pipeline package (PYTHONPATH=src)
│   ├── __init__.py
│   ├── runner.py                  # subprocess execution + outcome classification
│   ├── campaign.py                # drives N inputs through runner, writes JSONL, computes structural fingerprint
│   ├── json_strategy.py           # baseline_json / near_valid_json hand-derived from grammar/JSON.g4
│   ├── proposal.py                # load_strategy() sandbox/validator + proposal_inputs()
│   ├── llm.py                     # OpenAIProposer (thin, swappable)
│   ├── refinement.py               # CampaignSummary, build_refinement_prompt, run_refinement_loop, FEEDBACK_MODES
│   ├── triage.py                  # sanitizer_signature / signature_id / save_reproducer
│   ├── minimize.py                # Hypothesis `find`-based shrink + standalone re-verify
│   ├── seeding.py                 # seed_everything() shim coupled to Hypothesis internals
│   ├── experiment.py              # run_directory() / write_summary() — shared on-disk run layout
│   └── reproducibility.py         # build_report()/write_report() — environment provenance
├── scripts/
│   ├── run_baseline.py            # CLI: grammar-only campaign (no LLM), 1 iteration
│   ├── run_refinement.py          # CLI: real LLM refinement loop, --runs/--seed/--feedback
│   ├── aggregate_runs.py          # run-*/iteration-*/summary.json -> aggregate.csv/json
│   ├── compare_experiments.py     # two aggregate.json's -> comparison.csv/md (descriptive only)
│   ├── make_figures.py            # matplotlib per-iteration + across-runs figures
│   ├── make_paper_figure.py       # the specific acceptance_comparison figure used in the paper
│   ├── make_report.py             # single-run JSONL -> artifacts/report.md
│   ├── make_loop_report.py        # per-iteration table for one refinement run (used for parson too)
│   ├── build_target.sh            # compiles vendor/cjson + harness with -fsanitize=address,undefined
│   └── build_parson.sh            # same, for the parson target
├── tests/                         # pytest, one file per pipeline stage (no network/LLM calls; stub proposer)
├── vendor/
│   ├── cjson/                     # pinned v1.7.19, commit c859b25..., unmodified, own .git
│   └── parson/                    # pinned v1.5.3, commit ba29f4e..., unmodified
├── artifacts/                     # ALL experiment output; see layout in Section 3.1
│   ├── cjson-loop/                # the single "official" narrative run cited in early README sections — never overwritten
│   ├── parson-loop/               # the single official parson run (5 real iterations)
│   ├── final/, final-baseline.jsonl, final-report.md   # superseded n=5 pilot, kept for provenance (this is the version archived at the Zenodo DOI)
│   └── repeated/                  # all seeded, repeatable, --runs>1 experiments
│       ├── cjson-baseline-n15/, cjson-refined-n15/      # the n=15 result reported in the paper
│       └── ablation-counts/, ablation-counts-rejections/, ablation-full/   # RQ3
├── paper/
│   ├── main.tex                   # IEEEtran conference class, real author block
│   ├── main-icst-submission.tex   # identical content, anonymized author block for double-blind review
│   ├── abstract.tex, introduction.tex, related_work.tex, methodology.tex,
│   │   evaluation.tex, discussion.tex, conclusion.tex   # \input-ed section files, shared by both .tex entry points
│   ├── references.bib
│   ├── figures/                   # acceptance_comparison.{pdf,png} etc.
│   └── main.pdf                   # compiled output (9 pages, IEEEtran conference two-column)
├── requirements.txt                # pinned: hypothesis==6.165.5, pytest==9.1.1, openai==3.0.0, matplotlib==3.11.1
├── CITATION.cff
└── README.md                       # extremely thorough — treat as a second source of truth alongside this doc
```

### 4.2 Build/run instructions to reproduce an experiment end to end

```sh
# 1. environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# macOS only: brew install llvm   (Apple's ASan deadlocks on Apple Silicon, see Section 6)

# 2. build the sanitizer-instrumented target
./scripts/build_target.sh
printf '{}' | ./build/cjson_harness      # sanity check: status=accepted
printf '{]' | ./build/cjson_harness      # sanity check: status=rejected offset=<n>

# 3. run the tests (no LLM key needed — stub proposer)
PYTHONPATH=src .venv/bin/pytest -q

# 4. baseline campaign (no LLM key needed)
PYTHONPATH=src .venv/bin/python scripts/run_baseline.py --examples 500

# 5. real refinement loop (needs an OpenAI key)
export OPENAI_API_KEY=sk-...
PYTHONPATH=src .venv/bin/python scripts/run_refinement.py

# 6. repeated/seeded experiments + analysis (the paper-grade path)
PYTHONPATH=src .venv/bin/python scripts/run_baseline.py \
    --artifact-dir artifacts/repeated/cjson-baseline --runs 15 --examples 500 --seed 0
PYTHONPATH=src .venv/bin/python scripts/run_refinement.py \
    --artifact-dir artifacts/repeated/cjson-refined --runs 15 --iterations 5 \
    --examples 500 --seed 0 --model gpt-4.1-mini
.venv/bin/python scripts/aggregate_runs.py artifacts/repeated/cjson-baseline
.venv/bin/python scripts/aggregate_runs.py artifacts/repeated/cjson-refined
.venv/bin/python scripts/compare_experiments.py \
    artifacts/repeated/cjson-baseline artifacts/repeated/cjson-refined
```

Environment gotcha worth carrying forward: on macOS, Apple's clang/ASan (Xcode 17,
macOS 26) deadlocks on startup on Apple Silicon during shadow-memory setup
(`AsanInitFromRtl()` spinning on `StaticSpinMutex::LockSlow()` — a bug in Apple's
compiler-rt). `build_target.sh` works around it by preferring Homebrew's clang
(`/opt/homebrew/opt/llvm/bin/clang`) automatically when present. If your new target's
build system is not a simple `clang ... -o binary` invocation (e.g. it's CMake,
Bazel, or Dart's own AOT toolchain), you'll need to write an equivalent
`build_<target>.sh`/build script that still produces a single sanitizer-instrumented
(or equivalent-oracle) executable that reads candidate input from stdin and writes the
`status=accepted`/`status=rejected offset=N` sentinel contract to stdout — that
sentinel contract, not the build system, is what the rest of the pipeline actually
depends on.

---

## 5. PAPER WRITING CONVENTIONS

### 5.1 Format constraints

- `\documentclass[conference]{IEEEtran}` — IEEE two-column conference format.
- Compiled output is **9 pages** including references, figures, and one full-page
  table (`table*` environment, spans both columns).
- Two parallel entry points sharing every section file via `\input{}`: `main.tex`
  (real author block: name, affiliation "Independent Researcher", email, ORCID) and
  `main-icst-submission.tex` (anonymized author block: "Anonymous Author(s)",
  "Submission under double-blind review", no identifying links) — for ICST 2027's
  double-blind policy. **Only the author block differs**; content sections
  (`introduction.tex` through `conclusion.tex`) are never duplicated or edited
  separately between the two.
- Required sections, in order: Abstract, Introduction, Related Work, Methodology,
  Evaluation, Discussion, Conclusion, References (`\bibliographystyle{IEEEtran}`).
- Packages used: `graphicx`, `amsmath`, `hyperref`, `booktabs`, `tabularx`.
- Tables use `\toprule`/`\midrule`/`\bottomrule` (booktabs), and the widest table
  (RQ1 comparison) uses `table*` to span both columns since it has 4 numeric columns
  plus captions explaining statistical scope.
- Methodology is organized as one subsection per pipeline stage/RQ: Research
  questions → Target/grammar/harness → Outcome classification → Proxy signal →
  Refinement loop → Sandboxing → Crash triage → Reproducibility engineering →
  Experimental design. Evaluation is organized strictly per research question
  (RQ1/RQ2/RQ3 subsections), each ending with an explicit statement of what the
  result does *not* show.
- Recurring rhetorical convention worth imitating: every quantitative claim is
  immediately followed by an explicit statement of its scope/limits ("this is a
  ceiling on how small an exact p-value fifteen-per-arm observations can produce,
  not a measure of effect size on its own"; "we report this as a negative result...
  rather than claim a bug that was not observed"). Descriptive vs. tested numbers are
  never conflated — every table caption states explicitly which cells are
  statistically tested and which are descriptive only.

### 5.2 Abstract (full text)

```
Property-based testing tools such as Hypothesis can turn a formal grammar
into a generator of syntactically valid inputs, but the generator itself is
typically static: hand-tuned once and reused unchanged for the rest of a
fuzzing campaign. We study whether a large language model (LLM), given only
a formal grammar and parser-level feedback -- with no coverage
instrumentation -- can iteratively refine such a generator. We build a fully
black-box pipeline targeting the cJSON parser (pinned at v1.7.19): a baseline
Hypothesis strategy derived directly from an ANTLR JSON grammar generates
inputs, a sanitizer-instrumented harness classifies each as accepted,
rejected, or crashing, and a refinement loop feeds an LLM a summary of three
observable proxy signals -- acceptance rate, the structural diversity of the
shapes produced, and the distinct rejection signatures seen -- asking it to
propose a revised generator. Every proposal is statically sandboxed
(AST-checked, import-restricted) and validated before it ever touches the
target binary. Across fifteen independent, seeded runs of up to five
refinement iterations each, LLM-guided refinement raises mean acceptance
rate from 58.2% to 97.1% relative to a static baseline, using no coverage
data at all. Structural fingerprints and rejection signatures are reported as
descriptive signals; because the refined arm executes more iterations, their
aggregate counts are not treated as like-for-like effects. A follow-up
ablation over which subset of this feedback the proposer sees -- counts
alone, counts with rejection signatures, or the full signal -- finds
acceptance-rate gains are broadly similar across the three conditions, with
full feedback preserving more rejection-signature diversity than counts
alone (four usable runs per condition; reported descriptively, not tested).
We additionally run the identical, unmodified pipeline against a second
parser (parson) for five real iterations (3,000 sanitizer-instrumented
executions); no crash was found, and we report this as a negative result,
supported by manual review of the highest-risk code paths, rather than
claim a bug that was not observed. We discuss how grammar-implementation
mismatches -- for instance, duplicate JSON object keys accepted by one
parser and rejected by the other under an identical grammar -- are
themselves a source of fuzzing-relevant signal that a purely formal grammar
cannot supply, and we release the full pipeline, harnesses, and
reproducibility tooling.
```

### 5.3 Methodology section (full text)

```
Section: Methodology

Research questions
This paper asks three questions. RQ1: using only black-box, coverage-free
feedback, does LLM-guided refinement of a grammar-based generator improve
that generator's acceptance rate and structural diversity relative to a
static baseline, on a fixed target? RQ2: does the pipeline -- harness
contract, proxy signal, refinement loop, and sandbox -- generalize to a
second, independently adapted target without modification? RQ3: of the
three coverage-free proxies exposed to the proposer, does the specific
subset shown -- counts alone, counts with rejection signatures, or the full
signal -- change how effectively refinement raises acceptance rate?

Target, grammar, and harness
The primary target is cJSON, pinned at v1.7.19 (commit c859b25). The
grammar is the ANTLR grammars-v4 JSON grammar, vendored unmodified. A thin
C harness reads a candidate input from stdin and parses it with
cJSON_ParseWithLengthOpts(..., require_null_terminated=1), the library's
strictest entry point: it rejects any input with trailing bytes after a
valid value, so an "accepted" input is one where the entire buffer is a
single grammar-valid value, matching the grammar's `json : value EOF ;`
production exactly. The library's more commonly used cJSON_Parse entry
point does not enforce full-buffer consumption and was deliberately not
used, since it would silently accept inputs the grammar does not.

Reconciling the formal grammar with the target's actual behavior surfaced
three adaptations, each a genuine mismatch between what the grammar
specifies and what the implementation does: (i) the grammar has no token
for NaN/Infinity, matching cJSON's inability to produce or accept them, so
generators exclude non-finite floats; (ii) cJSON accepts duplicate object
keys, storing every entry in an internal linked list rather than rejecting
or de-duplicating, even though the grammar is silent on duplicate keys --
this is treated as valid-but-underspecified territory, not a rejection
case, and generators deliberately exercise it; (iii) the
full-buffer-consumption requirement above is enforced by the harness's
choice of entry point, not by the grammar itself. Section 5 reports the
analogous set of adaptations found for the second target, parson, where two
of the three go the opposite direction under the identical grammar.

Outcome classification
Every input is executed as a bounded subprocess (5-second default timeout)
against a sanitizer-instrumented build (-fsanitize=address,undefined). The
result is classified, in order: timeout if the process does not return
within the bound; signal:<name> if it is killed by a fatal signal; crash if
it exits with a non-zero return code or its stderr contains
AddressSanitizer or UndefinedBehaviorSanitizer text; accepted if its stdout
begins with status=accepted; otherwise rejected. Timeouts are classified
and reported alongside crashes rather than discarded, since an unbounded
hang in a parser is a denial-of-service bug in its own right.

A coverage-free proxy signal
With no coverage instrumentation, refinement is steered by three signals
computed purely from a campaign's classified outcomes:
- Acceptance rate -- the fraction of inputs classified accepted. A
  generator accepting close to 0% of its own output is testing only the
  rejection path, not the parser's structural handling of valid input, and
  is flagged for correction.
- Structural diversity -- the count of distinct structural fingerprints
  seen in a campaign. A fingerprint maps each byte of an input to one of
  six symbols (the six structural characters {}[]:, are kept literal,
  whitespace maps to _, ASCII digits map to #, the double-quote maps to ",
  and every other byte maps to x), concatenates the result, and truncates
  it to 256 characters. Two inputs share a fingerprint exactly when their
  first 256 bytes reduce to the same positional shape string; the count of
  distinct fingerprints across a campaign is used as a coverage-free proxy
  for how many different grammar shapes a generator has actually produced.
  The 256-byte truncation makes this proxy a lower bound on true shape
  diversity for inputs longer than that, since two structurally different
  inputs that agree on their first 256 bytes collapse to one fingerprint;
  this is a deliberate accuracy/cost tradeoff and is stated as a limitation
  in the Discussion.
- Rejection signatures -- the count of distinct parser rejection messages
  and offsets seen, used to tell the proposer which malformed shapes are
  already well covered versus unexplored.

These three numbers, plus outcome counts and unique input lengths, are the
entire feedback surface exposed to the LLM each iteration; no coverage
data, execution trace, or source excerpt is ever included in the prompt.

Refinement loop
Each iteration builds a prompt containing the grammar text and a summary of
the previous iteration's campaign (outcome counts, unique input lengths,
unique structural fingerprints, unique rejection signatures), and sends it
to a proposer -- an LLM in the live configuration, or, for the parson
generalization test, a human reasoning over the same summary and playing
the identical role. The proposer must return a single Python function,
generated_json, decorated with Hypothesis's @st.composite and built from
st.* combinators, so that recursive structure is expressed the same way a
human-authored Hypothesis strategy would express it. The official run uses
gpt-4.1-mini at temperature 0.2 as the proposer.

Sandboxing untrusted, LLM-authored code
Because the proposer's output is executable Python that this pipeline runs
locally, every proposal passes through a validator (load_strategy) before
it ever touches the target binary. The validator first parses the
proposal's AST and rejects it outright if it imports anything other than
hypothesis.strategies, or if it calls eval, exec, open, compile, or
__import__ by name. The proposal is then executed with an otherwise
ordinary Python builtin namespace, minus a short, explicit blocklist (eval,
exec, compile, __import__, open, input, breakpoint, exit, quit, help,
globals, locals, vars, getattr, setattr, delattr) -- ordinary helpers such
as ord, chr, str, len, and range remain available, so a proposal is free to
use normal Python rather than being restricted to Hypothesis combinators
alone. Finally, the resulting generated_json must be callable and must
produce a bytes value via .example(); a proposal that fails any of these
checks is rejected and logged, and never reaches the harness. This is
deliberately scoped as a filter against accidental misuse of untrusted,
LLM-authored code, not as a hardened security boundary: Python's object
model can reach functionality beyond any blocklisted name (for instance, by
walking ().__class__.__base__.__subclasses__()), and closing that off would
require process- or container-level isolation rather than name filtering.
We report this limitation directly rather than implying a guarantee the
design does not provide.

Crash triage and minimization
A sanitizer report is reduced to its SUMMARY: line and stack frames with
addresses and source line numbers normalized out, then hashed into a
16-character signature; records sharing a signature are treated as one root
cause. For each unique signature, Hypothesis's find is used to shrink a
triggering input to a minimal byte string that still reproduces the same
crash or timeout classification -- rather than simply keeping the first
crash observed -- and the minimized input is re-run once, standalone,
against the pinned build to verify it reproduces outside the shrinking
process itself.

Reproducibility engineering
Hypothesis's .example() draws from a private internal random state that
Python's own random.seed() does not reach, and separately orders its
candidate batch with the module-level random.shuffle. Seeding only one of
the two leaves the produced example stream non-reproducible across process
invocations; a shim (seeding.seed_everything) seeds both, which we verified
gives byte-identical example streams across repeated processes on
Hypothesis 6.165.5 / CPython 3.14.7. Two documented, non-internal
alternatives -- settings(derandomize=True) and global_force_seed -- were
rejected because both collapse a run's draws into repeats of a single small
batch, which would change the generation algorithm itself rather than only
fix its starting point. Because this shim depends on an internal
implementation detail, the Hypothesis version is pinned in requirements.txt
and the shim fails loudly rather than silently if the relied-upon attribute
is renamed or removed in a future release. Every run additionally persists
a manifest (seed, package versions, platform, model, feedback mode, CLI
arguments) and a reproducibility report (compiler, harness SHA-256, exact
command line, repository commit); the compiled harness binary itself is
gitignored and host-compiled, so it is identified by content hash rather
than assumed identical across machines. This reproducibility guarantee is
scoped to the generated input stream only: it does not extend to LLM
proposals themselves (temperature 0.2, no server-side seed), to
wall-clock-dependent timeout classification, or to the harness binary's
bit-for-bit identity across hosts and toolchains.

Experimental design
For RQ1, we run fifteen independent, seeded trials (seeds 0-14) of a static
baseline generator and fifteen independent, seeded trials of the
LLM-refined loop against the same pinned cJSON build, each trial consisting
of up to five refinement iterations of up to 500 examples. We report
acceptance rate, structural fingerprints, and rejection signatures per
trial. We compare the arms statistically only on acceptance rate, the
scale-free outcome; the count-based metrics are retained as descriptive
feedback signals because the two arms execute different total numbers of
inputs. For RQ2, we run the identical pipeline, entirely unmodified,
against parson for five real iterations, with a human reasoning over each
iteration's campaign summary in the proposer's role and every resulting
proposal passing through the same load_strategy validation and
run_campaign execution path a model's output would take; this substitutes
for a live API call without altering any other part of the pipeline being
tested. For RQ3, we repeat the RQ1 refined-arm recipe under each of the
three feedback modes (counts, counts+rejections, full), five seeded trials
(seeds 0-4) per mode against the same cJSON build. In one trial per mode,
every one of the five iterations produced an LLM proposal that failed
sandbox validation, leaving that trial with no executed inputs; following
the same iterations_with_data convention used throughout, these three
trials are excluded, leaving four usable trials per mode.
```

### 5.4 Results/Evaluation section (full text)

```
Section: Evaluation

RQ1: cJSON, baseline versus LLM-refined
Table 1 reports the fifteen-seeded-run-per-arm comparison described in the
Methodology -- an extension of an initial five-run-per-arm pilot to a
larger sample, run identically. Every refined-arm run has a higher
acceptance rate than every baseline-arm run. Since acceptance rate is
scale-free, this arm-level comparison remains interpretable despite the
different numbers of executed inputs. All fifteen observations have
complete rank separation, giving an exact two-sided permutation p-value of
2/C(30,15) ~ 1.29x10^-8 for this run-level comparison. This is the
smallest attainable exact p-value for a design with n=15 per arm, and, as
with the smaller pilot, should be read as the strongest separation this
design can report rather than as a precisely estimated population effect.
Structural fingerprints and rejection signatures remain useful feedback
signals, but their aggregate counts are not tested as arm-level effects
because the refined runs execute more iterations.

TABLE 1 -- cJSON: baseline vs. LLM-refined, fifteen seeded runs per arm
(mean over runs). The exact two-sided permutation p ~ 1.29x10^-8 applies
only to the scale-free acceptance-rate comparison; fingerprint and
rejection signature totals are descriptive because budgets differ.
  Metric                                          Baseline  Refined   Change
  Acceptance rate                                 58.21%    97.07%    +38.86 pp
  Structural fingerprints (sum/run; descriptive)  274.5     598.2     ---
  Rejection signatures (sum/run; descriptive)     87.8      24.1      ---
  Crashes / timeouts / signals                    0         0         ---

[Figure: Per-run acceptance rate, baseline vs. refined, cJSON (fifteen
seeded runs per arm). Every refined run exceeds every baseline run.]

Unequal budgets. Baseline runs execute 500 inputs on average; refined runs
execute 1,533 on average, because the refinement loop ran more iterations
per run on average and some iterations end early on a rejected LLM
proposal (RQ3). Every count-based quantity (accepted, rejected,
fingerprints, signatures as raw totals rather than rates) therefore scales
with a budget that differs between arms and is not directly comparable;
acceptance rate is scale-free and unaffected by this. We report the
budget-sensitive metrics above as sums over a run's iterations specifically
so the comparison is transparent about this rather than implying parity.

No crashes in either arm. Zero sanitizer crashes, timeouts, or fatal
signals occurred in either arm across all thirty runs. The effect measured
here is therefore on generator quality -- validity and structural diversity
-- not on vulnerability discovery in cJSON; we do not claim or imply that
refinement found, or was likely to find, a memory-safety bug in this
target.

RQ2: generalization to parson
We reused every pipeline component unchanged against a second, independent
target, parson (commit ba29f4e, v1.5.3), with a human standing in for the
LLM proposer call and every resulting proposal passing through the
identical validation and execution path. Reconciling the same JSON grammar
against parson's real behavior surfaced three adaptations, two of which go
the opposite direction from the cJSON adaptations reported in the
Methodology under the identical grammar: (i) unlike the cJSON harness,
parson's parse entry point does not require full-buffer consumption, so
trailing garbage after a valid value is silently accepted -- a superset of
what the grammar's `json : value EOF ;` production specifies; (ii) parson
explicitly rejects any object containing a duplicate key, propagating the
rejection up as a failure for the whole object -- a subset of what cJSON
accepts, even though the grammar itself is silent on duplicate keys for
both; (iii) parson enforces a fixed nesting limit (MAX_NESTING = 2048),
rejecting deeper structures outright rather than exhibiting unbounded
recursion. That the same formal grammar under-determines a directly
opposite validity decision (duplicate keys: accept vs. reject) on two
independently implemented parsers is, on its own, evidence that a purely
formal grammar specification cannot supply the target-specific signal
needed to fuzz either implementation precisely.

[Table 2 -- parson: five real refinement iterations, 500 examples each --
lists per-iteration focus, accept/reject counts, and fingerprints;
iterations progressively target wide objects/arrays, hash-bucket
collisions, and the internal error-cleanup free path.]

Result. No crash was found across all 3,000 sanitizer-instrumented
executions (500 baseline plus 5x500 refinement iterations), verified by
grepping every run's stderr for AddressSanitizer, UndefinedBehaviorSanitizer,
and LeakSanitizer text and checking for any non-accepted/rejected status.
Manual review of the highest-risk code paths -- parse_utf16's raw pointer
walk across surrogate pairs, process_string's output-buffer sizing,
json_object_grow_and_rehash's linear probing, and, informed specifically by
iterations 4-5, json_object_add's duplicate-key failure branch and
parse_object_value/parse_array_value's missing-bracket failure branch --
found that each relies on the harness's own null terminator as a safe,
in-bounds stopping condition, and that internal cleanup calls to
json_value_free are consistent with the harness's own top-level call (an
object's key count is never incremented before a duplicate is detected, so
cleanup never iterates past the last successfully added slot). We report
this as a defensible, evidence-supported explanation for the absence of a
crash within this budget, not as proof that none exists: five iterations
against one pinned commit, exercising the parse and internal free paths but
not parson's public mutation API (json_object_remove, json_array_remove,
and the _replace_* family), is a bounded search, and we do not claim more
than that bound supports.

RQ3: which feedback signal drives the improvement
Table 3 reports the feedback-signal ablation: the same refined-arm recipe
run under each of the three feedback modes, five seeded trials (seeds 0-4)
per mode. In one trial per mode, all five refinement iterations produced an
LLM proposal that failed sandbox validation, leaving that trial with no
executed inputs; these three trials are excluded, leaving four usable
trials per mode -- the same proposal-rejection behavior visible throughout
RQ1's refined arm, just concentrated into a full trial in these
smaller-sample runs rather than spread across otherwise-successful trials.

TABLE 3 -- cJSON refined arm under three feedback modes, four usable seeded
trials per mode. Descriptive only: with n=4 per condition and no separation
between conditions, no significance test is reported or implied.
  Feedback mode        Acceptance rate  Fingerprints (sum/run)  Rej. signatures (sum/run)
  counts                92.58%           505.5                   6.5
  counts+rejections     96.42%           457.3                  26.8
  full                  95.53%           503.5                  34.8

All three modes raise acceptance rate to a broadly similar, near-ceiling
level -- exposing only acceptance/rejection counts is already close to
sufficient for that specific objective, and the per-trial acceptance rates
across modes overlap (Table 3), so we do not claim any mode is
statistically distinguishable from another on this metric at n=4. The one
pattern worth reporting descriptively is rejection-signature diversity,
which increases monotonically with how much of the signal the proposer
sees: counts alone, with no visibility into which rejection shapes are
already covered, produces under a fifth of the distinct rejection
signatures that full feedback does, consistent with -- though not proof of
-- the concern raised in the Discussion that a proposer optimizing
acceptance rate without visibility into rejection diversity has less reason
to keep producing malformed, boundary-probing input. At four trials per
condition, this is a suggestive, small-sample result, not a tested effect,
and we report it as exactly that.
```

---

## 6. GAPS / KNOWN LIMITATIONS (read this before porting to a new target)

Ranked roughly by how much they'd bite when moving to a different kind of system
(e.g. a Dart/Flutter mobile JSON deserializer or a C++ binary codec, as this paper's
own Discussion section names as future work):

1. **Structural fingerprint is JSON-specific and hand-designed, not derived from the
   grammar.** `_structure()` (Section 1.2) hard-codes JSON's six structural
   characters. Porting to any other format requires rewriting this function around
   that format's actual token alphabet — there is no generic, grammar-driven
   fingerprinting mechanism in this codebase to fall back on. For a binary codec
   (protobuf, a custom TLV format) "structural character" doesn't even map cleanly
   onto printable bytes — you'd need a different proxy entirely (e.g. a coarse
   histogram over structurally significant byte offsets, or a length/field-count
   fingerprint), and that redesign is unvalidated territory.

2. **The "crash" oracle assumes a C process under a sanitizer + subprocess model.**
   `runner.py::run_input()`'s classification (`timeout` / `signal:<name>` / `crash`
   via ASan/UBSan stderr text / `accepted` via a stdout sentinel / `rejected`) is
   built entirely around spawning a native subprocess and inspecting its exit code,
   signal, and stderr. **This does not transfer to a memory-safe language target**
   (Dart, the Discussion section's own named example) — there is no sanitizer output,
   no fatal-signal semantics for a caught exception, and "crash" would need to be
   redefined around uncaught exceptions, assertion failures, or API-contract
   violations instead. The Discussion section states this explicitly as unaddressed
   future work, not a solved problem: *"a memory-safe language where a 'crash' oracle
   must be redefined around uncaught exceptions and API contract violations rather
   than sanitizer output... would test generalization along a materially different
   axis than implementation alone."* Nothing in this codebase does that redefinition
   for you.

3. **The harness contract (`status=accepted` / `status=rejected offset=N` on stdout,
   input on stdin) is a hand-written convention, not automatically derivable from a
   target's real API.** A stdin-driven, single-shot subprocess harness is trivial for
   a C library exposing a `parse(buffer, length)` function. It is a much bigger
   engineering lift for: (a) a library only reachable via language bindings/FFI
   rather than a plain C ABI, (b) a target that's a long-running process or a mobile
   app rather than a spawnable one-shot binary (the Discussion names this too: *"a
   live, running mobile or server application rather than a bounded harness
   process... would require redesigning the outcome-classification step"*), or (c) a
   target whose interesting behavior only manifests through stateful, multi-call
   sequences rather than one parse-and-done call.

4. **The sandbox around LLM-authored code is explicitly *not* a security boundary**
   (Section 1.5) — it's a blocklist that stops accidental misuse, not adversarial
   code execution. If a second paper's target or infrastructure makes untrusted-code
   execution higher-stakes (e.g. running inside shared infra, or handling a model
   that might be adversarially prompted), you need real process/container isolation,
   not a port of `load_strategy` as-is.

5. **The Hypothesis reproducibility shim (`seeding.py::seed_everything`) is coupled
   to a **private, undocumented** Hypothesis internal**
   (`hypothesis.core.threadlocal._hypothesis_global_random`), verified only against
   `hypothesis==6.165.5` / CPython 3.14.7. It fails loudly (raises `SeedingError`) if
   that attribute disappears in a future Hypothesis release — this is a documented,
   deliberate fragility, not an oversight, but it means **you cannot casually bump
   the `hypothesis` pin** without re-verifying this shim still gives byte-identical
   draw streams. If the new project uses a different property-testing library
   entirely (e.g. a Dart target might use `package:test`'s own generators, or a
   custom fuzzer), this entire reproducibility mechanism doesn't transfer and needs
   to be re-derived from scratch for whatever library is used.

6. **Rejection-signature deduplication has no normalization step** (Section 3.4) —
   it deduplicates on the harness's raw rejection string. For cJSON this happens to
   work well because the rejection message is just `status=rejected offset=<n>` (a
   small integer), so the signature space is naturally bounded. A target whose
   rejection/error messages are noisier (e.g. embed full messages with varying byte
   ranges, timestamps, or pointer-ish values for semantically identical failures)
   would need a `sanitizer_signature`-style normalization pass added for rejections,
   analogous to what already exists for crashes — this doesn't currently exist.

7. **The refinement objective has no floor against acceptance-rate over-optimization.**
   The Discussion section flags this directly: acceptance rate rose to 97.1%, close
   to a ceiling, and *"a generator that always emits valid input has, by
   construction, stopped exercising the accept/reject boundary at all."* The proxy
   signal as designed rewards acceptance rate monotonically with no explicit target
   reject-rate floor. This is named as a direct, low-cost fix that was *not*
   implemented in this codebase — worth doing properly in a second paper rather than
   inheriting the same gap.

8. **Statistical test is currently hand-derived, not library-backed** (Section 3.3).
   Fine for the complete-separation case reported here, but fragile if a new target's
   results don't happen to produce complete rank separation — you'd need to actually
   wire in `scipy.stats.mannwhitneyu(..., method="exact")` (or an equivalent) rather
   than reuse the by-hand `2/C(n,n)` shortcut, which only applies in the boundary
   case.

9. **Only one model, one temperature, one target family (small, well-audited C JSON
   parsers) was tested**, and the paper's own "External validity" threat says so
   explicitly: *"We make no claim that the magnitude of the cJSON effect, or the
   absence of a crash on parson, generalizes to other formats, other parsers, or
   other proposer models."* Treat every specific number in this document (58.2% →
   97.1%, p≈1.29e-8, the ablation percentages) as belonging to *this* target and
   *this* model — do not assume they transfer in magnitude to a new target, only the
   *pipeline architecture* is claimed to transfer (that's exactly what RQ2/parson was
   testing).

10. **Build system assumption**: `build_target.sh` assumes a flat, single-command
    `clang <flags> file1.c file2.c -o binary` build with no dependency graph. A
    Dart/Flutter target's build (AOT-compiled binary, or a Flutter integration test
    harness) or a C++ target with a real build system (CMake, Bazel, GN) will not fit
    this shell-script pattern and needs a properly separate build step — the pipeline
    downstream of the harness binary doesn't care how the binary was produced, only
    that it exists, is sanitizer-instrumented (or has an equivalent-strength oracle
    for a non-native target), and honors the stdin/stdout contract in Section 1.6.
