"""RQ1 campaign runner (docs/dart-oracle-design.md Section 1, RQ1 and Section
9's "Status" note). Classifies each generated input purely on whether it
passed the harness's shared *structural* gate -- i.e. whether
`dart:convert`'s `jsonDecode` accepted it as syntactically valid JSON. That
gate is the Dart analogue of cJSON's own accept/reject entry point (handoff
Section 1.6): RQ1 is a portability check for the refinement-loop *pipeline*,
reusing the original grammar-only generator (`json_strategy.py`) unmodified,
not a schema-level oracle -- the four-path divergence machinery (Tier B/C/D)
is RQ2/RQ3's job, driven by a different, schema-aware generator.

`run_campaign` matches the original project's exact signature
(`executable, inputs, output_path, max_examples, timeout_seconds`) so
`agentic_fuzzing.refinement`'s `CampaignSummary`, `build_refinement_prompt`,
and `run_refinement_loop` are reused with zero changes to their logic -- the
only edit anywhere in that file is which module `run_campaign` is imported
from. Everything below this docstring differs from the original because the
original's per-input subprocess model does not apply to a batch harness.
"""

from collections import Counter
import json
from pathlib import Path
from typing import Iterable

from .dart_runner import HarnessBatchResult, run_batch
from .proposal import GenerationError


def run_campaign(
    executable: str,
    inputs: Iterable[bytes | GenerationError],
    output_path: Path,
    max_examples: int = 500,
    timeout_seconds: float = 5.0,
) -> Counter[str]:
    """Run at most ``max_examples`` inputs through one harness invocation and
    persist every result as one JSON line, in the original project's exact
    record shape, so `refinement.summarize_records` needs no changes.

    ``timeout_seconds`` keeps the original signature's *per-input* meaning;
    since one harness process now serves the whole campaign rather than one
    process per input, it is scaled into a total batch timeout here (with a
    30s floor for small batches where per-input products round to near zero).
    """
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
                # a single bad Hypothesis draw must not abort the rest of the
                # campaign -- log it and keep going (matches the original).
                counts["encoding_error"] += 1
                output.write(json.dumps(_generation_error_observation(index, item)) + "\n")
                continue

            response = next(response_iter, None)
            if response is None:
                # the batch process died/timed out before reaching this input
                # -- this project's Tier A (docs/dart-oracle-design.md Section 9)
                status = "harness_timeout" if batch.timed_out else "harness_crash"
                counts[status] += 1
                output.write(
                    json.dumps(_harness_failure_observation(index, item, status, batch.returncode))
                    + "\n"
                )
                continue

            # RQ1's "accepted" matches cJSON's own grammar (handoff Section 2.1:
            # `json : value EOF ;`, any value type) -- both a fully schema-evaluated
            # object and a syntactically valid non-object top-level value count.
            status = (
                "accepted"
                if response.get("status") in ("schema_evaluated", "structural_valid_non_object")
                else "rejected"
            )
            counts[status] += 1
            output.write(json.dumps(_observation(index, item, status, response)) + "\n")
    return counts


def _observation(index: int, data: bytes, status: str, response: dict) -> dict[str, object]:
    return {
        "index": index,
        "input_hex": data.hex(),
        "input_length": len(data),
        "status": status,
        "returncode": None,
        "stdout": json.dumps(response),
        "stderr": "",
        "rejection_signature": response.get("reason") if status == "rejected" else None,
        "sanitizer_signature": None,
        "crash_id": None,
        "structure": _structure(data),
    }


def _harness_failure_observation(
    index: int, data: bytes, status: str, returncode: int | None
) -> dict[str, object]:
    return {
        "index": index,
        "input_hex": data.hex(),
        "input_length": len(data),
        "status": status,
        "returncode": returncode,
        "stdout": "",
        "stderr": "",
        "rejection_signature": None,
        "sanitizer_signature": None,
        "crash_id": None,
        "structure": _structure(data),
    }


def _generation_error_observation(index: int, error: GenerationError) -> dict[str, object]:
    return {
        "index": index,
        "input_hex": "",
        "input_length": 0,
        "status": "encoding_error",
        "returncode": None,
        "stdout": "",
        "stderr": "",
        "rejection_signature": None,
        "sanitizer_signature": None,
        "crash_id": None,
        "structure": "",
        "generation_error": error.error,
    }


def _structure(data: bytes) -> str:
    """Verbatim from the original project's `campaign.py` -- format-only, not
    C/cJSON-specific, so it transfers unchanged (docs/dart-oracle-design.md
    Section 9's "Status" note)."""
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
