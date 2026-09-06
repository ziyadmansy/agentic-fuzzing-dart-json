#!/usr/bin/env python3
"""RQ3 analysis pass (docs/dart-oracle-design.md Section 10 simplification
note): extracts `id`-field round-trip correctness from *existing* RQ2
campaign data rather than requiring a separate generator/harness/campaign
pipeline. Every `schema_evaluated` record already carries the ground-truth
input (`input_hex`) and each path's canonical decoded value, so precision
loss is a comparison, not a new experiment.

Ground truth for `id` is the exact Python `int` parsed from the original
generated JSON text (Python's `json.loads`/`int` are exact-precision, no
`float` detour -- same reasoning as docs/dart-oracle-design.md Section 5.1).
A path's decoded `id` is read from its own canonical value in the harness's
response. A mismatch is precision loss for that path on that input,
independent of whether the two disagree with each other (that's Tier C,
already counted) -- this counts each path against ground truth instead.

**Extended (2026-09-06)**: the schema is recursive (`child`, `child.child`,
...), and an "accepted" path's canonical value mirrors the full decoded
tree, not just the top-level fields -- so every nesting depth present in
already-collected data is another free, independent `id` check, walked in
lockstep with the same-shaped ground-truth tree. This costs no new
generation or API spend and simply extracts more of what campaigns already
produced; results are broken out by depth to check the pattern holds
uniformly rather than being a top-level-only artifact.
"""

import argparse
import json
from pathlib import Path
from typing import Iterator

_PATH_ORDER = ("A_manual", "B_json_serializable", "C_freezed", "D_built_value")


def _iter_records(paths: list[Path]) -> Iterator[dict]:
    for path in paths:
        if path.is_dir():
            yield from _iter_records(sorted(path.rglob("results.jsonl")))
            continue
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    yield json.loads(line)


def _walk_id_checks(original: object, canonical: object, depth: int = 0):
    """Yield (depth, ground_truth_id) for every level of a record tree where
    ground truth has a well-typed integer `id`, following `child` into both
    trees in lockstep. `canonical` may be `None`/malformed if the path
    diverged structurally -- in that case there is nothing further to check
    on this branch, so recursion simply stops rather than raising."""
    if not isinstance(original, dict) or not isinstance(original.get("id"), int):
        return
    yield depth, original["id"], canonical if isinstance(canonical, dict) else None
    child_original = original.get("child")
    child_canonical = canonical.get("child") if isinstance(canonical, dict) else None
    if isinstance(child_original, dict):
        yield from _walk_id_checks(child_original, child_canonical, depth + 1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path, help="results.jsonl files or directories to search recursively")
    args = parser.parse_args()

    per_path_accepted: dict[str, int] = {name: 0 for name in _PATH_ORDER}
    per_path_mismatch: dict[str, int] = {name: 0 for name in _PATH_ORDER}
    per_depth_accepted: dict[int, int] = {}
    per_depth_mismatch: dict[int, int] = {}
    mismatch_examples: dict[str, list[tuple[int, int]]] = {name: [] for name in _PATH_ORDER}
    total_checks = 0

    for record in _iter_records(args.paths):
        response = record.get("harness_response")
        if not response or response.get("status") != "schema_evaluated":
            continue
        input_hex = record.get("input_hex")
        if not input_hex:
            continue
        try:
            original = json.loads(bytes.fromhex(input_hex).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            continue
        if not isinstance(original, dict):
            continue

        by_path = {p["path"]: p for p in response["paths"]}
        for name in _PATH_ORDER:
            path_result = by_path.get(name)
            if path_result is None or path_result["status"] != "accepted":
                continue
            for depth, ground_truth_id, canonical in _walk_id_checks(original, path_result["canonical"]):
                if canonical is None:
                    continue
                total_checks += 1
                per_path_accepted[name] += 1
                per_depth_accepted[depth] = per_depth_accepted.get(depth, 0) + 1
                decoded_id = canonical.get("id")
                if decoded_id != ground_truth_id:
                    per_path_mismatch[name] += 1
                    per_depth_mismatch[depth] = per_depth_mismatch.get(depth, 0) + 1
                    if len(mismatch_examples[name]) < 3:
                        mismatch_examples[name].append((ground_truth_id, decoded_id))

    print(f"Total (path, depth) id checks across all accepted decodes: {total_checks}\n")
    print(f"{'path':<22} {'accepted':>10} {'mismatched':>12} {'mismatch rate':>15}")
    for name in _PATH_ORDER:
        accepted = per_path_accepted[name]
        mismatched = per_path_mismatch[name]
        rate = f"{100 * mismatched / accepted:.1f}%" if accepted else "n/a"
        print(f"{name:<22} {accepted:>10} {mismatched:>12} {rate:>15}")

    print(f"\n{'depth':<8} {'accepted':>10} {'mismatched':>12} {'mismatch rate':>15}")
    for depth in sorted(per_depth_accepted):
        accepted = per_depth_accepted[depth]
        mismatched = per_depth_mismatch.get(depth, 0)
        rate = f"{100 * mismatched / accepted:.1f}%" if accepted else "n/a"
        print(f"{depth:<8} {accepted:>10} {mismatched:>12} {rate:>15}")

    print()
    for name in _PATH_ORDER:
        if mismatch_examples[name]:
            print(f"{name} example mismatches (ground_truth -> decoded):")
            for truth, decoded in mismatch_examples[name]:
                print(f"  {truth} -> {decoded}")


if __name__ == "__main__":
    main()
