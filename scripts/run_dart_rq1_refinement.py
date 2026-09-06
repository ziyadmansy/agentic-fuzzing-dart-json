#!/usr/bin/env python3
"""Run the real LLM-driven RQ1 refinement loop against the compiled Dart
harness, once or repeatedly. Adapted from the original project's
`scripts/run_refinement.py` -- CLI shape, manifest/report plumbing, and the
reused (unedited-in-logic) `refinement.run_refinement_loop` are identical;
only the executable default, `dart_reproducibility` import, and grammar path
default point at this project's files.
"""

import argparse
import os
from pathlib import Path
from typing import Any

from openai import OpenAI

from agentic_fuzzing.dart_reproducibility import build_report, write_report
from agentic_fuzzing.experiment import run_directory, write_summary
from agentic_fuzzing.llm import OpenAIProposer
from agentic_fuzzing.refinement import DEFAULT_FEEDBACK_MODE, FEEDBACK_MODES, run_refinement_loop
from agentic_fuzzing.seeding import build_manifest, resolved_arguments, seed_everything, write_manifest

REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the RQ1 Dart-targeted agentic refinement loop")
    parser.add_argument("--executable", default=str(REPO_ROOT / "build" / "dart_json_harness"))
    parser.add_argument("--grammar", type=Path, default=REPO_ROOT / "grammar" / "JSON.g4")
    parser.add_argument("--artifact-dir", type=Path, default=Path("artifacts/repeated/rq1-loop"))
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--examples", type=int, default=500)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--model", default="gpt-4.1-mini")
    parser.add_argument("--seed", type=int, default=0, help="seed of the first run; run N uses seed+N-1")
    parser.add_argument("--runs", type=int, default=1, help="number of independent repeated runs")
    parser.add_argument("--overwrite", action="store_true", help="allow writing into a non-empty run directory")
    parser.add_argument(
        "--feedback",
        choices=sorted(FEEDBACK_MODES),
        default=DEFAULT_FEEDBACK_MODE,
        help="parser-feedback ablation: which campaign metrics the prompt exposes",
    )
    args = parser.parse_args()

    if args.runs < 1:
        raise SystemExit("--runs must be at least 1")

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY environment variable is not set")

    client = OpenAI(api_key=api_key)
    proposer = OpenAIProposer(client, model=args.model)
    arguments = resolved_arguments(args)
    first_manifest: dict[str, Any] | None = None

    for run_index in range(args.runs):
        seed = args.seed + run_index
        try:
            run_dir = run_directory(args.artifact_dir, run_index, seed, args.overwrite)
        except FileExistsError as error:
            raise SystemExit(str(error)) from error
        manifest = build_manifest(seed, arguments, model=args.model, feedback_mode=args.feedback)
        first_manifest = first_manifest or manifest
        write_manifest(run_dir / "manifest.json", manifest)

        seed_everything(seed)
        print(f"== {run_dir} (seed={seed})")
        summaries = run_refinement_loop(
            args.executable,
            args.grammar,
            proposer,
            run_dir,
            iterations=args.iterations,
            examples_per_iteration=args.examples,
            timeout_seconds=args.timeout,
            feedback_mode=args.feedback,
        )
        for index, summary in enumerate(summaries, start=1):
            print(f"iteration-{index}: {summary.as_dict()}")
            write_summary(run_dir / f"iteration-{index}", summary.as_dict())

    if first_manifest is not None:
        report = build_report(
            first_manifest,
            experiment_type="rq1_refined",
            executable=args.executable,
            runs=args.runs,
            examples_per_run=args.examples,
            max_refinement_iterations=min(args.iterations, 5),
            repo_root=REPO_ROOT,
            harness_dir=REPO_ROOT / "harness",
        )
        for path in write_report(args.artifact_dir, report):
            print(path)


if __name__ == "__main__":
    main()
