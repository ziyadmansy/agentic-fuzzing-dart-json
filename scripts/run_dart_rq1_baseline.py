#!/usr/bin/env python3
"""RQ1 grammar-only baseline campaigns (docs/dart-oracle-design.md Section 1,
RQ1): the same pipeline as the refinement loop with no LLM and no refinement,
so the two are directly comparable. Adapted from the original project's
`scripts/run_baseline.py` -- the only changes are the imports (`dart_campaign`
instead of `campaign`, `dart_reproducibility` instead of `reproducibility`)
and the default `--executable` path; the CLI shape, run-directory layout, and
manifest/report writing are unchanged.

`--artifact-dir` writes the run-NN-seed-SSSS/iteration-1/ layout the refined
experiments use. A baseline run has exactly one iteration because there is
nothing to refine.
"""

import argparse
import json
from pathlib import Path
from typing import Any

from agentic_fuzzing.dart_campaign import run_campaign
from agentic_fuzzing.experiment import run_directory, write_summary
from agentic_fuzzing.json_strategy import baseline_json, near_valid_json
from agentic_fuzzing.refinement import summarize_records
from agentic_fuzzing.dart_reproducibility import build_report, write_report
from agentic_fuzzing.seeding import build_manifest, resolved_arguments, seed_everything, write_manifest

REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the RQ1 bounded JSON baseline campaign")
    parser.add_argument("--executable", default=str(REPO_ROOT / "build" / "dart_json_harness"))
    parser.add_argument("--examples", type=int, default=50, help="refined runs use 500 per iteration")
    parser.add_argument("--timeout", type=float, default=5.0, help="per-input budget; see dart_campaign.run_campaign")
    parser.add_argument("--output", type=Path, default=Path("artifacts/rq1_baseline.jsonl"))
    parser.add_argument("--seed", type=int, default=0, help="seed of the first run; run N uses seed+N-1")
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help="write run-NN-seed-SSSS/iteration-1/ runs here instead of a single --output file",
    )
    parser.add_argument("--runs", type=int, default=1, help="repeated runs; requires --artifact-dir")
    parser.add_argument("--overwrite", action="store_true", help="allow writing into a non-empty run directory")
    args = parser.parse_args()

    if args.runs < 1:
        raise SystemExit("--runs must be at least 1")
    if args.runs > 1 and args.artifact_dir is None:
        raise SystemExit("--runs requires --artifact-dir")

    def input_stream():
        for index in range(args.examples):
            strategy = baseline_json() if index % 2 == 0 else near_valid_json()
            yield strategy.example()

    if args.artifact_dir is None:
        seed_everything(args.seed)
        counts = run_campaign(args.executable, input_stream(), args.output, args.examples, args.timeout)
        manifest = build_manifest(args.seed, resolved_arguments(args))
        manifest_path = write_manifest(args.output.with_suffix(".manifest.json"), manifest)
        report_paths = write_report(
            args.output.parent,
            _report(manifest, args, runs=1),
            stem=f"{args.output.stem}.reproducibility",
        )
        print(dict(counts))
        for path in (manifest_path, *report_paths):
            print(path)
        return

    arguments = resolved_arguments(args)
    first_manifest: dict[str, Any] | None = None
    for run_index in range(args.runs):
        seed = args.seed + run_index
        try:
            run_dir = run_directory(args.artifact_dir, run_index, seed, args.overwrite)
        except FileExistsError as error:
            raise SystemExit(str(error)) from error
        iteration_dir = run_dir / "iteration-1"
        iteration_dir.mkdir(parents=True, exist_ok=True)
        manifest = build_manifest(seed, arguments)
        first_manifest = first_manifest or manifest
        write_manifest(run_dir / "manifest.json", manifest)

        seed_everything(seed)
        print(f"== {run_dir} (seed={seed})")
        result_path = iteration_dir / "results.jsonl"
        run_campaign(args.executable, input_stream(), result_path, args.examples, args.timeout)
        with result_path.open(encoding="utf-8") as result_file:
            summary = summarize_records(json.loads(line) for line in result_file)
        write_summary(iteration_dir, summary.as_dict())
        print(f"iteration-1: {summary.as_dict()}")

    if first_manifest is not None:
        for path in write_report(args.artifact_dir, _report(first_manifest, args, runs=args.runs)):
            print(path)


def _report(manifest: dict[str, Any], args: argparse.Namespace, runs: int) -> dict[str, Any]:
    return build_report(
        manifest,
        experiment_type="rq1_baseline",
        executable=args.executable,
        runs=runs,
        examples_per_run=args.examples,
        max_refinement_iterations=None,
        repo_root=REPO_ROOT,
        harness_dir=REPO_ROOT / "harness",
    )


if __name__ == "__main__":
    main()
