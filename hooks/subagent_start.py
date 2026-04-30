"""Emit a SubagentStart telemetry record naming the agent and its budget.

Fires when CC invokes a subagent. The hook does two things, both
observability-only:

1. Look up the subagent's declared ``maxTurns`` in
   ``config/graph-registry.json`` (loaded via ``_graph.load_registry``)
   so the budget travels into the telemetry record alongside the
   start event.
2. Emit a ``subagent-start`` telemetry record with the agent name,
   the registry-declared budget, and the CC-supplied session and
   transcript IDs.

This is the "tracker + cascade propagator" pair from the Phase 2
spec, narrowed to the observability layer:

- **Tracker**: the start record is the durable ground truth that
  Phase 4's ``closed-loop-quality-scorer`` correlates against
  subsequent ``stop_failure`` / ``post_tool_failure`` /
  ``permission_denied`` records to compute per-agent precision /
  recall / cost.
- **Cascade propagator**: ``max_turns`` is recorded so downstream
  consumers can see what the contracted ceiling was without
  re-loading the registry. Active runtime enforcement (block when
  N turns elapsed) needs a runtime turn count the hook layer does
  not currently have; that lives at the orchestrator / agent layer
  and arrives in Phase 4.

Never networks. Never blocks. Always exits 0.
``_telemetry.emit`` swallows I/O failures internally.

Event: SubagentStart
Matcher: *
"""

from __future__ import annotations

import sys
from typing import Any

from hooks._graph import find_node, load_registry
from hooks._hook_shared import read_hook_input
from hooks._telemetry import emit


def _extract_agent_name(data: dict[str, object]) -> str:
    """Pull the subagent's identifier from the first matching field."""
    for key in ("agent_type", "agent_name", "subagent_type", "name"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _extract_string(data: dict[str, object], key: str) -> str:
    value = data.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return ""


def _max_turns_for(agent_name: str) -> int | None:
    """Look up ``metadata.maxTurns`` for *agent_name*, or ``None`` if absent."""
    if not agent_name:
        return None
    registry = load_registry()
    if not registry.get("nodes"):
        return None
    node = find_node(registry, agent_name)
    if node is None or not isinstance(node, dict):
        return None
    metadata = node.get("metadata")
    if not isinstance(metadata, dict):
        return None
    value = metadata.get("maxTurns")
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def main() -> int:
    data = read_hook_input()

    agent_name = _extract_agent_name(data)
    record: dict[str, Any] = {
        "agent": agent_name,
        "max_turns": _max_turns_for(agent_name),
        "session_id": _extract_string(data, "session_id"),
        "transcript_path": _extract_string(data, "transcript_path"),
    }
    emit("subagent-start", record)
    return 0


if __name__ == "__main__":
    sys.exit(main())
