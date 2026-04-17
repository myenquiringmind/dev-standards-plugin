"""Block Edit/Write/MultiEdit when HEAD is on a protected branch.

The framework rule: never commit directly to master (or main, or
any configured production branch). This hook enforces the discipline
at the tool-use layer — refusing the edit before it lands on disk.

Exit 2 with a message that prints the required remediation: cut a
feature branch. Any other branch (including detached HEAD) is
allowed.

Event: PreToolUse
Matcher: Edit|Write|MultiEdit
"""

from __future__ import annotations

import sys

from hooks._hook_shared import (
    PROTECTED_BRANCHES,
    get_current_branch,
    get_project_dir,
    read_hook_input,
)

_EDIT_TOOLS: frozenset[str] = frozenset({"Edit", "Write", "MultiEdit"})


def main() -> int:
    data = read_hook_input()
    tool_name = str(data.get("tool_name", ""))

    if tool_name not in _EDIT_TOOLS:
        return 0

    branch = get_current_branch(get_project_dir())
    if branch in PROTECTED_BRANCHES:
        print(
            f"[branch_protection] refusing {tool_name} on protected branch '{branch}'. "
            f"Cut a feature branch first: git checkout -b feat/<category>-<slug>",
            file=sys.stderr,
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
