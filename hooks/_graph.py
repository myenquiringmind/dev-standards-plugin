"""Read-side helpers for ``config/graph-registry.json``.

Phase 2 shared module. Consumers — `file_changed`, `config_change`,
and any hook that walks component relationships — use these helpers
to query the registry without re-implementing the JSON lookup boilerplate.

Paired with ``scripts/build_graph_registry.py`` (the producer).
This module never writes the registry; writes flow through the build
script so the `generated_at` timestamp stays authoritative.

Never raises on query helpers — missing nodes or edges return an empty
result, not an exception. The caller decides whether absence is an error.

Event: N/A (shared module, not a hook)
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from hooks._hook_shared import get_project_dir

_EMPTY_REGISTRY: dict[str, Any] = {
    "version": "0.0.0",
    "generated_at": "1970-01-01T00:00:00Z",
    "nodes": [],
    "edges": [],
}


def load_registry(root: Path | None = None) -> dict[str, Any]:
    """Load ``config/graph-registry.json`` from the project root.

    Returns an empty-registry stub on missing file or malformed JSON,
    never raises. Callers that require a real registry should check
    ``len(registry["nodes"])`` after the call.
    """
    base = root if root is not None else get_project_dir()
    path = base / "config" / "graph-registry.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError) as exc:
        print(f"[graph] registry not readable at {path}: {exc}", file=sys.stderr)
        return dict(_EMPTY_REGISTRY)
    except json.JSONDecodeError as exc:
        print(f"[graph] registry JSON malformed: {exc}", file=sys.stderr)
        return dict(_EMPTY_REGISTRY)

    if not isinstance(data, dict) or "nodes" not in data or "edges" not in data:
        print("[graph] registry shape invalid (missing nodes/edges)", file=sys.stderr)
        return dict(_EMPTY_REGISTRY)
    return data


def find_node(registry: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    """Return the node with the given id, or None if absent."""
    for node in registry.get("nodes", []):
        if isinstance(node, dict) and node.get("id") == node_id:
            return node
    return None


def nodes_by_type(registry: dict[str, Any], node_type: str) -> list[dict[str, Any]]:
    """Return every node whose ``type`` matches."""
    return [
        node
        for node in registry.get("nodes", [])
        if isinstance(node, dict) and node.get("type") == node_type
    ]


def find_edges_from(
    registry: dict[str, Any],
    node_id: str,
    *,
    edge_type: str | None = None,
) -> list[dict[str, Any]]:
    """Edges whose ``from`` matches ``node_id``, optionally filtered by type."""
    return [
        edge
        for edge in registry.get("edges", [])
        if isinstance(edge, dict)
        and edge.get("from") == node_id
        and (edge_type is None or edge.get("type") == edge_type)
    ]


def find_edges_to(
    registry: dict[str, Any],
    node_id: str,
    *,
    edge_type: str | None = None,
) -> list[dict[str, Any]]:
    """Edges whose ``to`` matches ``node_id``, optionally filtered by type."""
    return [
        edge
        for edge in registry.get("edges", [])
        if isinstance(edge, dict)
        and edge.get("to") == node_id
        and (edge_type is None or edge.get("type") == edge_type)
    ]


def topological_sort(
    registry: dict[str, Any],
    edge_type: str,
) -> list[str] | None:
    """Return node ids in topological order along edges of ``edge_type``.

    Edges of other types are ignored. Nodes without any edge of
    ``edge_type`` appear in the result too (as isolated vertices).

    Returns ``None`` if a cycle is detected. Errors are logged to
    stderr; the caller decides how to handle.
    """
    node_ids: set[str] = {
        node["id"]
        for node in registry.get("nodes", [])
        if isinstance(node, dict) and isinstance(node.get("id"), str)
    }

    edges_typed = [
        edge
        for edge in registry.get("edges", [])
        if isinstance(edge, dict) and edge.get("type") == edge_type
    ]

    successors: dict[str, list[str]] = defaultdict(list)
    in_degree: dict[str, int] = dict.fromkeys(node_ids, 0)
    for edge in edges_typed:
        frm = edge.get("from")
        to = edge.get("to")
        if not isinstance(frm, str) or not isinstance(to, str):
            continue
        if frm not in node_ids or to not in node_ids:
            continue
        successors[frm].append(to)
        in_degree[to] = in_degree.get(to, 0) + 1

    queue: deque[str] = deque(sorted(nid for nid, deg in in_degree.items() if deg == 0))
    result: list[str] = []
    while queue:
        current = queue.popleft()
        result.append(current)
        for nxt in sorted(successors.get(current, [])):
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0:
                queue.append(nxt)

    if len(result) != len(node_ids):
        cycle_nodes = sorted(nid for nid, deg in in_degree.items() if deg > 0)
        print(
            f"[graph] cycle detected on edge_type='{edge_type}' involving {cycle_nodes[:5]}",
            file=sys.stderr,
        )
        return None
    return result
