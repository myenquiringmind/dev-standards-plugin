"""CLI: assert that scaffolded tests are RED (failing, not erroring).

Invoked by ``/scaffold`` as its final step. After ``/scaffold`` writes a
stub module (method bodies ``...``) and a test skeleton, the tests must be
**RED** before ``/tdd`` proceeds: every collected test *fails*, none
*errors* (import / fixture / collection problems), and none *passes* (a
passing test against an unimplemented stub is a broken test, not a spec).

This runs the profile's ``testRunner`` against the given ``--test`` paths
and classifies the outcome. It is a CLI utility, not a CC event hook — the
develop phase has no standing trigger that would tell a PostToolUse hook
"scaffolding just finished", and running the suite on every edit would be
both wrong (GREEN wants passes) and too slow. ``/scaffold`` calls this
explicitly, the same way ``/validate`` calls ``run_cli_checks``.

Classification (pytest summary counts are the primary signal; the return
code is the fallback):

* ``failed > 0`` and ``passed == 0`` and ``errors == 0`` → **RED** (exit 0)
* ``errors > 0``                                         → not RED (exit 2)
* ``passed > 0``                                         → not RED (exit 2)
* no tests collected                                     → not RED (exit 2)

Exit codes:

* 0 — RED confirmed
* 1 — bad args, no profile, or the test runner could not be launched
* 2 — not RED (errors, unexpected passes, or no tests) — ``/scaffold`` stops

Event: N/A (CLI utility invoked by /scaffold; not a hook)
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from hooks._hook_shared import get_project_dir
from hooks._profiles import build_tool_argv, load_profile

if TYPE_CHECKING:
    from collections.abc import Sequence

_SUBPROCESS_TIMEOUT: int = 60

#: Counts pulled from a pytest summary line, e.g. "2 failed, 1 error in 0.1s".
_COUNT_RE = re.compile(r"(\d+)\s+(passed|failed|error|errors)\b", re.IGNORECASE)


class Verdict(Enum):
    """Outcome of the red-gate classification."""

    RED = "RED"
    ERRORED = "NOT_RED: tests ERROR (import/collection) — scaffold must FAIL, not ERROR"
    PASSED = "NOT_RED: tests PASS — a RED scaffold must fail before implementation"
    NO_TESTS = "NOT_RED: no tests collected — scaffold must produce failing tests"
    UNKNOWN = "NOT_RED: could not classify test output"


def _parse_counts(output: str) -> dict[str, int]:
    """Extract ``passed`` / ``failed`` / ``error`` counts from runner output."""
    counts = {"passed": 0, "failed": 0, "error": 0}
    for number, label in _COUNT_RE.findall(output):
        key = "error" if label.lower().startswith("error") else label.lower()
        counts[key] = counts.get(key, 0) + int(number)
    return counts


def classify(output: str, returncode: int) -> Verdict:
    """Classify a test run as RED or one of the not-RED reasons.

    Args:
        output: Combined stdout+stderr of the test runner.
        returncode: The runner's exit code (fallback when no counts parse).

    Returns:
        The :class:`Verdict`.
    """
    counts = _parse_counts(output)

    if counts["error"] > 0:
        return Verdict.ERRORED
    if counts["passed"] > 0:
        return Verdict.PASSED
    if counts["failed"] > 0:
        return Verdict.RED

    # No failures, passes, or errors counted. Lean on the return code:
    # pytest exits 5 when it collects no tests at all (a gate block — the
    # scaffold produced no failing tests); a clean 0 means an unrecognised
    # all-green run (not RED); anything else we cannot classify.
    if returncode == 5:
        return Verdict.NO_TESTS
    if returncode == 0:
        return Verdict.PASSED
    return Verdict.UNKNOWN


def _runner_argv(profile: dict[str, Any], tests: list[str]) -> list[str] | None:
    tools = profile.get("tools")
    if not isinstance(tools, dict):
        return None
    spec = tools.get("testRunner")
    # Build the base argv, dropping the {file} placeholder, then append the
    # concrete test targets so several scaffolded files run in one pass.
    argv = build_tool_argv(spec, "")
    if argv is None:
        return None
    argv = [tok for tok in argv if tok and tok != "{file}"]
    argv.extend(tests)
    return argv


def run_gate(language: str, tests: list[str], project_dir: Path) -> tuple[Verdict, str]:
    """Run the red gate and return ``(verdict, detail)``."""
    profile = load_profile(language, project_dir)
    if profile is None:
        return Verdict.UNKNOWN, f"no profile for language '{language}'"

    argv = _runner_argv(profile, tests)
    if argv is None:
        return Verdict.UNKNOWN, f"profile '{language}' declares no testRunner"

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
        return Verdict.UNKNOWN, f"test runner '{argv[0]}' not found on PATH"
    except subprocess.TimeoutExpired:
        return Verdict.UNKNOWN, f"test runner timed out after {_SUBPROCESS_TIMEOUT}s"
    except OSError as exc:
        return Verdict.UNKNOWN, f"could not run test runner: {exc}"

    output = (result.stdout + result.stderr).strip()
    return classify(output, result.returncode), output


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="scaffold_red_gate")
    parser.add_argument(
        "--language",
        required=True,
        help="Profile name whose testRunner to use (e.g. 'python').",
    )
    parser.add_argument(
        "--test",
        action="append",
        required=True,
        metavar="PATH",
        help="Repeatable — scaffolded test path(s) to run.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2

    verdict, detail = run_gate(args.language, args.test, get_project_dir())

    if verdict is Verdict.RED:
        print("[scaffold_red_gate] RED confirmed — scaffolded tests fail as required")
        return 0

    print(f"[scaffold_red_gate] {verdict.value}", file=sys.stderr)
    if detail:
        print(detail, file=sys.stderr)
    # UNKNOWN with a launch error (no profile / no runner / not found) is an
    # operational failure (exit 1); a classified not-RED outcome is a gate
    # block (exit 2).
    if verdict is Verdict.UNKNOWN:
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
