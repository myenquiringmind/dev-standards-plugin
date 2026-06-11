"""CLI: run a language profile's CLI validation checks at module scope.

Invoked by the validate pipeline (``/validate``) and by ``/tdd``'s VALIDATE
step. Given a ``--language`` (a profile name such as ``python``), this runs
that profile's *CLI* validation steps — the subset of ``validationSteps``
that map to a command-line tool rather than an agent — concurrently, and
reports a JSON pass/fail summary on stdout. ``/validate`` consumes the
summary to decide whether to call ``stamp_validation.py``.

The command for each step is derived from the profile's ``tools`` block,
adapted to *check mode*:

* the ``{file}`` placeholder and any ``--fix`` / ``--fix-only`` token are
  removed (validation must not silently mutate the tree);
* formatters gain ``--check`` so they report drift instead of rewriting;
* test runners run the **whole suite** (no target path) — honouring the
  full-pytest-for-footer convention;
* linters and type checkers run against the ``--target`` paths (default
  ``.``).

Only the P0 ``python`` / frontend tool shapes are exercised today. Richer
per-profile validation commands can be added when a profile needs them —
the same narrow-now-grow-later stance ``_hook_shared`` takes for the step
tuples.

Exit codes:

* 0 — every CLI step passed
* 1 — at least one CLI step failed, or an I/O / profile error occurred
* 2 — bad arguments

Event: N/A (CLI utility invoked by /validate; not a hook)
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING, Any

from hooks._hook_shared import get_project_dir
from hooks._profiles import load_profile

if TYPE_CHECKING:
    from collections.abc import Sequence

#: Per-step subprocess timeout. pytest dominates; keep generous but bounded.
_SUBPROCESS_TIMEOUT: int = 120

#: Max characters of captured tool output echoed back in the JSON summary.
_OUTPUT_CAP: int = 4000

#: Canonical CLI validation step name -> the profile ``tools`` kind that
#: implements it. A ``validationSteps`` entry not present here is an agent
#: step (e.g. ``objective-verifier``) and is skipped by this runner.
_STEP_TOOL_KIND: dict[str, str] = {
    "ruff-check": "linter",
    "eslint": "linter",
    "ruff-format": "formatter",
    "mypy-strict": "typeChecker",
    "tsc-strict": "typeChecker",
    "pytest": "testRunner",
    "vitest": "testRunner",
}

#: Tokens stripped from a tool template when building its check-mode argv.
_FIX_TOKENS: frozenset[str] = frozenset({"--fix", "--fix-only", "{file}"})


class StepResult:
    """Outcome of one CLI validation step."""

    __slots__ = ("name", "output", "passed")

    def __init__(self, *, name: str, passed: bool, output: str) -> None:
        self.name = name
        self.passed = passed
        self.output = output

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "passed": self.passed, "output": self.output}


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="run_cli_checks")
    parser.add_argument(
        "--language",
        required=True,
        help="Profile name to run CLI checks for (e.g. 'python').",
    )
    parser.add_argument(
        "--target",
        action="append",
        default=None,
        metavar="PATH",
        help="Repeatable — path(s) to check. Defaults to '.' (project root).",
    )
    return parser.parse_args(argv)


def _build_check_argv(kind: str, spec: dict[str, Any], targets: list[str]) -> list[str] | None:
    """Turn a profile tool-spec into a check-mode argv, or ``None``.

    Args:
        kind: The tool kind (``linter`` / ``formatter`` / ``typeChecker`` /
            ``testRunner``) — drives check-mode adaptation.
        spec: The ``tools.<kind>`` block from the profile.
        targets: Paths to check (ignored for ``testRunner``).

    Returns:
        Argv token list, or ``None`` if *spec* has no usable ``command``.
    """
    template = spec.get("command")
    if not isinstance(template, str) or not template.strip():
        return None

    argv = [tok for tok in shlex.split(template, posix=False) if tok not in _FIX_TOKENS]

    extra = spec.get("args")
    if isinstance(extra, list):
        argv.extend(str(a) for a in extra if isinstance(a, str))

    if kind == "formatter" and "--check" not in argv:
        argv.append("--check")

    if kind != "testRunner":
        argv.extend(targets)

    return argv


def _run_step(name: str, argv: list[str], project_dir: Path) -> StepResult:
    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
            check=False,
            cwd=project_dir,
        )
    except FileNotFoundError:
        return StepResult(name=name, passed=False, output=f"tool '{argv[0]}' not found on PATH")
    except subprocess.TimeoutExpired:
        return StepResult(
            name=name, passed=False, output=f"timed out after {_SUBPROCESS_TIMEOUT}s"
        )
    except OSError as exc:
        return StepResult(name=name, passed=False, output=f"could not run: {exc}")

    output = (result.stdout + result.stderr).strip()[:_OUTPUT_CAP]
    return StepResult(name=name, passed=result.returncode == 0, output=output)


def _plan_steps(profile: dict[str, Any], targets: list[str]) -> list[tuple[str, list[str]]]:
    """Resolve the profile's CLI steps to ``(step_name, argv)`` pairs."""
    steps = profile.get("validationSteps")
    tools = profile.get("tools")
    if not isinstance(steps, list) or not isinstance(tools, dict):
        return []

    planned: list[tuple[str, list[str]]] = []
    for step in steps:
        kind = _STEP_TOOL_KIND.get(step) if isinstance(step, str) else None
        if kind is None:
            continue
        spec = tools.get(kind)
        if not isinstance(spec, dict):
            continue
        argv = _build_check_argv(kind, spec, targets)
        if argv is not None:
            planned.append((step, argv))
    return planned


def run_checks(language: str, targets: list[str], project_dir: Path) -> dict[str, Any]:
    """Run *language*'s CLI checks against *targets* and return the summary."""
    profile = load_profile(language, project_dir)
    if profile is None:
        return {
            "language": language,
            "all_passed": False,
            "error": f"no profile for language '{language}'",
            "steps": [],
        }

    planned = _plan_steps(profile, targets)
    if not planned:
        return {
            "language": language,
            "all_passed": False,
            "error": "profile declares no CLI validation steps",
            "steps": [],
        }

    with ThreadPoolExecutor(max_workers=len(planned)) as pool:
        results = list(
            pool.map(lambda item: _run_step(item[0], item[1], project_dir), planned),
        )

    return {
        "language": language,
        "all_passed": all(r.passed for r in results),
        "steps": [r.as_dict() for r in results],
    }


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2

    targets: list[str] = args.target if args.target else ["."]
    summary = run_checks(args.language, targets, get_project_dir())

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
