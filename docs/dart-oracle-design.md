# Dart/Flutter JSON Deserialization: Oracle and Experiment Design

This document records the design decisions for this project's oracle, target set,
harness architecture, and experiment plan. It supersedes the "not yet started"
placeholder in the README and is written to the same standard as
[`methodology-handoff.md`](methodology-handoff.md): concrete enough that
implementation can start directly from it, and explicit about what is reused
unchanged from the original pipeline versus what is genuinely new.

## 0. Why not a single-target crash hunt

The obvious port of the original methodology — pick one Dart JSON decoder, wrap it
in a stdin/stdout harness, and look for a "crash" — was rejected. `dart:convert`'s
decoder is a heavily audited SDK component; the most likely outcome is the same
negative result parson already produced, without parson's advantage of a novel
*second target* to compare against. That would make this paper a rerun of RQ2 on a
less interesting target rather than a new contribution.

Instead this project keeps the refinement-loop machinery (Section 1 of the handoff)
essentially unchanged and replaces the single crash oracle with two oracles that are
both (a) genuinely novel relative to the original paper and (b) produce findings a
Flutter team could act on directly, independent of whether anything "crashes":

1. **Cross-framework differential divergence** (Section 2) — no ground truth needed;
   disagreement between independently-implemented decoders is itself the signal,
   exactly as duplicate-key handling disagreeing between cJSON and parson was
   reported as a finding in the original RQ2, generalized here to four targets.
2. **Numeric round-trip / precision-loss** (Section 3) — a ground-truth oracle:
   a decoded value either preserves the exact input magnitude or it doesn't. This
   catches silent corruption, which is strictly more dangerous than a crash because
   it fails quietly in production, and it maps onto a real, frequently-reported Dart
   pain point (large integer IDs losing precision through `double`-backed decoding).

## 1. Research questions

- **RQ1 (replication/generalization check).** Using the unmodified coverage-free
  refinement loop and proxy signal (acceptance rate, structural diversity, rejection
  signatures — Section 1.2 of the handoff), does LLM-guided refinement improve a
  Dart JSON generator's acceptance rate and structural diversity relative to a
  static grammar-only baseline, as it did for cJSON? This is intentionally cheap:
  the format is still JSON, so the grammar, `_structure()` fingerprint, prompt
  template, sandbox, and loop all transfer with no redesign — only the harness
  target changes. Its purpose is to confirm the *pipeline* (not just the cJSON
  result) generalizes, before spending effort on the two novel RQs below.
  **"Accepted" is defined exactly as cJSON's own grammar defines it** (handoff
  Section 2.1: `json : value EOF ;`, any value type, not only objects) — see
  Section 9's `structural_valid_non_object` status — precisely so this RQ tests
  pipeline portability on a like-for-like criterion, not a criterion this
  project's own Record schema happens to impose.

  **Status (2026-09-05): implemented and verified against the real compiled
  harness, no LLM yet.** `src/agentic_fuzzing/{seeding,proposal,experiment,llm,
  json_strategy,refinement}.py` are the original project's files, copied
  verbatim (confirmed byte-identical reproducibility on the exact pinned
  `hypothesis==6.165.5` — the newer 6.167.1 does *not* expose the private
  attribute `seeding.py` patches, reproducing on the nose the fragility the
  original project's own gap 5 warned about); `refinement.py`'s only edit is
  its `run_campaign` import target. `dart_runner.py` (batch subprocess client)
  and `dart_campaign.py` (this RQ's classifier, matching the original
  `run_campaign`'s exact signature so `refinement.py` needed no other changes)
  are new. `scripts/build_dart_target.sh` and `scripts/run_dart_rq1_baseline.py`
  (both adapted from the originals) ran a real 40-example baseline campaign
  against `build/dart_json_harness`: 20/40 accepted, exactly the expected
  ~50/50 split between `baseline_json` (should mostly parse) and
  `near_valid_json` (deliberately corrupted) — the harness's classification is
  behaving correctly.

  **Status (2026-09-06): complete, n=5 per arm, real `OPENAI_API_KEY`
  spend.** `grammar/JSON.g4` (copied verbatim from the original repo) and
  `scripts/run_dart_rq1_refinement.py` (adapted from the original's
  `run_refinement.py`) now exist; `scripts/aggregate_runs.py` is the
  original's file, copied verbatim — RQ1's `CampaignSummary` shape is
  byte-identical to the original's, so the aggregation script needed no
  changes at all. **Baseline** (seeds 0-4, 500 examples, no LLM): acceptance
  rate exactly 50.0% every run (by construction), stdev 0. **Refined**
  (seeds 0-4, 5 iterations x 500 examples, `gpt-4.1-mini`): per-run
  acceptance rate 68.6%, 98.0%, 97.3%, 98.2%, 98.1% — mean 92.04%, stdev 13.1
  (one run's lower rate traces to a seed with fewer usable iterations —
  `iterations_with_data` ranged 1-4 of 5 across runs, the rest consumed by
  ordinary proposal failures, e.g. one hit Python's recursion limit building
  an unbounded-depth strategy, logged and handled exactly as designed).
  Every refined run still exceeds every baseline run: complete separation,
  exact two-sided Mann-Whitney U **p ≈ 0.00794** (`2/C(10,5)` — the same
  combinatorial value as RQ2's Section 11 result, both being n=5/n=5
  complete separations; the underlying effects are unrelated). This is the
  clean replication RQ1 was designed to be: refinement raises the fraction
  of generated documents that are syntactically valid JSON from 50% to a
  92% mean, mirroring the original paper's 58.2%-to-97.1% cJSON result in
  shape, on a completely different runtime and language. Structural
  fingerprint counts are, as in the original, reported descriptively only —
  not directly comparable between arms since the refined arm executes more
  inputs per run when iterations succeed (500-2000 vs. baseline's fixed 500,
  handoff Section 3.3's exact discipline).

  **Taken together with Section 11's RQ2 result, this is a real, three-part
  story worth foregrounding in the paper**: the underlying refinement-loop
  *mechanism* generalizes cleanly to a new runtime on a simple
  acceptance-style objective (RQ1, replicating the original), but the same
  mechanism, same model, same iteration budget, does not straightforwardly
  transfer to a differential, multi-implementation divergence objective
  (RQ2) — refinement helps or hurts depending on what exactly is being
  optimized. That contrast is itself a nontrivial, reportable methodological
  finding, not just two isolated numbers.
- **RQ2 (centerpiece).** Across four independently-implemented, widely-used Dart
  JSON deserialization paths, does malformed or boundary-case input surface
  behavioral divergence — one path accepting where another rejects, or two
  accepting paths producing different values for the same input — and what do the
  resulting divergence categories imply for teams choosing between these
  frameworks?
- **RQ3 (second novel oracle).** Does JSON numeric decoding across these same four
  paths preserve exact value semantics for boundary-magnitude integers and
  high-precision decimals, and does LLM-guided refinement — steered by distinct
  precision-loss signatures as its proxy, in place of acceptance rate — find
  precision-loss-triggering inputs at a higher rate than a static numeric-edge-case
  baseline?
- **RQ4 (optional, low-cost confirmatory).** Reuse the original feedback-mode
  ablation (`counts` / `counts+rejections` / `full`) unchanged against the RQ1
  setup. Deprioritized relative to RQ2/RQ3 — include only if time remains, since it
  reuses existing infrastructure almost for free but adds no new methodological
  contribution beyond confirming the original RQ3 result on a second target.

## 2. Target set and pinned versions

Four decoding paths over one shared logical schema (Section 4), chosen because they
are the four ways a real Flutter codebase actually deserializes JSON today — not
picked for novelty, picked for relevance:

| # | Path | Package | Version pinned | Why it's in the set |
|---|---|---|---|---|
| A | Manual | `dart:convert` (SDK) | Dart SDK 3.13.2 (stable) | The "no codegen" baseline every Dart tutorial teaches: `jsonDecode` + explicit `as` casts / manual null checks. Represents hand-written parsing code with no generated safety net. |
| B | `json_serializable` | `json_serializable 6.14.1` + `json_annotation 4.12.0` | pinned via `harness/pubspec.lock` | The most widely used Dart codegen serialization package. |
| C | `freezed` | `freezed 4.0.1` + `freezed_annotation 3.1.0` (+ `json_serializable` as its JSON backend) | pinned via `harness/pubspec.lock` | Adds sealed/union-type discrimination on top of (B)'s JSON backend — the interesting divergence surface is in how it handles the discriminant field, not the leaf-value decoding, which should mostly match (B). |
| D | `built_value` | `built_value 8.13.0` + `built_value_generator 8.13.0` | pinned via `harness/pubspec.lock` | An independently-designed serialization model (`Serializers`/`FullType`-based, not annotation+`Map`-based like B/C) — the most likely source of genuine independent-implementation divergence, analogous to parson vs. cJSON being independent C implementations. |

**Status (2026-09-05): resolved and verified.** `harness/pubspec.yaml` declares all
four dependencies together; `dart pub get` resolves them with no conflicts (68
transitive packages, `harness/pubspec.lock` committed). This required upgrading the
local Flutter/Dart toolchain from Dart 3.12.2 to 3.13.2 (`freezed 4.0.1` requires
SDK ≥3.13.0) — a deliberate global-environment change, done with explicit
confirmation since it affects every Dart/Flutter project on the machine, not just
this one. `pubspec.lock` is the source of truth for exact versions from here on;
the table above records the versions at the time of pinning for readability, not as
a second source of truth to keep in sync by hand.

## 3. Shared logical schema

One schema, hand-implemented four times (once per path), analogous to how the
original project's `json_strategy.py` was one hand-translation of `JSON.g4`. Fields
chosen to exercise the specific places these frameworks are expected to differ:

```
Record {
  id: int                 // boundary-magnitude integer, RQ3 target
  amount: decimal-as-string-in-JSON  // high-precision decimal, RQ3 target
  name: String?            // nullable field — null-safety contract surface
  status: enum(Active, Inactive, Unknown)  // unknown-enum-value handling
  tags: List<String>
  child: Record?           // one level of recursion — bounded, mirrors grammar's recursive value
}
```

Rationale per field:
- `id`/`amount` exist purely to feed RQ3 (Section 5); every other field feeds RQ2.
- `status` as an enum is a known, real divergence point: some Dart codegen tools
  throw on an unrecognized enum string, others fall back to a documented default,
  others silently produce a null — this is exactly the kind of practically-relevant
  divergence RQ2 is built to surface.
- `name: String?` under sound null safety is where "manual" (path A) code most
  commonly gets it wrong in real Flutter codebases (raw `json['name'] as String`
  throwing a raw, uncaught `TypeError` instead of a handled, documented failure) —
  this is Tier B in the oracle taxonomy below, and is itself a finding worth
  reporting even without cross-path divergence.
- `child` provides one bounded level of recursion so the structural fingerprint
  (Section 1.2 of the handoff, reused unchanged) still has nesting to characterize;
  it is not unbounded, for the same reason the original `json_value` strategy capped
  `max_leaves`.

## 4. Oracle taxonomy (what "failure" means here)

Four tiers, checked in this priority order per input — mirrors the original
`runner.py` priority-ordered classification (timeout → signal → crash → accepted →
rejected) but re-scoped to a multi-path batch harness:

- **Tier A — process-level crash.** The harness process itself is killed by a
  signal, times out, or exits non-zero for a reason outside the harness's own
  per-path exception handling (Section 5.3) — e.g. a native stack overflow or OOM
  that bypasses Dart's catchable `StackOverflowError`. This is the direct analog of
  the original crash tier and is expected to be rare; when it happens it is the
  strongest possible finding and gets the same manual-triage treatment the original
  project gave sanitizer crashes.
- **Tier B — undocumented exception contract violation.** A path rejects the input,
  but with an exception type outside that path's own documented failure surface
  (e.g. a raw `TypeError`/`NoSuchMethodError`/`RangeError` escaping instead of a
  `FormatException`/`CheckedFromJsonException`/path-specific deserialization
  exception). Computed per-path, no comparison to other paths needed. This is
  directly actionable: it tells a team "this framework can throw an exception type
  your `catch (FormatException)` won't catch."
- **Tier C — cross-path divergence.** Computed after all four paths have been run
  on the same input. Two subtypes, both fully automatic:
  - *Accept/reject divergence*: at least one path accepts and at least one rejects.
  - *Value divergence*: two or more accepting paths produce different canonical
    values for the same input (see Section 4.1 for what "canonical value" means and
    how comparison avoids introducing floating-point bugs of its own).
- **Tier D — numeric round-trip divergence.** Section 5. Kept as its own tier
  rather than folded into Tier C's value divergence because it has a ground truth
  (the exact input decimal text) and applies even when all four paths *agree* with
  each other but all four still lose precision relative to the input.

### 4.1 Canonical value comparison (avoiding a second-order precision bug)

Comparing "decoded values" across four frameworks safely requires that the
comparison itself not silently reintroduce floating-point error. Each path's
decoded value is converted to a canonical report via a fixed routine written once
in the harness (not per-path), which represents every field as one of: a UTF-8
string, a boolean, `null`, an exact-integer string (arbitrary precision, not a
64-bit `int`), an exact-decimal string (Section 5.1's ground-truth format, not a
`double`), a sorted-key JSON object of canonical values, or an ordered list of
canonical values. Two canonical values are compared as strings/structures, never as
`double`, so a value divergence can never be a false positive introduced by the
harness's own comparison logic — any reported Tier C/D divergence is real by
construction.

## 5. RQ3's numeric oracle in detail

### 5.1 Ground truth representation

Numbers are generated in Python as exact-precision Python `int` values, not
`float` — generation must avoid `float` from the start, since drawing one and
then formatting it already loses the information the oracle is designed to
test for. Concretely: `st.integers(...)` with a range and distribution biased
toward boundary magnitudes (near `double`'s 2^53 exact-integer boundary, and
separately near 64-bit `int` boundaries, plus well beyond both), serialized
via plain `json.dumps`. **Simpler than an earlier draft of this section
assumed**: Python's `json.dumps` already serializes arbitrary-precision `int`
values as correct, exact JSON integer literals with no `float` detour (
verified: `json.dumps(10**26) == "100000000000000000000000000"`, exact) — so
no hand-assembled decimal-text generation is needed; plain `st.integers()`
plus `json.dumps` already gives exact-precision literals of any magnitude.
JSON's grammar permits arbitrary-precision number literals syntactically
(`NUMBER` in `JSON.g4`, Section 2.1 of the handoff, has no magnitude limit)
even though most parsers/decoders silently coerce them on the way in — that
gap is exactly what this oracle measures, and Section 5.2's confirmed finding
(json_serializable/freezed's `.toInt()` silently saturating a 10^26 `id` to
`int64::MAX`) is a first, concrete instance of it.

Ground truth = the canonicalized literal text itself (strip a leading `+`, strip
insignificant leading zeros, normalize exponent case/sign), not a re-parse of it by
any Dart or Python numeric type.

**Correction (2026-09-05): the target field is `id`, not `amount`.** An earlier
draft of this section named `amount` alongside `id` as a target, but `amount`
is typed `String` in the Section 3 schema specifically so it carries text
byte-for-byte with no numeric coercion by any path — there is no precision to
lose on a string field, so it cannot exhibit this oracle's failure mode at
all. `id` (typed `int`, decoded from a bare JSON number token) is the correct
and only schema field this oracle applies to.

**Preliminary finding, confirmed empirically (2026-09-05) before writing any
generator** — reading the actual generated code settled this rather than
assuming it: `json_serializable`'s and `freezed`'s generated code both decode
`id` as `(json['id'] as num).toInt()` (`harness/lib/schema/
json_serializable_model.g.dart:10`, `freezed_model.g.dart:11`), **not**
`json['id'] as int` (which is what `manual.dart` and `built_value` effectively
require). Probing `build/dart_json_harness` directly with
`id: 99999999999999999999999999` (10^26, far beyond both `double`'s exact-
integer range and 64-bit `int`'s range) reproduces exactly the failure mode
this oracle exists to find: **A (manual) and D (built_value) both reject** with
a type-cast/`DeserializationError` (the JSON number decodes to a `double`
first, and a raw `int` cast on a `double` fails), **while B
(`json_serializable`) and C (`freezed`) both silently accept, reporting
`id: 9223372036854775807`** (64-bit `int` max) — a ~10^26-to-2^63-1 silent
truncation with no exception, no warning, on two of the four most common
Dart JSON codegen frameworks in real use. Two smaller boundary probes
(2^53+1, and `int64::MAX` itself) round-trip losslessly and identically on
all four paths, confirming the failure is specifically about magnitudes
where `.toInt()` on an out-of-range `double` silently saturates, not about
common near-boundary values a real API would plausibly send. This is a
strong, concrete, directly-actionable candidate for the paper's RQ3 result —
finding it took one hand-picked probe once the actual generated code was
read, before the automated generator/harness even existed; the fuzzing
campaign's job is establishing how systematically it holds (does it also
saturate at other codegen-generated numeric fields, is the saturation always
exactly `int64::MAX`/`MIN`, does it depend on sign) and finding any exceptions.

### 5.2 Per-path scoring

For each path, after decoding: re-derive a canonical decimal string for the decoded
value using the fixed harness-side routine from Section 4.1 (which must itself
avoid `double` for this step — e.g. by inspecting the underlying representation the
path actually produced, such as `built_value`'s typed field or a `Decimal`-like
wrapper if the path uses one, falling back to `double.toString()` only for paths
that decode straight to `double`, in which case the ground-truth comparison is
expected to show loss and that expectation is itself part of the finding). Compare
the re-derived string to ground truth; a mismatch is a Tier D record for that path
on that input, tagged with the magnitude/precision bucket (Section 5.3) so results
are reported as a rate curve over boundary distance, not a single yes/no count.

### 5.3 Precision-loss signature (for refinement-loop feedback)

Analogous to the original's rejection-signature dedup (handoff Section 3.4), but
normalized the way the handoff's Section 6, gap 6 flags as missing for a noisier
target: a signature is `f"{path_name}:{magnitude_bucket}:{loss_direction}"` where
`magnitude_bucket` buckets `len(digit_string)` into coarse ranges (e.g. `<15`,
`15-17`, `18-19`, `20+`) rather than using the raw digit count, and `loss_direction`
is `truncated` / `rounded` / `exponent-shifted`. Distinct-signature count is the new
proxy field fed into the refinement prompt in place of (or alongside) acceptance
rate for the RQ3 arm — same `CampaignSummary`-shaped plumbing, new field.

## 6. Harness architecture

### 6.1 Why not one subprocess per input (the original model)

The original C harness spawns one process per input because process-per-input is
cheap for a native binary. A Dart VM cold start is not free, and this project needs
four decode paths per input rather than one, so process-per-input would multiply
both costs. Since Dart is memory-safe, a per-path exception no longer needs a fresh
process for fault isolation the way a C sanitizer crash does — an exception can be
caught in-process without corrupting the state needed to test the next path or the
next input. This changes the harness shape but **not** the outcome-classification
contract's spirit: a batch harness still classifies each input independently, and
the driver still wraps the whole batch invocation in the same
timeout/signal/nonzero-exit checks `runner.py` already performs (handoff Section
1.6) — only the granularity moves from "one process = one input" to "one process =
one campaign, one flushed stdout line = one input's result."

### 6.2 Contract

Build once per experiment via `dart compile exe harness/dart_json_harness.dart -o
build/dart_json_harness` (AOT, analogous to `build_target.sh` compiling the
sanitizer-instrumented C binary — Section 4.2 of the handoff). The compiled
executable:

- Reads newline-delimited JSON from stdin, one object per line:
  `{"input_b64": "<base64 of the candidate's raw bytes>"}`. Base64 (not raw text)
  because a candidate input is arbitrary bytes and may be invalid UTF-8 by design
  (testing decoder robustness against bad encoding is in scope) — a raw-text NDJSON
  line could not represent that.
- Per line: base64-decode to `Uint8List`; attempt `utf8.decode(bytes, allowMalformed:
  false)` as its own classified step (a `FormatException` here is recorded as
  `utf8_decode_error` and short-circuits the rest of the line — none of the four
  paths can proceed without a String); on success, run all four paths against the
  same decoded string, each wrapped in its own `try { ... } on Object catch (e, st)`
  so one path's exception can never prevent the other three from running on the
  same input; compute the Tier C/D classification from the four results; write one
  JSON result line to stdout and **flush immediately**.
- The immediate per-line flush is deliberate and load-bearing: if the process is
  later killed by a true process-level fault (Tier A), the driver can identify
  exactly which input line was being processed (the first line after the last
  flushed result) rather than losing attribution for the whole batch — preserving
  the original project's "nothing is thrown away, auditable after the fact"
  property (handoff Section 1.7) at batch granularity instead of per-process
  granularity.

### 6.3 What stays exactly as in the original pipeline

- `_structure()` (handoff Section 1.2) — unchanged. The format is still JSON, so
  the six-symbol fingerprint alphabet still applies with no redesign; this is one
  of the few places this project does *less* work than a from-scratch port, and is
  called out here explicitly per the handoff's own gap 1, since gap 1 warned this
  function is JSON-specific but did not warn it would also need to be redesigned
  for a same-format retarget — it doesn't.
- `load_strategy()` sandboxing (handoff Section 1.5), the refinement loop's
  iteration/example budget caps (handoff Section 1.7), and `seeding.py` (handoff
  Section 1.4/6, gap 5) — all reused unchanged; none of them are C- or
  cJSON-specific, they operate on the Python/Hypothesis side of the pipeline only.
- The `build_refinement_prompt` template (handoff Section 1.3) — reused with the
  `metrics` dict's field set extended (RQ3 adds precision-loss-signature counts;
  RQ2 is not itself loop-driven per input in the same way, see Section 7) rather
  than replaced.

## 7. Experiment design

- **RQ1**: same 15-seed baseline-vs-refined design as the original (handoff Section
  3.1), same statistical treatment (handoff Section 3.3 — exact permutation test on
  acceptance rate, `scipy.stats.mannwhitneyu(..., method="exact")` used directly
  from the start this time rather than hand-derived, addressing handoff gap 8).
  Target for this arm is path B (`json_serializable`) alone, chosen as the most
  representative "typical Flutter app" codegen path — RQ1 is a pipeline-portability
  check, not the place to spend the four-way harness's cost.
- **RQ2**: not a rate comparison between two arms — like the original parson result,
  this is a campaign (or a small number of seeded campaigns for coverage) whose
  output is a set of concrete divergence cases, each manually triaged and
  categorized (accept/reject divergence vs. value divergence, and which
  field/path pair) the same way parson's manual code review was reported
  qualitatively rather than statistically (handoff Section 5.4, RQ2 discussion).
  Both the static baseline generator and the LLM-refined loop are run against the
  four-path harness so refinement's effect on divergence-finding rate can still be
  reported descriptively, without claiming a tested effect size.
- **RQ3**: mirrors RQ1's baseline-vs-refined structure (seeded, 15 runs per arm if
  time budget allows, otherwise scaled down and reported as such rather than
  silently reducing rigor), but the generator is the numeric-edge-case generator
  (Section 5.1) instead of `json_strategy.py`'s general-purpose one, and the tested
  metric is precision-loss rate (mismatches / accepted-and-comparable inputs) in
  place of acceptance rate.
- **RQ4**: only attempted after RQ1-RQ3 are complete, reusing the RQ1 setup with
  `--feedback` varied exactly as in the original ablation (handoff Section 3.5).

## 8. Open items before implementation starts

- ~~Confirm all four packages resolve together under one `pubspec.yaml` without
  version conflicts~~ **Done (2026-09-05).** `harness/pubspec.yaml` +
  `harness/pubspec.lock` resolve cleanly; see Section 2's status note.
- ~~Decide whether `freezed`'s JSON backend is configured to delegate to
  `json_serializable`~~ **Done.** `harness/lib/schema/freezed_model.dart` uses
  `@freezed` with a `fromJson` factory delegating to `_$FreezedRecordFromJson`
  (json_serializable-generated), per the recommendation above.
- ~~Write the four hand-implementations of the Section 3 schema and get a smoke
  test passing~~ **Done.** `harness/lib/schema/{manual,json_serializable_model,
  freezed_model,built_value_model,serializers}.dart` implement path A-D;
  `harness/bin/smoke_test.dart` decodes one valid document through all four and
  confirms agreement (`dart run bin/smoke_test.dart`). Note one deliberate
  divergence already designed into path A vs. B/C for the `status` enum field:
  `ManualStatus.values.byName(...)` (path A) and json_serializable's default
  `$enumDecode` (path B, inherited by C) both throw on an unrecognized enum
  string, but as different raw exception types (`ArgumentError` vs.
  json_serializable's own error) — this is exactly the Tier B/C material RQ2
  is designed to surface once the generator starts producing unrecognized
  `status` strings; it has not been exercised yet since the smoke test only
  covers the happy path.

### Next up

- ~~Extend with hand-picked malformed documents to characterize exception
  types~~ **Done (2026-09-05).** `harness/bin/characterize_exceptions.dart`,
  13 hand-picked cases. Findings that reshape RQ2 and the Tier B/C design
  (Section 4/9 below) and must not be lost:

  1. **JSON syntax validity is a single shared gate, not a per-path one.**
     All four `fromJson`/`deserializeWith` entry points take an
     already-`jsonDecode`d Dart object, never raw text (this is also how
     real Flutter code is structured — you call `jsonDecode` once, then pass
     the result to whichever model class). Confirmed empirically: a
     syntactically invalid document (`{"id": 42, "amount": "19.99",}`) fails
     once, at `jsonDecode`, before any of the four paths run. **Consequence
     for the generator (Section 10, new)**: a byte-level/grammar-level
     mutator analogous to the original project's `near_valid_json` can only
     ever produce shared, uniform rejections here — it cannot find Tier C
     divergence by construction. Divergence-hunting needs a *schema-aware*
     generator that always emits syntactically valid JSON and perturbs
     values relative to the Section 3 schema (wrong types, missing fields,
     unrecognized enum strings, boundary numbers) instead.
  2. **A genuine, precisely-scoped Tier C divergence, found by hand on the
     first try**: given the schema's `tags` field missing entirely from the
     input, path D (`built_value`) silently accepts and defaults it to an
     empty list, while A/B/C all reject with a private `_TypeError`. This
     does **not** generalize to scalar required fields — missing `id`,
     `amount`, or `status` are correctly rejected by all four paths,
     including D (`DeserializationError: ... null for non-nullable field`).
     The finding is therefore specifically about **collection-typed**
     required fields under `built_value`'s builder-based construction, not
     laxness in general — this precision matters; overclaiming "built_value
     is lax" would not survive a fuzzing campaign the way the narrower,
     correct claim will.
  3. **A systematic, 100%-consistent exception-type pattern across every
     malformed-*type* case tested** (wrong-type `id`/`name`/`tags` element,
     null-for-non-nullable): paths A, B, and C surface Dart's private
     `_TypeError` (`type 'X' is not a subtype of type 'Y' in type cast`) —
     a class with a leading underscore, meaning it is not publicly
     importable/nameable and can only be caught via its public supertype
     `on TypeError catch (e)` or a blanket `catch (e)`, never by its own
     specific name. Path D wraps every such failure in its own public,
     documented `DeserializationError` instead. **Exception**: for the
     enum field specifically, B/C already throw a public `ArgumentError`
     rather than `_TypeError`, because json_serializable's generated code
     calls an explicit enum-decode helper with its own null/membership
     check for enums (but still falls through to a raw `as` cast, hence
     `_TypeError`, for plain scalar fields) — so "does codegen improve on
     manual's raw-cast contract" is answered per-field-type, not uniformly,
     and must be reported that way.

  These three findings, especially #3, are strong candidates for the
  paper's central RQ2 claim — but they rest on 13 hand-picked cases. The
  fuzzing campaign's job is to establish whether pattern #3 holds as
  systematically as it appears to, find any exceptions to it, and find
  further instances of pattern #2's shape (a documented failure contract on
  one path vs. silent defaulting on another) elsewhere in the schema.

- Design and implement the NDJSON batch harness (Section 6.2), refined per
  finding 1 above into an explicit two-stage design (Section 9, new): a
  single shared syntax/structure gate, then four independent schema-level
  attempts with a **catchability classifier** operationalizing finding 3 —
  "is this exception's concrete runtime type publicly nameable, or is it a
  leading-underscore private class forcing a catch-all?" — mechanically,
  not by a hand-maintained per-package documentation list.
- Only after the harness contract is real: port `_structure()`,
  `load_strategy()`, and the refinement loop from the original Python
  pipeline (reused unchanged per Section 6.3) and wire them to the compiled
  Dart executable in place of the cJSON binary — now targeting the
  schema-aware value generator (this section, item 1) rather than
  `json_strategy.py` directly for RQ2/RQ3.

## 9. Harness implementation, revised (supersedes Section 6.2's sketch)

Two stages per input, corresponding exactly to Section 8 finding 1:

1. **Structural gate** (shared across all four paths): base64-decode the
   input line, `utf8.decode(bytes, allowMalformed: false)`, then
   `jsonDecode(string)`. Any failure here (`FormatException` from either
   step) is recorded once as `status: structural_reject`, with no per-path
   breakdown — there is nothing to break down, all four paths would fail
   identically before ever running. If the decoded value is syntactically
   valid JSON but not an object (e.g. a bare array, number, or `null` at the
   top level — the grammar's `json : value EOF ;`, handoff Section 2.1,
   permits any value type there, not just objects), record
   `status: structural_valid_non_object` — distinct from `structural_reject`,
   since the bytes *were* valid JSON, there is simply no schema for a
   non-object to evaluate against. RQ1 (Section 1) counts this as accepted,
   matching cJSON's own grammar exactly; RQ2/RQ3 have no use for it since
   their oracle only exists at the schema stage.
2. **Schema stage** (only reached if stage 1 succeeds): run all four paths
   against the same decoded `Map`, each independently wrapped in
   `try { ... } on Object catch (e)`. For each path record either
   `{status: accepted, canonical: <Section 4.1 canonical value>}` or
   `{status: rejected, exception_type: e.runtimeType.toString(),
   is_private: <leading-underscore check>, message: e.toString()}`. Then
   compute, purely from these four records:
   - `tier_b_paths`: which paths (if any) rejected with a private
     (`is_private: true`) exception type.
   - `tier_c_divergence`: `none` if all four agree (all reject, or all
     accept with equal canonical values); `accept_reject` if acceptance
     status differs across paths; `value` if all accepted but canonical
     values differ.

A batch process outcome outside this per-line contract (nonzero exit,
killed by signal, or the timeout the driver wraps the whole invocation in)
is Tier A, exactly as in the original `runner.py` priority order, just
checked around the whole batch rather than around one input.

**Status (2026-09-05): implemented and verified.** `harness/lib/canonical.dart`
(canonicalization + hand-written deep-equality comparator, Section 4.1),
`harness/lib/oracle.dart` (the two-stage classifier above), and
`harness/bin/dart_json_harness.dart` (the NDJSON batch executable) are
written and compile clean (`dart analyze`). Compiled via `dart compile exe`
and smoke-tested with six hand-built NDJSON lines covering every branch
(valid, missing collection field, invalid JSON syntax, invalid UTF-8,
non-object top level, unrecognized enum value) — the harness's automated
classifier reproduces the manual findings from the "Next up" section above
exactly: `missing_tags` is correctly flagged `tier_b_paths: [A_manual,
B_json_serializable, C_freezed]` and `tier_c_divergence: "accept_reject"`,
with no hand-curation involved. This is the harness contract the refinement
loop will drive once ported (Section 10).

## 10. Schema-aware value generator (replaces `json_strategy.py` for RQ2/RQ3)

Per Section 8 finding 1, a byte/grammar-level mutator cannot find Tier C
divergence — it can only vary JSON *syntax*, which all four paths share a
single gate for. The generator that drives RQ2/RQ3 must instead always emit
syntactically valid JSON and vary *schema-level content*. Concretely, a
Hypothesis strategy (same `@st.composite def generated_json(draw) -> bytes`
contract as the original — Section 1.4 of the handoff, reused unchanged) built
in two layers:

1. **Base valid-record generator**: draws a value for each Section 3 field
   using its correct type (`id`: signed integer biased toward boundary
   magnitudes per Section 5.1; `amount`: exact decimal text, same bias;
   `name`: `None` or bounded Unicode text, including empty string and
   surrogate-adjacent codepoints; `status`: one of the three valid enum
   strings; `tags`: a bounded list of bounded strings; `child`: `None` or a
   recursive draw, depth-capped the same way the original `json_value`
   capped `max_leaves`), then serializes with `json.dumps` exactly as the
   original `baseline_json` did.
2. **Schema-perturbation layer**, applied probabilistically per field
   (mirroring `near_valid_json`'s role, but schema-aware): drop the field
   entirely (found the `tags`/`built_value` divergence by hand — this is the
   single highest-value perturbation to keep well-represented); replace its
   value with a wrong-but-JSON-valid type (string where int expected, number
   where string expected, object where list expected); set it to `null`
   regardless of nullability; for `status` specifically, substitute an
   arbitrary string not in the three valid values; inject extra,
   schema-unknown top-level keys; for `child`, force a deeper recursion chain
   than the base generator's normal cap, up to a separate, explicit hard
   limit (testing whether any path's recursive decode has a *different*
   effective depth limit than the others — an undiscovered Tier C variant
   the manual study didn't cover).

**Feedback fields fed back into the refinement prompt** (extending
`CampaignSummary`, Section 1.2/1.3 of the handoff, with new fields rather
than replacing the mechanism): for the RQ2 arm, replace acceptance-rate-style
metrics with counts of `tier_b_paths` occurrences (per path) and
`tier_c_divergence` (split `accept_reject` vs. `value`) over the campaign,
so the LLM is steered toward *finding more divergence*, not toward
acceptance rate (acceptance/rejection at the schema level is not the target
metric here — divergence and undocumented-exception exposure are). For the
RQ3 arm, use the Section 5.3 precision-loss-signature count exactly as
already specified. RQ1 keeps the original acceptance-rate metric unchanged,
since RQ1 deliberately reuses the original generator and objective as a
portability check.

**Status (2026-09-06): implemented and run for real (500 examples, no LLM
yet).** `src/agentic_fuzzing/dart_record_strategy.py` (the generator),
`dart_divergence_campaign.py` (RQ2's own `run_campaign`/`summarize_records`/
`build_refinement_prompt`/`run_refinement_loop`, parallel to but distinct
from RQ1's reused `refinement.py` since the metric is divergence, not
acceptance), and `scripts/run_dart_rq2_baseline.py` all exist and ran
end-to-end against the real compiled harness.

**A real bug was caught and fixed while wiring this up**, worth recording
because it could easily have been mistaken for the harness crashing: the
first run showed 30/500 examples as `harness_crash`. The actual cause was in
the *Python* batch client (`dart_runner.py`), not the harness: splitting the
harness's stdout with Python's `str.splitlines()` breaks on far more
characters than `\n` (U+2028, U+2029, U+000C, U+0085, ...), and those are
*legal, unescaped* characters inside a JSON string per the JSON spec (only
`"`, `\`, and ASCII control characters below 0x20 must be escaped) — the
generator's arbitrary Unicode text fields produced them, splitting single
response lines into garbage fragments and desynchronizing the
response-to-request correspondence for the rest of the batch. Fixed by
splitting strictly on the literal `\n` byte before decoding each line.
Re-run after the fix: 500/500 `schema_evaluated`, zero crashes — confirming
it was a client-side bookkeeping bug, not a Dart-level fault.

**Real results (500 examples, seed 0, static generator, no refinement)**:
`tier_b_counts: {A_manual: 300, B_json_serializable: 178, C_freezed: 178}` —
**`D_built_value` had zero private-exception rejections across all 500
examples**, confirming Section 8 finding 3 at scale, not just the original
13 hand-picked cases. `tier_c_accept_reject: 99` (19.8% of all generated
documents show cross-path accept/reject disagreement) with only 4 distinct
divergence patterns (`RRRR` 230, `AAAA` 171, `RAAR` 91, `RRRA` 8, in
`A_manual/B_json_serializable/C_freezed/D_built_value` order). Two of those
patterns are direct, large-sample confirmations of this document's two
headline findings, found with **no LLM refinement at all**:

- **`RAAR` (91/500 = 18.2%)** is Section 5.2's `id`-overflow finding:
  A (manual) and D (built_value) reject an out-of-range `id`, B
  (json_serializable) and C (freezed) silently accept via `.toInt()`
  saturation. Confirms the earlier single hand-picked probe holds at real
  frequency, not as a rare edge case — the shared `_id_strategy` used by
  both RQ2 and RQ3's generator finds it directly. This means **RQ2 and RQ3
  may not need materially separate campaigns**: RQ3's numeric analysis can
  largely be extracted from RQ2's own campaign data (every `schema_evaluated`
  record already carries each path's canonical `id`, which is enough to
  detect saturation) rather than requiring a second generator/harness/
  campaign pipeline — revisit this simplification before building RQ3's
  pipeline separately.
- **`RRRA` (8/500 = 1.6%)** is Section 8 finding 2: A/B/C reject a
  dropped/nulled `tags`, D silently defaults to `[]`. Lower rate than the
  `id` pattern because it requires the specific `tags`-drop perturbation,
  one path among several the perturbation layer picks uniformly at random —
  consistent with, not contradicting, the earlier characterization.

**Status (2026-09-06): first real LLM-driven run completed, one seed, real
`OPENAI_API_KEY` spend.** `scripts/run_dart_rq2_refinement.py` (adapted from
the original's `run_refinement.py`) ran 5 iterations x 500 examples against
`gpt-4.1-mini`, seed 0. Two proposal failures occurred and were handled
exactly as the original design specifies (logged, iteration slot consumed,
loop continued): iteration 1 of an earlier smoke test used `import json`
(fixed by making the prompt state explicitly that only
`from hypothesis import strategies as st` may be imported and JSON text must
be hand-built — the original project's own working LLM proposals do this via
string concatenation, confirmed by reading `artifacts/cjson-loop/iteration-1/
proposal.py` in the original repo); iteration 5 of the real run returned a
plain string instead of a `SearchStrategy` (ordinary LLM code-gen noise, not
a sandbox or prompt defect).

**A real, honest, notable finding — not spun positively**: across the four
iterations that did produce data, `tier_c_accept_reject` and `tier_c_value`
were **both zero every time**, despite `tier_b_counts` climbing sharply by
iteration 4 (A_manual 208, B/C ~201 each, out of 264 schema-evaluated
inputs) — i.e., refinement successfully drove up per-path rejection rates
but found **zero cross-path divergence**, worse than the static generator's
19.8% divergence rate in a single 500-example batch (this section, "Real
results" above). Plausible reason, not yet confirmed: the prompt's metrics
surface `tier_b_counts` and `tier_c_*` together with no relative emphasis,
so a proposer optimizing "make the numbers move" has no signal that
`tier_c_divergence` specifically (not `tier_b_counts`) is the actual
objective — mirroring almost exactly the concern the *original* paper's own
Discussion raised about acceptance-rate optimization crowding out
boundary-probing (handoff Section 6, gap 7), just manifesting on a different
metric here. **Confirmed with two more seeds (1 and 2), same unmodified prompt**: zero
`tier_c_divergence` across all 15 iterations that ran across all three seeds
combined (some iterations per seed failed proposal validation, as expected —
2/5 for seed 1, 2/5 for seed 2, ordinary code-gen noise, not systematic).
This is no longer attributable to single-run variance: three independent
seeds, fifteen iteration-campaigns, **zero** cross-path divergence found,
against the static generator's 19.8% in one 500-example batch. This is now
a confirmed, systematic finding, not noise — the current prompt reliably
fails at this specific objective even though it reliably drives up per-path
rejection counts. **Conclusion: the prompt needs revision** to isolate
`tier_c_divergence` as the explicit objective rather than presenting it
alongside `tier_b_counts` with no relative weighting — this is the next
concrete step (Section 8 "Next up"), to be evaluated on a fresh seed before
any further multi-seed spend, not layered on top of the current prompt.

**Fix validated (2026-09-06, seed 3, fresh/unused seed).**
`build_refinement_prompt` now states an explicit "YOUR SCORE" line
(`tier_c_accept_reject + tier_c_value`, out of total) ahead of the rest of
the metrics, explicitly says a high `tier_b_counts` alone is not the goal,
and adds a *methodological* hint (vary one or two things about an otherwise
valid document, rather than maximizing how broadly malformed a document
looks) deliberately worded to avoid naming the specific fields/outcomes
already found by hand, so any resulting discovery is the loop's own, not a
foregone conclusion planted in the prompt. Result: iteration 3 found 1/500,
iteration 4 found **59/500 (11.8%)**, iteration 5 found 23/500 (4.6%) —
a dramatic change from the prior confirmed 0/500 across three full seeds
with the unrevised prompt. Inspecting iteration 4's patterns: `RRRR` 219,
`RAAR` 59 (100% of the divergence found), `AAAA` 54 — the LLM's own
generated inputs independently rediscovered exactly the `id`-overflow
pattern (Section 5.2), via its own reasoning about "a value at a type
boundary," not by the hand-designed `_id_strategy`'s bias (this campaign
used a wholly LLM-authored generator, not `dart_record_strategy.py`) —
meaningful independent confirmation that the finding is robust to *how* the
boundary values get generated, not an artifact of one specific hand-written
generator. Not yet found: a genuinely *new* divergence pattern beyond the
two already known by hand — the next real test of this loop's value is
whether further iterations/seeds surface a pattern nobody found by hand.

**RQ3 analysis pass, run for real (2026-09-06), confirms the finding at
scale with a large N and no additional API spend.**
`scripts/analyze_rq3_precision.py` implements the Section 10 simplification
noted above: extract `id` ground truth from each record's own
`input_hex` (parsed with Python's exact-precision `int`, not `float`) and
compare against each path's canonical decoded `id`, across every
`schema_evaluated` record already collected from RQ2's baseline-n5 and
LLM-refined campaigns combined (7,458 candidate records). Result:

| path | accepted | mismatched | rate |
|---|---:|---:|---:|
| A_manual | 3,678 | 0 | 0.0% |
| B_json_serializable | 4,193 | 280 | 6.7% |
| C_freezed | 4,193 | 280 | 6.7% |
| D_built_value | 3,756 | 0 | 0.0% |

B and C's mismatch counts are identical (both 280/4193) — consistent with
freezed delegating `id` decoding to json_serializable's generated code
(Section 2, target-set rationale). A and D never silently mismatch: they
either decode `id` exactly or reject the input outright — confirmed at
n≈3,700-4,200 accepted cases per path, not just the single hand-picked probe.
Sampled mismatches generalize the earlier finding in a way the single probe
didn't show: saturation happens at **both** boundaries, not just the
positive one — e.g. `-9223372036854775810 -> -9223372036854775808` (exactly
`int64::MIN`), the mirror image of the original `int64::MAX` probe. This is
now a large-sample, quantified, reportable RQ3 result obtained entirely by
re-analyzing data already collected for RQ2 — no separate RQ3
generator/harness/campaign pipeline was needed, confirming the
simplification hypothesized above.

## 11. RQ2's headline statistical result (n=5 per arm, complete, 2026-09-06)

Budget-scoped to n=5 per arm (this session's `OPENAI_API_KEY` had a $3 hard
cap; see the cost/scope discussion this section's status notes are drawn
from) rather than the original paper's n=15 — reported honestly as a
smaller-sample design throughout, the same way the original project reported
its own n=5 feedback-mode ablation (handoff Section 3.5) as descriptive
relative to its n=15 headline result. `scripts/aggregate_rq2_runs.py`
computes, per run, the divergence rate two ways: over every generated
example, and over only the subset that reached the schema stage (isolating
targeting quality from JSON-syntax generation quality — this split mattered,
see below).

**Baseline arm** (`artifacts/repeated/rq2-baseline-n5`, static
`dart_record_strategy.generated_json`, seeds 0-4, 500 examples/run, no LLM):
divergence rate 19.8%, 21.8%, 22.2%, 23.4%, 23.8% — mean 22.2%, stdev 1.57.
Every run reached 500/500 `schema_evaluated` (the static generator always
emits syntactically valid JSON via `json.dumps`), so the two rate
definitions are identical for this arm.

**Refined arm** (`artifacts/repeated/rq2-loop-run01`, seeds 3-7 — the fixed
prompt from this section's earlier status note, 5 iterations x 500
examples/run, `gpt-4.1-mini`, real `OPENAI_API_KEY` spend): divergence rate
over all examples 5.53%, 1.3%, 1.45%, 2.75%, 3.6% — mean 2.93%, stdev 1.74;
over schema-evaluated examples only, 7.75%, 2.10%, 2.14%, 4.19%, 4.30% —
mean 4.10%, stdev 2.30. Both are far below the baseline's 22.2% on every
single run — complete separation in the **opposite direction** from the
original paper's cJSON headline result, where refinement beat the static
baseline. Exact two-sided Mann-Whitney U (`scipy.stats.mannwhitneyu(...,
method="exact")`, addressing handoff gap 8 directly instead of repeating the
original's hand-derived shortcut) on the over-total rates: **p ≈ 0.00794**
(matches the combinatorial `2/C(10,5)` check exactly). This is a genuine,
statistically rigorous result — reported honestly, not spun: **for this
objective, on this target, a simple static generator outperforms LLM-guided
refinement, even after the prompt was corrected to isolate the right metric.**

**Why, mechanistically — evidenced, not speculative.** The schema-evaluated
split shows refinement's shortfall is not fully explained by wasted budget
on syntactically invalid JSON (the sandbox forbids `import json`, forcing
the LLM to hand-roll JSON text — Section 8's earlier `import json` failure
and its fix): even conditioning on inputs that *did* reach the schema stage,
the refined arm's rate (mean 4.10%) is still roughly a fifth of the
baseline's (22.2%). Some of the gap is generation-quality overhead (refined
runs' `schema_evaluated` fraction of `total` ranged 41.9%-83.7% across runs,
vs. the baseline's fixed 100%), but the larger remaining gap is in
*targeting*: the static generator's perturbation catalog (Section 10 — field
drop, wrong-type substitution, null-for-non-nullable, boundary integers, all
applied independently and combinable) was hand-designed after studying which
perturbations actually cause divergence (Section 8's original 13-case
study); the LLM, given only a numeric score and a general methodological
hint deliberately worded not to name specific fields, had to rediscover
that catalog from scratch within a 5-iteration budget and did not fully
match it.

**No qualitatively new divergence pattern was found.** Pooling every
`schema_evaluated` record across all five fixed-prompt refined seeds:
`RRRR` 3689, `AAAA` 1292, `RAAR` 150, `RRRA` 66 — the same four patterns the
static baseline found, including both confirmed findings (`RAAR`, the
`id`-saturation pattern; `RRRA`, the `tags`/built_value pattern), just at
lower absolute counts. The refinement loop rediscovered known findings
independently (methodologically meaningful — Section 8's earlier note on
this) but did not surface anything beyond them in this budget.

**Framing for the paper**: this is a legitimate, itself-interesting result,
not a failure to hide. The original paper's RQ1 showed refinement helps when
the metric is acceptance rate against a single native parser; this result
shows the same mechanism does *not* straightforwardly transfer to a
differential, four-way divergence objective against Dart's codegen
frameworks, and offers a concrete, evidenced mechanistic account of why
(sandbox-driven generation overhead, plus a targeting gap versus a
hand-informed perturbation catalog) rather than an unexplained negative
result. This is worth reporting as directly as the original reported
parson's negative result, with the same discipline about not overclaiming
past what n=5 supports (handoff Section 5.1's rhetorical convention: every
quantitative claim paired with an explicit statement of its scope).

**Not yet done**: a larger-n confirmation of this result if `OPENAI_API_KEY`
budget is later increased; RQ1's own refined arm (not yet run at all); and
any exploration of prompt variants beyond the one fix already tested (e.g.,
explicitly giving the LLM more iterations, or feeding back which specific
perturbation *categories* produced this iteration's divergence, without
naming the exact fields already known) as a follow-up methodological
question, not a re-run of the same design hoping for a different result.

## 12. Ablation: is the RQ2 gap generation overhead or targeting? (resolved)

**Status (2026-09-06): resolved, decisively, at n=5.** Section 11 could
only partially separate two candidate explanations for RQ2's gap — sandbox-
driven generation overhead (the LLM can't `import json`, must hand-roll
JSON text, fails often) vs. a genuine targeting shortfall — via a
schema-evaluated-only rate, which still left a wide gap and couldn't fully
attribute it. `src/agentic_fuzzing/proposal_relaxed.py` is a deliberately
separate sandbox module (not a parameter on the original, unmodified
`proposal.py`) permitting `import json` in addition to
`hypothesis.strategies`; `dart_divergence_campaign.py` gained an
`allow_json` parameter threading through `build_refinement_prompt` and
`run_refinement_loop` (default `False`, so every existing script/result is
unaffected). Ran 5 fresh seeds (100-104, disjoint from every other run) at
5×500 under this relaxed sandbox: every iteration that produced data
reached at or near 100% `schema_evaluated` (generation overhead
essentially eliminated, exactly as predicted), but the divergence rate was
**2.20% mean** (stdev 1.42) — statistically indistinguishable from the
constrained sandbox's 2.93% (exact two-sided Mann-Whitney U, `p ≈ 0.69`)
and still in complete separation below the static baseline's 22.2%
(`p ≈ 0.00794`). **Conclusion: the RQ2 gap is not generation overhead at
all — it is entirely a targeting problem.** This is a materially stronger,
more precise finding than Section 11's original hedge, and it directly
sharpens Section 8's "Next up" prompt-design suggestion (feeding back
perturbation *categories*, not specific fields) as the one remaining lever
actually worth trying, since making LLM-generated JSON more reliably
well-formed has now been ruled out as a path to closing the gap.

This result, its table, and the corresponding paper text (abstract,
introduction contributions list, Methodology §J, a new Evaluation §C,
Discussion §A rewritten, Conclusion) are already integrated into
`paper/main.tex` and compiled cleanly (`tectonic main.tex`, 9 pages, zero
errors).

## 13. Free RQ3 strengthening: recursive depth extraction (no cost)

**Status (2026-09-06): done.** `scripts/analyze_rq3_precision.py` originally
only checked the top-level `id`. Since the schema is recursive and an
accepting path's canonical value mirrors the whole decoded tree, every
nesting depth already present in collected data is another free `id`
check — extended the script to walk `child` in lockstep on both the
ground-truth and canonical sides. Re-run over every RQ2 campaign (baseline
+ constrained-refined + json-allowed ablation, pooled): **N rose from 7,458
to 43,336 checks**. A_manual and D_built_value remain at exactly 0.0%
mismatch; B_json_serializable/C_freezed at 5.7% (was 6.7% on the smaller,
narrower pool — a fair, expected shift from broadening the sample, not a
contradiction). New, real, and reported descriptively in the paper: the
mismatch rate for B/C rises with nesting depth (3.4% at depth 0 → 7.7% →
20.7% → 21.2% at depth 3, N thinning sharply past that to single digits).
No confirmed mechanism for the depth correlation — flagged honestly as
untested in the paper rather than overclaimed.

## 14. Follow-up: perturbation-category feedback (tested, negative result)

**Status (2026-09-06): done, real API spend, genuinely surprising
result.** Direct follow-up to Section 12's ablation: having established the
RQ2 gap is a targeting problem, does feeding the proposer *categories* of
perturbation (not just a score) help it target better? Implementation:
`_classify_perturbations()` in `dart_divergence_campaign.py` inspects any
generated document's shape against the schema (missing_field,
null_override, wrong_type, bad_enum, boundary_id, extra_key, deep_nesting)
— fully generator-agnostic, since the LLM's own generator source can't be
introspected. `DivergenceCampaignSummary` gained a
`divergence_perturbation_categories: Counter` field; `build_refinement_prompt`
gained `category_feedback: bool` (default `False`, existing prompt/behavior
untouched) that swaps in a category-count strategy hint in place of the
generic one, still without naming specific fields (same discipline as
Section 8's original score-based fix). CLI: `--category-feedback` on
`run_dart_rq2_refinement.py`.

Ran n=5 fresh seeds (200-204): mean divergence rate **0.95%** — not just
"no better" than the score-only prompt's 2.93%, but *significantly worse*
(exact two-sided Mann-Whitney U, p≈0.032, holding both overall and
restricted to schema-evaluated-only records, ruling out proposal-failure
noise as the explanation). Two of five seeds found literally zero
divergence in their only successfully-validated iteration — a real
observation of the prompt's own quality, not an artifact of failed
proposals. No confirmed mechanism; plausible-but-untested reading in the
paper: a longer prompt enumerating 7 named categories may compete for the
proposer's attention or invite more elaborate, more bug-prone generator
code. This is genuinely valuable, counter-intuitive material: it rules out
the most obvious next fix, sharpening future work toward structural changes
(e.g., letting the loop retain/mutate prior generator source instead of
rewriting from scratch each iteration, which the reused-unmodified
`run_refinement_loop` currently never does) rather than more descriptive
prompting.

Fully integrated into `paper/main.tex`: Abstract, Introduction (new
contribution bullet), Methodology §K, new Evaluation §D + Table IV,
Discussion §A extended, Future Work rewritten, Conclusion updated.
Compiled clean, 9 pages. Estimated additional spend for this experiment:
~25 API calls ≈ $0.34.

## 15. Side study: does `freezed` ever diverge from `json_serializable`?

**Status (2026-09-06): done, qualitative, no LLM/API cost.** Addresses the
construct-validity gap flagged in prior sections: `freezed` and
`json_serializable` are identical in every Record-schema result reported
anywhere in this project, since freezed delegates every field's leaf
decoding to json_serializable's generated code — the schema never
exercises freezed's own signature feature (native discriminated-union JSON
dispatch). Rather than retrofitting a union field into the validated
Record schema/pipeline (real risk of destabilizing everything else), built
a completely separate, additive side study:

- New schema: `Payload.text(String) | Payload.number(num)`, discriminated
  by a `"type"` key, implemented once per path following each framework's
  own idiomatic real-world pattern: `harness/lib/schema/union_manual.dart`
  (if/else dispatch), `union_json_serializable.dart` (hand-written dispatch
  + `@JsonSerializable()` leaf classes — json_serializable has no native
  polymorphism), `union_freezed.dart` (`@Freezed(unionKey: 'type')` +
  `@FreezedUnionValue`, freezed's own native mechanism, confirmed exact
  API via a live pub.dev fetch before writing any code), `union_built_value.dart`
  + `union_built_value_dispatch.dart` + `union_serializers.dart` (hand-written
  dispatch + custom serializers per leaf, split into 3 files specifically
  to avoid a circular import between the Built classes and the
  `Serializers` registry that references them).
- `bin/union_smoke_test.dart`: all four paths agree on both valid variants
  (verified before anything else).
- `bin/union_characterize_exceptions.dart`: 13 hand-picked documents
  (mirroring the exact discipline of the original main-schema
  `characterize_exceptions.dart`).

**The finding**: freezed finally diverges from json_serializable — at the
**exception-type** level, not accept/reject or value. Every
invalid-discriminant case (unknown/missing/null/wrong-type/differently-cased)
is rejected by all four, but freezed raises the public, structured
`CheckedFromJsonException` (from `json_annotation`'s checked-decoding
support) while manual/json_serializable/built_value all raise a generic
`ArgumentError` — the first behavioral difference of any kind ever observed
between B and C in this entire project. For wrong-type/missing leaf-*value*
cases (valid discriminant), all four converge back to the familiar main-
schema pattern (A/B/C private `_TypeError`, D its own `DeserializationError`)
with no B-vs-C difference. No accept/reject divergence or value divergence
observed in this small sample — expected, since deterministic discriminant
dispatch gives no natural source of same-input-different-value decoding
without a more ambiguous union shape.

**Deliberately not done**: this is explicitly a smaller, qualitative
side study (13 hand-picked cases), not run through the automated
oracle/generator/harness/campaign pipeline or given a statistical
treatment — building that (a Payload-shaped generator, a dedicated harness
endpoint, a seeded baseline-vs-refined comparison) is real, scoped future
work, not attempted here, and the paper says so explicitly rather than
overclaiming quantitative rigor for a 13-case qualitative probe.

Fully integrated into `paper/main.tex`: new Evaluation §F
(`sec:evaluation-union`), Future Work's third item rewritten to describe
what was actually found and what remains. Compiled clean. No new API
spend — pure Dart engineering + `dart run` (free).

