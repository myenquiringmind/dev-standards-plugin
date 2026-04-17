"""Block Bash commands that match known-destructive patterns.

This is a last-ditch defence — not a full sandbox. The patterns list
catches the canonical footguns (``rm -rf /``, ``git reset --hard``
on protected branches, fork bombs, piping remote URLs to a shell).
Each pattern has to be literal enough that the false-positive rate
stays near zero.

Anything more nuanced belongs upstream — either the model refuses,
or a permission prompt gates it. This hook is the belt to that
set of braces.

Event: PreToolUse
Matcher: Bash
"""

from __future__ import annotations

import re
import sys

from hooks._hook_shared import (
    PROTECTED_BRANCHES,
    get_current_branch,
    get_project_dir,
    read_hook_input,
)

_GENERIC_DANGEROUS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("rm -rf /", re.compile(r"\brm\s+-[rRf]{2,3}\s+/(?=\s|$|;|&|\|)")),
    ("rm -rf ~", re.compile(r"\brm\s+-[rRf]{2,3}\s+~")),
    ("rm -rf /*", re.compile(r"\brm\s+-[rRf]{2,3}\s+/\*")),
    ("dd to raw device", re.compile(r"\bdd\s+.*\bof=/dev/[sh]d[a-z]")),
    ("mkfs", re.compile(r"\bmkfs\.")),
    ("chmod 777 /", re.compile(r"\bchmod\s+(-[rRf]+\s+)?777\s+/(?=\s|$|;|&|\|)")),
    ("write to /dev/sd*", re.compile(r">\s*/dev/[sh]d[a-z]")),
    ("curl | sh", re.compile(r"\bcurl\b[^|\n]*\|\s*(bash|sh|zsh)\b")),
    ("wget | sh", re.compile(r"\bwget\b[^|\n]*\|\s*(bash|sh|zsh)\b")),
    ("fork bomb", re.compile(r":\s*\(\s*\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:")),
    ("Windows format c:", re.compile(r"\bformat\s+[cdefgh]:", re.IGNORECASE)),
    ("DROP DATABASE", re.compile(r"\bDROP\s+(DATABASE|TABLE)\b", re.IGNORECASE)),
    ("TRUNCATE TABLE", re.compile(r"\bTRUNCATE\s+TABLE\b", re.IGNORECASE)),
)

_GIT_RESET_HARD = re.compile(r"\bgit\s+reset\s+--hard\b")


def _check_protected_reset(command: str) -> str | None:
    if not _GIT_RESET_HARD.search(command):
        return None
    branch = get_current_branch(get_project_dir())
    if branch in PROTECTED_BRANCHES:
        return f"git reset --hard on protected branch '{branch}'"
    return None


def _check_generic(command: str) -> str | None:
    for label, pattern in _GENERIC_DANGEROUS:
        if pattern.search(command):
            return label
    return None


def main() -> int:
    data = read_hook_input()
    if str(data.get("tool_name", "")) != "Bash":
        return 0

    tool_input = data.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return 0

    command = tool_input.get("command")
    if not isinstance(command, str) or not command.strip():
        return 0

    found = _check_generic(command) or _check_protected_reset(command)
    if found:
        truncated = command if len(command) < 120 else command[:117] + "..."
        print(
            f"[dangerous_command_block] refusing Bash — matched pattern '{found}'. "
            f"Command: {truncated}",
            file=sys.stderr,
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
