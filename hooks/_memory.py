"""Framework-memory directory resolution.

Phase 4 shared module. Provides path helpers for the canonical
framework memory tier under ``${CLAUDE_PLUGIN_DATA}/framework-memory/``,
mirroring :func:`hooks._session_state_common.get_memory_dir` for the
project/session tiers and :func:`hooks.write_agent_memory._resolve_memory_root`
for the agent tier.

The framework tier holds:

* ``incidents/<YYYY-MM>/INC-<ulid>.jsonl`` — incident log written by
  ``_incident.py`` (Phase 2).
* ``telemetry/<YYYY-MM-DD>.jsonl`` — rotating telemetry written by
  ``_telemetry.py`` (Phase 2).
* ``graph-history/<ISO>.json`` — graph-registry snapshots (Phase 4
  stream 3, ``file_changed.py`` extension).
* ``quality-scores.json`` — per-agent precision / latency / cost
  written by ``closed-loop-quality-scorer`` (Phase 4 stream 4).
* ``principles/`` and ``retrospectives/`` — reserved for Phase 10
  ``closed-loop-knowledge-compactor`` and
  ``closed-loop-incident-retrospective-analyst``; Phase 4 does not
  populate them but reserves the names so the directory layout is
  stable across phases.

Resolution priority (matches ``write_agent_memory._resolve_memory_root``):

1. ``$CLAUDE_PLUGIN_DATA/framework-memory``
2. ``$CLAUDE_PROJECT_DIR/.claude/framework-memory``
3. ``<get_project_dir()>/.claude/framework-memory``

The per-subdirectory env var overrides (``CLAUDE_INCIDENTS_DIR``,
``CLAUDE_TELEMETRY_DIR``) carry forward for backwards compatibility
with the Phase 2 modules and their test fixtures — :func:`incident_dir`
and :func:`telemetry_dir` honour them before falling back to the
canonical layout under :func:`framework_memory_dir`.

Event: N/A (shared module, not a hook)
"""

from __future__ import annotations

import os
from pathlib import Path

from hooks._hook_shared import get_project_dir


def framework_memory_dir() -> Path:
    """Resolve the canonical framework memory root.

    Returns:
        Absolute ``Path`` to the framework memory directory. May not
        yet exist; ``session_start_framework_memory.py`` ensures the
        tree is created on each session start.
    """
    plugin = os.environ.get("CLAUDE_PLUGIN_DATA")
    if plugin:
        return Path(plugin).resolve() / "framework-memory"
    project_env = os.environ.get("CLAUDE_PROJECT_DIR")
    if project_env:
        return Path(project_env).resolve() / ".claude" / "framework-memory"
    return get_project_dir() / ".claude" / "framework-memory"


def incident_dir() -> Path:
    """Resolve the incidents directory.

    ``CLAUDE_INCIDENTS_DIR`` overrides for backwards compatibility
    with :mod:`hooks._incident` and its test fixtures. When unset,
    returns ``framework_memory_dir() / "incidents"``.
    """
    override = os.environ.get("CLAUDE_INCIDENTS_DIR")
    if override:
        return Path(override).resolve()
    return framework_memory_dir() / "incidents"


def telemetry_dir() -> Path:
    """Resolve the telemetry directory.

    ``CLAUDE_TELEMETRY_DIR`` overrides for backwards compatibility
    with :mod:`hooks._telemetry` and its test fixtures. When unset,
    returns ``framework_memory_dir() / "telemetry"``.
    """
    override = os.environ.get("CLAUDE_TELEMETRY_DIR")
    if override:
        return Path(override).resolve()
    return framework_memory_dir() / "telemetry"


def graph_history_dir() -> Path:
    """Resolve the graph-history snapshot directory.

    Phase 4 stream 3 (``file_changed.py`` extension) snapshots
    ``config/graph-registry.json`` here on every change. No env var
    override — graph history is always under the canonical root.
    """
    return framework_memory_dir() / "graph-history"


def quality_scores_path() -> Path:
    """Resolve the per-agent quality-scores file path.

    Phase 4 stream 4 (``closed-loop-quality-scorer``) writes its
    aggregate scores here. No env var override — the path is always
    under the canonical root.
    """
    return framework_memory_dir() / "quality-scores.json"


def all_subdirs() -> tuple[Path, ...]:
    """Return every subdirectory the framework-memory tree owns.

    Used by ``session_start_framework_memory.py`` to ensure the
    full tree exists at session start. Reserves ``principles/`` and
    ``retrospectives/`` for Phase 10 even though Phase 4 does not
    populate them — the directories are cheap and the layout
    contract is stable across phases.
    """
    return (
        incident_dir(),
        telemetry_dir(),
        graph_history_dir(),
        framework_memory_dir() / "principles",
        framework_memory_dir() / "retrospectives",
    )
