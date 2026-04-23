"""Runtime gate for Bash invocations from read/reason-tier subagents.

Companion to ``pre_tool_use_tier_enforcer.py``. The enforcer blocks
mutating *file-tools* (Edit/Write/MultiEdit/NotebookEdit). This hook
blocks mutating *Bash commands* — because a read-tier agent can sneak
around the file-tool gate by running ``echo x > foo`` or ``rm -rf .``
through Bash.

Strategy: for each segment of the command (split on ``&&``, ``||``,
``;``, ``|``, ``&``), the first token must be in the read-only
allowlist. ``git`` is special-cased — its sub-verb must be in the
git-read allowlist (``git status`` ok, ``git push`` blocked).

The allowlist is intentionally tight. Agents that need a verb outside
it should escalate via ``AskUserQuestion`` — adding to the allowlist
is a deliberate choice, not a default. False positives are preferable
to false negatives here.

Fail-open contracts (consistent with the enforcer):
- No ``agent_type`` in payload → main-thread call, pass.
- Empty/missing registry → pre-build state, pass.
- Agent not registered → overlay or scaffold, pass.
- Agent tier not in {read, reason} → out of scope, pass.

Event: PreToolUse
Matcher: Bash
"""

from __future__ import annotations

import re
import shlex
import sys

from hooks._graph import find_node, load_registry
from hooks._hook_shared import read_hook_input

_READ_ONLY_TIERS: frozenset[str] = frozenset({"read", "reason"})

#: Bare program names a read-tier agent may invoke via Bash.
_BASH_READ_ALLOWLIST: frozenset[str] = frozenset(
    {
        # Filesystem inspection
        "ls",
        "pwd",
        "cat",
        "head",
        "tail",
        "wc",
        "file",
        "stat",
        "find",
        "tree",
        "du",
        "df",
        # Search
        "grep",
        "egrep",
        "fgrep",
        "rg",
        # Structured data (read-side; sed/awk in-place flags are not validated,
        # so they are deliberately excluded)
        "jq",
        "yq",
        "awk",
        # Shell introspection
        "which",
        "where",
        "type",
        "command",
        "echo",
        "printf",
        "env",
        "true",
        "false",
        # Git — sub-verb checked separately
        "git",
    }
)

#: Git sub-verbs that do not mutate the working tree, refs, or remotes.
_GIT_READ_VERBS: frozenset[str] = frozenset(
    {
        "status",
        "log",
        "diff",
        "show",
        "branch",
        "rev-parse",
        "remote",
        "describe",
        "ls-files",
        "ls-tree",
        "ls-remote",
        "blame",
        "cat-file",
        "shortlog",
        "tag",
        "for-each-ref",
        "reflog",
        "stash",
        "config",
        "help",
        "version",
        "rev-list",
        "show-ref",
        "name-rev",
    }
)

#: Shell operators that delimit independently-evaluated command segments.
_SEGMENT_SPLIT = re.compile(r"\s*(?:&&|\|\||;|\||&)\s*")


def _is_segment_allowed(segment: str) -> tuple[bool, str]:
    """Return (allowed, offending_token).

    ``offending_token`` is empty when allowed; otherwise it is the token
    that triggered the block (for the stderr message).
    """
    segment = segment.strip()
    if not segment:
        return True, ""

    try:
        tokens = shlex.split(segment, posix=True)
    except ValueError:
        # Unbalanced quotes etc. Block — better safe than sorry.
        return False, segment

    if not tokens:
        return True, ""

    program = tokens[0]
    # Strip a leading path so /usr/bin/git is treated as git.
    program = program.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]

    if program not in _BASH_READ_ALLOWLIST:
        return False, program

    if program == "git":
        if len(tokens) < 2:
            # Bare ``git`` prints help — read-only.
            return True, ""
        verb = tokens[1]
        if verb not in _GIT_READ_VERBS:
            return False, f"git {verb}"

    return True, ""


def main() -> int:
    data = read_hook_input()

    tool_name = str(data.get("tool_name", ""))
    if tool_name != "Bash":
        return 0

    agent_type = data.get("agent_type")
    if not isinstance(agent_type, str) or not agent_type:
        # Main-thread Bash call. The framework does not police user tool calls.
        return 0

    registry = load_registry()
    if not registry.get("nodes"):
        return 0

    node = find_node(registry, agent_type)
    if node is None:
        return 0

    metadata = node.get("metadata") if isinstance(node, dict) else None
    tier = metadata.get("tier") if isinstance(metadata, dict) else None

    if tier not in _READ_ONLY_TIERS:
        return 0

    tool_input = data.get("tool_input")
    command = ""
    if isinstance(tool_input, dict):
        raw_command = tool_input.get("command", "")
        if isinstance(raw_command, str):
            command = raw_command

    if not command.strip():
        # No command to evaluate — pass.
        return 0

    for segment in _SEGMENT_SPLIT.split(command):
        allowed, offending = _is_segment_allowed(segment)
        if not allowed:
            print(
                f"[bash_tier_guard] refusing Bash — subagent '{agent_type}' is "
                f"tier: {tier}. Command segment '{offending}' is not in the "
                f"read-only allowlist. Read/reason tier agents may only run "
                f"inspection commands (git status/log/diff, ls, cat, grep, jq, "
                f"find, etc.). Route mutating commands through a write-tier "
                f"agent, or escalate via `AskUserQuestion` if the tier is wrong.",
                file=sys.stderr,
            )
            return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
