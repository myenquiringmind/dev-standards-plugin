"""Phase 2 live-integration smoke — exercise assertions 1, 2, 10 with real model calls.

Spec'd in ``docs/phases/phase-2-hook-completion.md`` § exit gate.
``scripts/bootstrap_smoke.py`` covers assertions 1, 2, and 10
*structurally* (file presence, frontmatter shape, schema membership).
This script exercises the same agent contracts *live*: each check
makes a real Anthropic Messages API call using the agent's own
prompt body and asserts the response shape.

Skipped silently (exit 0 with a status line) when:

- ``ANTHROPIC_API_KEY`` is unset, or
- the ``anthropic`` SDK is not installed (``uv add --dev anthropic``).

The skip path lets unkeyed users (and CI environments without
secrets) run this without breaking. The bootstrap_smoke structural
assertions are the line of defence that runs everywhere; this
script is the on-demand live confirmation.

Cost: ~3 small Haiku 4.5 calls per run, well under one cent per
run. Intended as on-demand verification by the user, not
per-build CI.

Usage:
    ANTHROPIC_API_KEY=sk-... uv run python -m scripts.live_integration_smoke
    uv run python -m scripts.live_integration_smoke --root /path/to/repo
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

_MODEL: str = "claude-haiku-4-5-20251001"
_MAX_TOKENS: int = 512


@dataclass
class CheckResult:
    number: int
    name: str
    passed: bool
    detail: str = ""


def _strip_frontmatter(text: str) -> str:
    """Drop a leading YAML frontmatter block, returning the agent's body text."""
    match = re.match(r"^---\n.*?\n---\n", text, re.DOTALL)
    return text[match.end() :] if match else text


def _call_model(client: Any, *, system: str, user: str) -> str:
    """One Messages API call. Returns the assistant's text response."""
    response = client.messages.create(
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    parts = [block.text for block in response.content if getattr(block, "type", "") == "text"]
    return "\n".join(parts).strip()


def _check_validate_command_live(client: Any, root: Path) -> CheckResult:
    """Live equivalent of bootstrap_smoke assertion 1.

    Loads ``commands/validate.md`` as the system prompt and asks the
    model to summarise what running ``/validate code`` would do. A
    non-empty, on-topic response confirms the command body is coherent
    enough to drive a real model.
    """
    path = root / "commands" / "validate.md"
    if not path.is_file():
        return CheckResult(1, "validate-command-live", False, f"missing: {path}")
    system = _strip_frontmatter(path.read_text(encoding="utf-8"))
    try:
        response = _call_model(
            client,
            system=system,
            user=(
                "In one short paragraph, describe what running `/validate code` "
                "in this framework checks. Do not invoke any tools."
            ),
        )
    except Exception as exc:
        return CheckResult(1, "validate-command-live", False, f"API error: {exc}")
    if not response or len(response) < 50:
        return CheckResult(1, "validate-command-live", False, "response too short")
    if "validate" not in response.lower():
        return CheckResult(1, "validate-command-live", False, "off-topic response")
    return CheckResult(1, "validate-command-live", True)


def _check_objective_verifier_live(client: Any, root: Path) -> CheckResult:
    """Live equivalent of bootstrap_smoke assertion 2.

    Loads ``agents/validation/validation-objective-verifier.md`` and
    presents a deliberately scope-violating synthetic diff. Expects a
    response containing a recognizable verdict signal.
    """
    path = root / "agents" / "validation" / "validation-objective-verifier.md"
    if not path.is_file():
        return CheckResult(2, "objective-verifier-live", False, f"missing: {path}")
    system = _strip_frontmatter(path.read_text(encoding="utf-8"))
    user = (
        "OBJECTIVE: fix a typo in README.md.\n\n"
        "STAGED DIFF: a 200-line refactor of hooks/_os_safe.py introducing a "
        "new locking strategy plus three new tests.\n\n"
        "Evaluate scope drift. Respond with a one-line verdict starting with "
        "either 'APPROVED:' or 'BLOCKED:' followed by your reasoning."
    )
    try:
        response = _call_model(client, system=system, user=user)
    except Exception as exc:
        return CheckResult(2, "objective-verifier-live", False, f"API error: {exc}")
    if not response:
        return CheckResult(2, "objective-verifier-live", False, "empty response")
    upper = response.upper()
    if "BLOCKED" not in upper and "APPROVED" not in upper:
        return CheckResult(
            2,
            "objective-verifier-live",
            False,
            f"no verdict signal: {response[:120]}",
        )
    # The synthetic diff is a clear scope violation; expect BLOCKED.
    if "BLOCKED" not in upper:
        return CheckResult(
            2,
            "objective-verifier-live",
            False,
            "scope violation accepted (expected BLOCKED)",
        )
    return CheckResult(2, "objective-verifier-live", True)


def _check_transcript_extractor_live(client: Any, root: Path) -> CheckResult:
    """Live equivalent of bootstrap_smoke assertion 10.

    Loads the transcript-todo-extractor agent body and runs it against a
    synthetic transcript fragment containing a clear deferral. Validates
    the JSON output against the report schema.
    """
    agent_path = root / "agents" / "closed-loop" / "closed-loop-transcript-todo-extractor.md"
    schema_path = root / "schemas" / "reports" / "transcript-todo-extraction.schema.json"
    if not agent_path.is_file():
        return CheckResult(10, "transcript-extractor-live", False, f"missing: {agent_path}")
    if not schema_path.is_file():
        return CheckResult(10, "transcript-extractor-live", False, f"missing: {schema_path}")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    system = _strip_frontmatter(agent_path.read_text(encoding="utf-8"))
    user = (
        "Synthetic SubagentStop transcript fragment:\n\n"
        '{"type":"assistant","content":"Implemented the change. There is an '
        "unused import in hooks/foo.py I noticed but did not clean up here; "
        'we should address that in a follow-up."}\n\n'
        "Emit a JSON report matching the transcript-todo-extraction schema. "
        "Set subagent='live-smoke', session_id='live-smoke', "
        "extracted_at='2026-05-01T00:00:00Z'. Output ONLY the JSON object, "
        "no prose."
    )
    try:
        response = _call_model(client, system=system, user=user)
    except Exception as exc:
        return CheckResult(10, "transcript-extractor-live", False, f"API error: {exc}")
    # Strip markdown code fences if the model wrapped the JSON.
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", response.strip(), flags=re.MULTILINE)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        return CheckResult(
            10,
            "transcript-extractor-live",
            False,
            f"output not JSON: {exc}; got: {cleaned[:120]}",
        )
    errors = list(Draft202012Validator(schema).iter_errors(parsed))
    if errors:
        return CheckResult(
            10,
            "transcript-extractor-live",
            False,
            f"schema violation: {errors[0].message}",
        )
    return CheckResult(10, "transcript-extractor-live", True)


def _skip(reason: str) -> int:
    print(f"[live-integration-smoke] skipped - {reason}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 2 live-integration smoke")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return _skip("ANTHROPIC_API_KEY not set")

    try:
        import anthropic  # type: ignore[import-not-found]
    except ImportError:
        return _skip("anthropic SDK not installed (uv add --dev anthropic)")

    client = anthropic.Anthropic(api_key=api_key)
    root: Path = args.root.resolve()

    checks = [
        _check_validate_command_live(client, root),
        _check_objective_verifier_live(client, root),
        _check_transcript_extractor_live(client, root),
    ]
    total = len(checks)
    for r in checks:
        status = "PASS" if r.passed else "FAIL"
        line = f"[live-integration-smoke] {r.number:>2}/{total} [{status}] {r.name}"
        if r.detail:
            line += f" - {r.detail}"
        print(line)

    passed = sum(1 for r in checks if r.passed)
    outcome = "OK" if passed == total else "FAILED"
    print(f"[live-integration-smoke] {passed}/{total} passed - live exit gate {outcome}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
