"""Audit .gitignore for critical patterns at SessionStart.

Per ``.claude/rules/security-internal.md``, the plugin's ``.gitignore``
must cover a set of ephemeral-file and secret-file patterns. Missing
patterns mean ephemeral cache files or forbidden secret files could
accidentally be committed.

This hook warns but never blocks — a missing entry is a flag for
the session to fix, not a gate that stops work. The warning is
emitted both to stderr (for humans tailing the terminal) and as
``additionalContext`` (for the model to act on).

Event: SessionStart
Matcher: *
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from hooks._hook_shared import get_project_dir, read_hook_input

_REQUIRED_PATTERNS: tuple[str, ...] = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    ".validation_stamp*",
    ".context_pct",
    "session-state.md.injected",
    "tmp/",
    ".venv/",
    "node_modules/",
)


_COMMENT_RE = re.compile(r"\s*#.*$")


def _gitignore_entries(project_dir: Path) -> set[str]:
    path = project_dir / ".gitignore"
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return set()
    entries: set[str] = set()
    for raw_line in raw.splitlines():
        line = _COMMENT_RE.sub("", raw_line).strip()
        if not line:
            continue
        normalised = line.lstrip("!")
        entries.add(normalised)
    return entries


def _is_covered(required: str, entries: set[str]) -> bool:
    if required in entries:
        return True
    alternatives = {
        required,
        required.lstrip("/"),
        "/" + required,
    }
    if required.endswith("/"):
        trimmed = required.rstrip("/")
        alternatives.update({trimmed, trimmed + "/", "/" + trimmed, "/" + trimmed + "/"})
    return bool(alternatives & entries)


def _missing_patterns(project_dir: Path) -> list[str]:
    entries = _gitignore_entries(project_dir)
    if not entries:
        return list(_REQUIRED_PATTERNS)
    return [p for p in _REQUIRED_PATTERNS if not _is_covered(p, entries)]


def main() -> int:
    read_hook_input()

    project_dir = get_project_dir()
    missing = _missing_patterns(project_dir)

    if not missing:
        return 0

    joined = ", ".join(missing)
    print(
        f"[session_start_gitignore_audit] .gitignore missing required patterns: {joined}. "
        f"See .claude/rules/security-internal.md for the canonical list.",
        file=sys.stderr,
    )

    warning = (
        "## .gitignore audit warning\n\n"
        f"The project `.gitignore` is missing these required patterns: {joined}.\n\n"
        "Per `.claude/rules/security-internal.md`, these patterns prevent ephemeral "
        "cache files, secrets, and scratch directories from being committed. "
        "Add the missing entries when you next edit `.gitignore`."
    )
    print(json.dumps({"additionalContext": warning}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
