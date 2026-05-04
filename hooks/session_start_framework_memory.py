"""Initialise the framework-memory directory tree at SessionStart.

Phase 4 stream 1. Ensures every directory under
``framework_memory_dir()`` exists before later hooks try to write
to them. Idempotent: existing directories are left alone, missing
ones are created. A defensive ``.gitignore`` is dropped at the
framework-memory root so the tree never accidentally gets committed
when the resolver falls back to ``<project>/.claude/framework-memory``
(the env-var-unset case).

Advisory only. Returns exit 0 even on I/O failure — the framework
remembers state across sessions, but a single SessionStart that
cannot create the tree should not block the user from working. The
hook prints a warning to stderr; the next session retries.

Event: SessionStart
Matcher: *
"""

from __future__ import annotations

import sys

from hooks._hook_shared import read_hook_input
from hooks._memory import all_subdirs, framework_memory_dir
from hooks._os_safe import atomic_write

_GITIGNORE_BODY: str = (
    "# Framework memory tier — local plugin state, never committed.\n"
    "# Phase 4 session_start_framework_memory.py writes this defensively;\n"
    "# the canonical location is ${CLAUDE_PLUGIN_DATA}/framework-memory/\n"
    "# which already lives outside the repo. The .gitignore covers the\n"
    "# fallback case where the resolver lands inside <project>/.claude/.\n"
    "*\n"
    "!.gitignore\n"
)


def main() -> int:
    read_hook_input()

    root = framework_memory_dir()
    failures: list[str] = []

    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        failures.append(f"{root}: {exc}")

    for subdir in all_subdirs():
        try:
            subdir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            failures.append(f"{subdir}: {exc}")

    if not failures:
        gitignore = root / ".gitignore"
        try:
            if not gitignore.is_file():
                atomic_write(gitignore, _GITIGNORE_BODY)
        except OSError as exc:
            failures.append(f"{gitignore}: {exc}")

    if failures:
        joined = "; ".join(failures)
        print(
            f"[session_start_framework_memory] could not initialise tree: {joined}",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
