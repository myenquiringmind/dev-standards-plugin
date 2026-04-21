"""Block ``git commit`` unless every required validation stamp is valid.

The keystone of the framework's commit gate. On any Bash command that
invokes ``git commit`` the hook:

1. Honours two explicit bypasses — ``[WIP]`` in the commit message and
   a ``.git/MERGE_HEAD`` sentinel (conflict resolution).
2. Inspects the staged diff to decide which gates must be stamped.
3. For each required gate, loads the stamp file, validates it against
   ``schemas/stamp.schema.json`` and checks freshness (<15 min),
   branch match, and canonical step coverage.
4. Exits 2 with a specific message on the first failure.

No stamp enforcement happens on non-``git commit`` Bash calls.

Event: PreToolUse
Matcher: Bash
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

from hooks._hook_shared import (
    AGENT_VALIDATION_STEPS,
    FE_VALIDATION_STEPS,
    PY_VALIDATION_STEPS,
    STAMP_TTL,
    get_current_branch,
    get_project_dir,
    read_hook_input,
)

_GIT_COMMIT = re.compile(r"\bgit\s+(?:-[cC]\s+\S+\s+)*commit\b(?!-)")
_WIP_MARKER = re.compile(r"\[WIP\]")

_STAMP_FILENAMES: dict[str, str] = {
    "code": ".validation_stamp",
    "frontend": ".frontend_validation_stamp",
    "agent": ".agent_validation_stamp",
    "db": ".db_validation_stamp",
    "api": ".api_validation_stamp",
}

_CANONICAL_STEPS: dict[str, frozenset[str]] = {
    "code": frozenset(PY_VALIDATION_STEPS),
    "frontend": frozenset(FE_VALIDATION_STEPS),
    "agent": frozenset(AGENT_VALIDATION_STEPS),
    "db": frozenset(),
    "api": frozenset(),
}

_FRONTEND_EXTS: frozenset[str] = frozenset(
    {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte", ".css", ".scss"}
)


def _is_git_commit(command: str) -> bool:
    return bool(_GIT_COMMIT.search(command))


def _has_wip_bypass(command: str) -> bool:
    return bool(_WIP_MARKER.search(command))


def _has_merge_head(project_dir: Path) -> bool:
    return (project_dir / ".git" / "MERGE_HEAD").is_file()


def _staged_files(project_dir: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _required_gates(staged: list[str]) -> set[str]:
    gates: set[str] = set()
    for raw in staged:
        path = Path(raw)
        suffix = path.suffix.lower()
        parts = path.parts

        if suffix == ".py":
            gates.add("code")
        elif suffix in _FRONTEND_EXTS:
            gates.add("frontend")

        if parts and parts[0] == "agents" and suffix == ".md":
            gates.add("agent")
        if "migrations" in parts and suffix == ".sql":
            gates.add("db")
        if parts and parts[0] == "api" and suffix in {".yaml", ".yml", ".json"}:
            gates.add("api")
        if path.name.lower().startswith("openapi.") and suffix in {".yaml", ".yml", ".json"}:
            gates.add("api")
    return gates


def _load_schema(project_dir: Path) -> dict[str, Any] | None:
    path = project_dir / "schemas" / "stamp.schema.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _parse_timestamp(raw: str) -> datetime | None:
    try:
        # Accept both "...Z" and full ISO-8601 with offset.
        normalized = raw.replace("Z", "+00:00") if raw.endswith("Z") else raw
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _validate_stamp(
    gate: str,
    project_dir: Path,
    branch: str,
    schema: dict[str, Any],
    now: datetime,
) -> str | None:
    """Return None if the stamp is valid, else a human-readable error."""
    filename = _STAMP_FILENAMES[gate]
    stamp_path = project_dir / filename

    if not stamp_path.is_file():
        return f"no stamp found for gate '{gate}' — run /validate before committing"

    try:
        stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"stamp for gate '{gate}' is unreadable: {exc}"

    errors = sorted(Draft202012Validator(schema).iter_errors(stamp), key=lambda e: list(e.path))
    if errors:
        first = errors[0]
        path = ".".join(str(p) for p in first.path) or "(root)"
        return f"stamp for gate '{gate}' fails schema at {path}: {first.message}"

    ts = _parse_timestamp(str(stamp.get("timestamp", "")))
    if ts is None:
        return f"stamp for gate '{gate}' has unparseable timestamp"
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    age_seconds = (now - ts).total_seconds()
    if age_seconds > STAMP_TTL:
        minutes = int(age_seconds // 60)
        return (
            f"stamp for gate '{gate}' is stale ({minutes} min old, TTL {STAMP_TTL // 60} min) "
            f"— re-run /validate"
        )
    if age_seconds < -60:
        return f"stamp for gate '{gate}' is dated in the future — clock skew?"

    stamp_branch = str(stamp.get("branch", ""))
    if stamp_branch != branch:
        return (
            f"stamp for gate '{gate}' is for branch '{stamp_branch}', "
            f"but current branch is '{branch}' — re-run /validate"
        )

    canonical = _CANONICAL_STEPS[gate]
    if canonical:
        stamp_steps = {str(s) for s in stamp.get("steps", [])}
        missing = canonical - stamp_steps
        if missing:
            return (
                f"stamp for gate '{gate}' is missing canonical steps: "
                f"{sorted(missing)} — re-run /validate"
            )

    return None


def main() -> int:
    data = read_hook_input()
    if str(data.get("tool_name", "")) != "Bash":
        return 0

    tool_input = data.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return 0

    command = tool_input.get("command")
    if not isinstance(command, str) or not _is_git_commit(command):
        return 0

    project_dir = get_project_dir()

    if _has_merge_head(project_dir):
        return 0
    if _has_wip_bypass(command):
        return 0

    staged = _staged_files(project_dir)
    if not staged:
        return 0

    gates = _required_gates(staged)
    if not gates:
        return 0

    branch = get_current_branch(project_dir)
    if not branch:
        print(
            "[pre_commit_cli_gate] refusing commit — could not determine current branch",
            file=sys.stderr,
        )
        return 2

    schema = _load_schema(project_dir)
    if schema is None:
        print(
            "[pre_commit_cli_gate] refusing commit — stamp schema missing or invalid "
            "at schemas/stamp.schema.json",
            file=sys.stderr,
        )
        return 2

    now = datetime.now(UTC)
    for gate in sorted(gates):
        error = _validate_stamp(gate, project_dir, branch, schema, now)
        if error is not None:
            print(f"[pre_commit_cli_gate] refusing commit — {error}", file=sys.stderr)
            return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
