"""Environment provenance for a completed experiment, adapted from the
original project's `reproducibility.py`. The generic parts (manifest merging,
git lookups, markdown rendering, degrade-to-"unknown" discipline) are reused
verbatim in spirit; `_parser_identity`/`_harness_facts` are rewritten because
this project's harness is one binary containing four independent
dependency-pinned targets (docs/dart-oracle-design.md Section 2), not a
single vendored C library with ASan/UBSan markers to detect.
"""

import hashlib
import json
from pathlib import Path
import platform
import re
import shlex
import subprocess
import sys
from typing import Any

UNKNOWN = "unknown"

# The four paths this experiment targets (docs/dart-oracle-design.md Section 2)
# and the pubspec.lock package names whose pinned versions identify them.
_TARGET_PACKAGES = {
    "A_manual": None,  # dart:convert (SDK), not a pub.dev package
    "B_json_serializable": "json_serializable",
    "C_freezed": "freezed",
    "D_built_value": "built_value",
}


def _git(repo: Path, *arguments: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo), *arguments],
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return UNKNOWN
    if completed.returncode != 0:
        return UNKNOWN
    return completed.stdout.decode("utf-8", errors="replace").strip() or UNKNOWN


def _dart_sdk_version() -> str:
    try:
        completed = subprocess.run(
            ["dart", "--version"], capture_output=True, timeout=10, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return UNKNOWN
    text = (completed.stdout + completed.stderr).decode("utf-8", errors="replace")
    match = re.search(r"Dart SDK version:\s*(\S+)", text)
    return match.group(1) if match else UNKNOWN


def _pinned_versions(harness_dir: Path) -> dict[str, str]:
    """Read exact pinned versions straight from pubspec.lock, never from the
    (mutable, aspirational) version ranges in pubspec.yaml."""
    lock_path = harness_dir / "pubspec.lock"
    if not lock_path.is_file():
        return {name: UNKNOWN for name in _TARGET_PACKAGES.values() if name}
    versions: dict[str, str] = {}
    current_package: str | None = None
    for line in lock_path.read_text(encoding="utf-8").splitlines():
        package_match = re.match(r"^  (\S+):$", line)
        if package_match:
            current_package = package_match.group(1)
            continue
        version_match = re.match(r'^\s+version:\s*"?([^"\s]+)"?', line)
        if version_match and current_package is not None:
            versions[current_package] = version_match.group(1)
    return {
        name: versions.get(name, UNKNOWN)
        for name in _TARGET_PACKAGES.values()
        if name is not None
    }


def _harness_facts(executable: str) -> dict[str, str]:
    """Read build facts off the compiled binary itself, so they describe what
    actually ran (mirrors the original project's `_harness_facts`, minus the
    ASan/UBSan marker search, which has no Dart analogue)."""
    path = Path(executable)
    if not path.is_file():
        return {"harness_sha256": UNKNOWN}
    try:
        data = path.read_bytes()
    except OSError:
        return {"harness_sha256": UNKNOWN}
    return {"harness_sha256": hashlib.sha256(data).hexdigest()}


def build_report(
    manifest: dict[str, Any],
    *,
    experiment_type: str,
    executable: str,
    runs: int,
    examples_per_run: int,
    max_refinement_iterations: int | None,
    repo_root: Path,
    harness_dir: Path,
) -> dict[str, Any]:
    """Merge one run manifest with environment facts it cannot record itself."""
    seed = manifest.get("seed")
    return {
        "experiment_type": experiment_type,
        "targets": _TARGET_PACKAGES,
        "target_versions": _pinned_versions(harness_dir),
        "dart_sdk_version": _dart_sdk_version(),
        "python_version": manifest.get("python_version", UNKNOWN),
        "python_implementation": manifest.get("python_implementation", UNKNOWN),
        "operating_system": f"{platform.system()} {platform.release()}".strip() or UNKNOWN,
        "platform": manifest.get("platform", UNKNOWN),
        "hypothesis_version": manifest.get("hypothesis_version", UNKNOWN),
        "model": manifest.get("model") or "not applicable",
        "feedback_mode": manifest.get("feedback_mode") or "not applicable",
        "seed": seed if seed is not None else UNKNOWN,
        "seeds": [seed + index for index in range(runs)] if isinstance(seed, int) else UNKNOWN,
        "runs": runs,
        "examples_per_run": examples_per_run,
        "max_refinement_iterations": max_refinement_iterations
        if max_refinement_iterations is not None
        else "not applicable",
        "timestamp": manifest.get("timestamp", UNKNOWN),
        "command_line": shlex.join(sys.argv),
        "git_commit": _git(repo_root, "rev-parse", "HEAD"),
        "git_branch": _git(repo_root, "rev-parse", "--abbrev-ref", "HEAD"),
        "harness_executable": executable,
        **_harness_facts(executable),
    }


_LABELS = (
    ("experiment_type", "Experiment type"),
    ("target_versions", "Target package versions"),
    ("dart_sdk_version", "Dart SDK version"),
    ("harness_executable", "Harness executable"),
    ("harness_sha256", "Harness SHA-256"),
    ("python_version", "Python version"),
    ("python_implementation", "Python implementation"),
    ("operating_system", "Operating system"),
    ("platform", "Platform"),
    ("hypothesis_version", "Hypothesis version"),
    ("model", "OpenAI model"),
    ("feedback_mode", "Prompt feedback mode"),
    ("seed", "Base random seed"),
    ("seeds", "Per-run seeds"),
    ("runs", "Number of runs"),
    ("examples_per_run", "Examples per run"),
    ("max_refinement_iterations", "Maximum refinement iterations"),
    ("timestamp", "Execution timestamp (UTC)"),
    ("command_line", "Executed command line"),
    ("git_commit", "Repository commit"),
    ("git_branch", "Repository branch"),
)


def render_markdown(report: dict[str, Any]) -> str:
    lines = ["# Reproducibility report", "", "| Field | Value |", "|---|---|"]
    for key, label in _LABELS:
        value = report.get(key, UNKNOWN)
        if isinstance(value, (list, dict)):
            value = ", ".join(f"{k}={v}" for k, v in value.items()) if isinstance(value, dict) else ", ".join(
                str(item) for item in value
            )
        text = str(value).replace("|", "\\|")
        if key in {"harness_sha256", "git_commit", "command_line", "harness_executable"}:
            text = f"`{text}`"
        lines.append(f"| {label} | {text} |")
    lines += [
        "",
        f'Fields reported as "{UNKNOWN}" were not recoverable in this environment; '
        "they are reported as missing rather than inferred.",
    ]
    return "\n".join(lines) + "\n"


def write_report(directory: Path, report: dict[str, Any], stem: str = "reproducibility") -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / f"{stem}.json"
    markdown_path = directory / f"{stem}.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return [json_path, markdown_path]
