"""Cross-hook telemetry emission.

Phase 2 shared module. Hooks (and eventually agents via a CLI
wrapper) call :func:`emit` or :func:`emit_many` to append JSONL
records to a date-rotated telemetry log under
``<project>/.claude/telemetry/<YYYY-MM-DD>.jsonl``.

Writes are concurrency-safe via ``portalocker`` sidecar locks —
two hooks firing simultaneously cannot interleave mid-record.
Failures never raise and never block the caller; an I/O problem
logs to stderr and returns silently. Telemetry is observability,
not control flow.

The category field accepts short kebab-case identifiers
(``hook-failure``, ``stamp-write``, ``tier-violation``, etc.).
It is the primary index readers filter on.

Event: N/A (shared module, not a hook)
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hooks._hook_shared import get_project_dir
from hooks._os_safe import locked_open

_CATEGORY_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _telemetry_dir() -> Path:
    """Resolve the telemetry directory. ``CLAUDE_TELEMETRY_DIR`` overrides."""
    override = os.environ.get("CLAUDE_TELEMETRY_DIR")
    if override:
        return Path(override).resolve()
    return get_project_dir() / ".claude" / "telemetry"


def _log_path_for(now: datetime) -> Path:
    return _telemetry_dir() / f"{now.strftime('%Y-%m-%d')}.jsonl"


def _build_record(category: str, data: dict[str, Any], *, now: datetime) -> dict[str, Any]:
    return {
        "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "category": category,
        "data": data,
    }


def _append_lines(path: Path, lines: list[str]) -> None:
    """Append ``lines`` to ``path`` under a sidecar portalocker lock.

    Each entry already ends with ``\\n``; we concatenate and write once,
    which keeps the append atomic from the filesystem's perspective —
    readers scanning mid-write see either the full batch or none of it.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    if not lock_path.exists():
        lock_path.touch()

    with locked_open(lock_path, "r+", timeout=10.0), path.open("a", encoding="utf-8") as fh:
        fh.write("".join(lines))


def emit(category: str, data: dict[str, Any]) -> None:
    """Append one telemetry record. Silent on I/O failure.

    Args:
        category: Short kebab-case identifier. Rejected if it contains
            path separators or does not match ``^[a-z0-9][a-z0-9-]*$``.
        data: JSON-serialisable dict of event-specific fields.
    """
    if not _CATEGORY_RE.match(category):
        print(f"[telemetry] refusing invalid category: {category!r}", file=sys.stderr)
        return

    now = datetime.now(UTC)
    record = _build_record(category, data, now=now)
    try:
        line = json.dumps(record, sort_keys=True) + "\n"
    except (TypeError, ValueError) as exc:
        print(f"[telemetry] record not JSON-serialisable: {exc}", file=sys.stderr)
        return

    path = _log_path_for(now)
    try:
        _append_lines(path, [line])
    except OSError as exc:
        print(f"[telemetry] could not write: {exc}", file=sys.stderr)


def emit_many(category: str, records: list[dict[str, Any]]) -> None:
    """Append many records atomically under a single lock.

    All records share the same ``category`` and the same millisecond-
    precision timestamp (the lock window). Callers that need per-record
    timestamps should call :func:`emit` in a loop instead — the
    atomic-batch guarantee here trades per-record timing for concurrency
    safety.
    """
    if not records:
        return
    if not _CATEGORY_RE.match(category):
        print(f"[telemetry] refusing invalid category: {category!r}", file=sys.stderr)
        return

    now = datetime.now(UTC)
    lines: list[str] = []
    for data in records:
        record = _build_record(category, data, now=now)
        try:
            lines.append(json.dumps(record, sort_keys=True) + "\n")
        except (TypeError, ValueError) as exc:
            print(f"[telemetry] record not JSON-serialisable: {exc}", file=sys.stderr)
            return

    path = _log_path_for(now)
    try:
        _append_lines(path, lines)
    except OSError as exc:
        print(f"[telemetry] could not write: {exc}", file=sys.stderr)
