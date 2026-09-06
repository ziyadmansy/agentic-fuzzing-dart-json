#!/usr/bin/env python3
"""Run the real LLM-driven RQ2 divergence-hunting refinement loop against the
compiled Dart harness, once or repeatedly. Adapted from the original
project's `scripts/run_refinement.py`: same CLI shape and manifest/report
plumbing, but drives `dart_divergence_campaign.run_refinement_loop` (no
grammar file or feedback-mode ablation -- RQ2 has its own fixed prompt,
docs/dart-oracle-design.md Section 10) instead of the original's
grammar-based, feedback-mode-ablated loop.
"""

import argparse
import os
from pathlib import Path
from typing import Any

from openai import OpenAI

from agentic_fuzzing.dart_divergence_campaign import run_refinement_loop
from agentic_fuzzing.dart_reproducibility import build_report, write_report
from agentic_fuzzing.experiment import run_directory, write_summary
from agentic_fuzzing.llm import OpenAIProposer
from agentic_fuzzing.seeding import build_manifest, resolved_arguments, seed_everything, write_manifest

REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the RQ2 LLM-driven divergence-hunting refinement loop")
    parser.add_argument("--executable", default=str(REPO_ROOT / "build" / "dart_json_harness"))
    parser.add_argument("--artifact-dir", type=Path, default=Path("artifacts/repeated/rq2-loop"))
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--examples", type=int, default=500)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--model", default="gpt-4.1-mini")
    parser.add_argument("--seed", type=int, default=0, help="seed of the first run; run N uses seed+N-1")
    parser.add_argument("--runs", type=int, default=1, help="number of independent repeated runs")
    parser.add_argument("--overwrite", action="store_true", help="allow writing into a non-empty run directory")
    parser.add_argument(
        "--allow-json",
        action="store_true",
        help="ablation (paper Future Work item 1): also permit `import json` in the sandbox",
    )
    parser.add_argument(
        "--category-feedback",
        action="store_true",
        help="follow-up (paper Future Work): feed back divergence perturbation categories, not just a score",
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
        manifest = build_manifest(seed, arguments, model=args.model)
        first_manifest = first_manifest or manifest
        write_manifest(run_dir / "manifest.json", manifest)

        seed_everything(seed)
        print(f"== {run_dir} (seed={seed})")
        summaries = run_refinement_loop(
            args.executable,
            proposer,
            run_dir,
            iterations=args.iterations,
            examples_per_iteration=args.examples,
            timeout_seconds=args.timeout,
            allow_json=args.allow_json,
            category_feedback=args.category_feedback,
        )
        for index, summary in enumerate(summaries, start=1):
            print(f"iteration-{index}: {summary.as_dict()}")
            write_summary(run_dir / f"iteration-{index}", summary.as_dict())

    if first_manifest is not None:
        if args.allow_json:
            experiment_type = "rq2_refined_json_allowed"
        elif args.category_feedback:
            experiment_type = "rq2_refined_category_feedback"
        else:
            experiment_type = "rq2_refined"
        report = build_report(
            first_manifest,
            experiment_type=experiment_type,
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
