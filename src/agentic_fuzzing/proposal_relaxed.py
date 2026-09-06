"""Experimental variant of `proposal.py` for one isolated ablation (paper
Section V-E, future work item 1): does relaxing the sandbox's import
restriction to also permit `json` -- and nothing else -- close part of
RQ2's refinement/static-generator gap by removing the JSON-hand-rolling
overhead, or does the targeting gap persist regardless?

`proposal.py` itself is left completely untouched: it is one of the files
reused verbatim from the original pipeline, and this ablation must not risk
that file's validated behavior for RQ1/RQ2's main comparison. This module
duplicates its AST-validation logic with exactly one line of difference
(the set of importable module names), rather than parametrizing the
original, so the original's own file stays byte-for-byte what it was
validated as.
"""

import ast
from collections.abc import Iterable
from dataclasses import dataclass
import builtins

from hypothesis import strategies as st
import json as _json_module

from .proposal import GenerationError, ProposalError

_ALLOWED_MODULES = {"hypothesis", "json"}


def load_strategy(source: str):
    """Same validation as `proposal.load_strategy`, except `import json` (and
    only `json`) is additionally permitted."""
    try:
        tree = ast.parse(source, mode="exec")
    except SyntaxError as error:
        raise ProposalError(f"proposal has invalid Python: {error}") from error

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = {alias.name for alias in node.names}
            module = node.module if isinstance(node, ast.ImportFrom) else None
            if isinstance(node, ast.Import):
                if names - _ALLOWED_MODULES:
                    raise ProposalError(
                        "proposal imports are restricted to hypothesis.strategies and json"
                    )
            else:
                if module == "hypothesis":
                    names.discard("strategies")
                    if names:
                        raise ProposalError(
                            "proposal imports are restricted to hypothesis.strategies and json"
                        )
                elif module != "json":
                    raise ProposalError(
                        "proposal imports are restricted to hypothesis.strategies and json"
                    )
        if isinstance(node, (ast.Call,)) and isinstance(node.func, ast.Name):
            if node.func.id in {"eval", "exec", "open", "compile", "__import__"}:
                raise ProposalError(f"proposal uses forbidden call: {node.func.id}")

    def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "hypothesis" and fromlist == ("strategies",):
            return builtins.__import__(name, globals, locals, fromlist, level)
        if name == "json":
            return _json_module
        raise ProposalError("proposal imports are restricted to hypothesis.strategies and json")

    _BLOCKED_BUILTINS = frozenset(
        {
            "eval", "exec", "compile", "__import__", "open", "input",
            "breakpoint", "exit", "quit", "help",
            "globals", "locals", "vars", "getattr", "setattr", "delattr",
        }
    )
    safe_builtins = {
        name: value for name, value in vars(builtins).items() if name not in _BLOCKED_BUILTINS
    }
    safe_builtins["__import__"] = safe_import
    namespace = {"st": st, "json": _json_module, "__builtins__": safe_builtins}
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


def proposal_inputs(source: str, examples: int) -> Iterable[bytes | GenerationError]:
    strategy = load_strategy(source)
    for _ in range(examples):
        try:
            value = strategy().example()
        except Exception as error:
            yield GenerationError(f"{type(error).__name__}: {error}")
            continue
        if not isinstance(value, bytes):
            yield GenerationError("generated_json emitted a non-bytes value")
            continue
        yield value
