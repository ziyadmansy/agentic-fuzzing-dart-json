#!/usr/bin/env python3
"""Aggregate RQ2 run directories (docs/dart-oracle-design.md Section 10) into
one row per run, mirroring the original project's `aggregate_runs.py`
convention: sum across a run's iterations (excluding iterations where the
proposal itself failed validation -- they contribute no campaign
observations, matching `iterations_with_data` in the original), then compute
two divergence rates per run: over *all* generated examples, and over only
the subset that reached the schema stage (`schema_evaluated`) -- the second
isolates targeting quality from JSON-syntax generation quality, which turned
out to matter a lot once real refined-arm data existed (see the design doc's
RQ2 status notes).
"""

import argparse
import json
import statistics
from pathlib import Path


def iteration_dirs(run_dir: Path) -> list[Path]:
    return sorted(
        (p for p in run_dir.iterdir() if p.is_dir() and p.name.startswith("iteration-")),
        key=lambda p: int(p.name.split("-")[1]),
    )


def collect_run(run_dir: Path) -> dict:
    total = 0
    schema_evaluated = 0
    tier_c = 0
    iterations_with_data = 0
    iterations_rejected = 0
    for iteration_dir in iteration_dirs(run_dir):
        summary_path = iteration_dir / "summary.json"
        if not summary_path.is_file():
            continue
        summary = json.loads(summary_path.read_text())
        counts = summary.get("top_level_counts", {})
        if "proposal_rejected" in counts:
            iterations_rejected += 1
            continue
        iterations_with_data += 1
        total += int(summary["total"])
        schema_evaluated += int(counts.get("schema_evaluated", 0))
        tier_c += int(summary["tier_c_accept_reject"]) + int(summary["tier_c_value"])
    return {
        "run": run_dir.name,
        "iterations_with_data": iterations_with_data,
        "iterations_rejected": iterations_rejected,
        "total": total,
        "schema_evaluated": schema_evaluated,
        "tier_c": tier_c,
        "divergence_rate_over_total": (100.0 * tier_c / total) if total else None,
        "divergence_rate_over_schema_evaluated": (100.0 * tier_c / schema_evaluated) if schema_evaluated else None,
    }


def collect_runs(artifact_dir: Path, min_seed: int | None = None) -> list[dict]:
    rows = []
    for run_dir in sorted(p for p in artifact_dir.iterdir() if p.is_dir() and p.name.startswith("run-")):
        if min_seed is not None:
            manifest_path = run_dir / "manifest.json"
            if not manifest_path.is_file():
                continue
            seed = json.loads(manifest_path.read_text()).get("seed")
            if seed is None or seed < min_seed:
                continue
        rows.append(collect_run(run_dir))
    return rows


def summarize(rows: list[dict], field: str) -> None:
    values = [row[field] for row in rows if row[field] is not None]
    if not values:
        print(f"{field}: no usable runs")
        return
    mean = statistics.mean(values)
    stdev = statistics.stdev(values) if len(values) > 1 else 0.0
    print(f"{field}: n={len(values)} mean={mean:.2f} stdev={stdev:.2f} values={[round(v, 2) for v in values]}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact_dir", type=Path)
    parser.add_argument(
        "--min-seed",
        type=int,
        default=None,
        help="only include runs whose manifest seed is >= this (e.g. to exclude pre-prompt-fix seeds)",
    )
    args = parser.parse_args()

    rows = collect_runs(args.artifact_dir, args.min_seed)
    for row in rows:
        print(row)
    print()
    summarize(rows, "divergence_rate_over_total")
    summarize(rows, "divergence_rate_over_schema_evaluated")


if __name__ == "__main__":
    main()
