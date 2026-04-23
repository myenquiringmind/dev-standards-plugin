"""Runtime enforcement of R/R/W tier restrictions on tool use.

Complements the static ``allOf`` check in
``schemas/agent-frontmatter.schema.json``. The schema blocks a
``read`` or ``reason`` tier agent from *declaring* Edit/Write in
its tools list; this hook blocks such an agent from *invoking*
Edit/Write at runtime — even if the agent file somehow slipped
past schema validation (an overlay, a stale registry, a manual
edit).

When a PreToolUse event fires inside a subagent context, CC
includes the calling subagent's ``agent_type`` field in the hook
payload. We look the agent up in ``config/graph-registry.json``
and, if its declared tier is ``read`` or ``reason``, block any
mutating tool (Edit / Write / MultiEdit / NotebookEdit).

Main-thread tool calls (no ``agent_type`` in payload) pass
through unchanged — the framework's R/R/W model only applies to
subagents.

Event: PreToolUse
Matcher: Edit|Write|MultiEdit|NotebookEdit
"""

from __future__ import annotations

import sys

from hooks._graph import find_node, load_registry
from hooks._hook_shared import read_hook_input

_MUTATING_TOOLS: frozenset[str] = frozenset({"Edit", "Write", "MultiEdit", "NotebookEdit"})
_READ_ONLY_TIERS: frozenset[str] = frozenset({"read", "reason"})


def main() -> int:
    data = read_hook_input()

    tool_name = str(data.get("tool_name", ""))
    if tool_name not in _MUTATING_TOOLS:
        return 0

    agent_type = data.get("agent_type")
    if not isinstance(agent_type, str) or not agent_type:
        # Main-thread tool use. The framework does not police user tool calls.
        return 0

    registry = load_registry()
    if not registry.get("nodes"):
        # No registry (fresh repo, pre-build). Phase 2 is fail-open here:
        # registry absence is itself a tier-3 problem for the author to fix,
        # not a reason to block everyday work.
        return 0

    node = find_node(registry, agent_type)
    if node is None:
        # Subagent not registered. Could be an in-progress scaffold, an
        # overlay, or a manual invocation. Fail-open for the same reason
        # as above — silently let it through; the graph-registry-validator
        # is the right gate for "node without file".
        return 0

    metadata = node.get("metadata") if isinstance(node, dict) else None
    tier = metadata.get("tier") if isinstance(metadata, dict) else None

    if tier in _READ_ONLY_TIERS:
        print(
            f"[tier_enforcer] refusing {tool_name} — subagent '{agent_type}' is "
            f"tier: {tier}. Read/reason tier agents cannot mutate files. "
            f"Route the write through a write-tier agent, or escalate via "
            f"`AskUserQuestion` if the tier assignment itself is wrong.",
            file=sys.stderr,
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
