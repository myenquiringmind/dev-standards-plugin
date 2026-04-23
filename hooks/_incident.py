"""Per-incident append-only JSONL log with ULID-keyed correlation.

Phase 2 shared module. Differs from ``_telemetry.py`` on three
axes:

1. **Scope.** Telemetry is high-volume observability (every hook
   firing, every stamp write). Incidents are low-volume
   escalations — a failed commit gate, a stop with uncommitted
   changes, a manual ``AskUserQuestion``.
2. **Correlation.** Every incident gets a ULID at creation. Later
   records (resolution, additional context, follow-up failures)
   append to the same file so the whole incident reads top-to-
   bottom as one narrative.
3. **Persistence model.** One file per incident, not one file per
   day. Grouped into month-subdirectories so listings stay
   manageable: ``.claude/incidents/<YYYY-MM>/INC-<ulid>.jsonl``.

Never raises. Never blocks. I/O failure logs to stderr and
returns an empty string (for ``write_incident``) or ``None`` (for
``append_to_incident``).

Event: N/A (shared module, not a hook)
"""

from __future__ import annotations

import json
import os
import re
import secrets
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hooks._hook_shared import get_project_dir
from hooks._os_safe import locked_open

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_CATEGORY_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_SEVERITY_VALUES: frozenset[str] = frozenset({"error", "warn", "info"})
_ULID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")


def _generate_ulid() -> str:
    """Generate a 26-char Crockford-base32 ULID."""
    ms = int(time.time() * 1000) & ((1 << 48) - 1)
    rand = secrets.randbits(80)

    chars: list[str] = []
    # 48-bit timestamp, padded to 50 bits (10 base32 chars).
    for i in range(9, -1, -1):
        chars.append(_CROCKFORD[(ms >> (i * 5)) & 0x1F])
    # 80-bit randomness (16 base32 chars).
    for i in range(15, -1, -1):
        chars.append(_CROCKFORD[(rand >> (i * 5)) & 0x1F])
    return "".join(chars)


def _incidents_dir() -> Path:
    """Resolve the incidents root directory. ``CLAUDE_INCIDENTS_DIR`` overrides."""
    override = os.environ.get("CLAUDE_INCIDENTS_DIR")
    if override:
        return Path(override).resolve()
    return get_project_dir() / ".claude" / "incidents"


def _incident_path(ulid: str, when: datetime) -> Path:
    month_dir = _incidents_dir() / when.strftime("%Y-%m")
    return month_dir / f"INC-{ulid}.jsonl"


def _find_incident_file(ulid: str) -> Path | None:
    """Locate an existing incident file by ULID. Returns ``None`` if not found."""
    root = _incidents_dir()
    if not root.is_dir():
        return None
    filename = f"INC-{ulid}.jsonl"
    for month_dir in sorted(root.iterdir()):
        if not month_dir.is_dir():
            continue
        candidate = month_dir / filename
        if candidate.is_file():
            return candidate
    return None


def _append_line(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    if not lock_path.exists():
        lock_path.touch()
    with locked_open(lock_path, "r+", timeout=10.0), path.open("a", encoding="utf-8") as fh:
        fh.write(line)


def write_incident(
    category: str,
    detail: str,
    *,
    severity: str = "error",
    **extra: Any,
) -> str:
    """Create a new incident file and write the opening record.

    Args:
        category: Short kebab-case identifier (``^[a-z0-9][a-z0-9-]*$``).
        detail: Human-readable summary. Required; empty string rejected.
        severity: ``"error"`` (default), ``"warn"``, or ``"info"``.
        **extra: JSON-serialisable per-incident fields stored under ``extra``.

    Returns:
        The new ULID on success, empty string on any failure (invalid
        input, serialisation error, I/O error).
    """
    if not _CATEGORY_RE.match(category):
        print(f"[incident] refusing invalid category: {category!r}", file=sys.stderr)
        return ""
    if severity not in _SEVERITY_VALUES:
        print(f"[incident] refusing invalid severity: {severity!r}", file=sys.stderr)
        return ""
    if not detail.strip():
        print("[incident] refusing empty detail", file=sys.stderr)
        return ""

    ulid = _generate_ulid()
    now = datetime.now(UTC)
    record = {
        "ulid": ulid,
        "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "category": category,
        "severity": severity,
        "detail": detail,
        "extra": dict(extra),
    }
    try:
        line = json.dumps(record, sort_keys=True) + "\n"
    except (TypeError, ValueError) as exc:
        print(f"[incident] record not JSON-serialisable: {exc}", file=sys.stderr)
        return ""

    path = _incident_path(ulid, now)
    try:
        _append_line(path, line)
    except OSError as exc:
        print(f"[incident] could not write: {exc}", file=sys.stderr)
        return ""
    return ulid


def append_to_incident(
    ulid: str,
    detail: str,
    *,
    severity: str = "info",
    **extra: Any,
) -> bool:
    """Append a follow-up record to an existing incident.

    Args:
        ulid: The 26-char Crockford-base32 ULID of the incident.
        detail: Human-readable follow-up note.
        severity: ``"error"``, ``"warn"``, or ``"info"`` (default).
        **extra: Additional fields for this record (stored under ``extra``).

    Returns:
        ``True`` on success, ``False`` on any failure (bad ULID,
        missing incident, I/O error).
    """
    if not _ULID_RE.match(ulid):
        print(f"[incident] refusing invalid ulid: {ulid!r}", file=sys.stderr)
        return False
    if severity not in _SEVERITY_VALUES:
        print(f"[incident] refusing invalid severity: {severity!r}", file=sys.stderr)
        return False
    if not detail.strip():
        print("[incident] refusing empty detail", file=sys.stderr)
        return False

    path = _find_incident_file(ulid)
    if path is None:
        print(f"[incident] no incident file for ulid {ulid}", file=sys.stderr)
        return False

    now = datetime.now(UTC)
    record = {
        "ulid": ulid,
        "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "severity": severity,
        "detail": detail,
        "extra": dict(extra),
    }
    try:
        line = json.dumps(record, sort_keys=True) + "\n"
    except (TypeError, ValueError) as exc:
        print(f"[incident] record not JSON-serialisable: {exc}", file=sys.stderr)
        return False

    try:
        _append_line(path, line)
    except OSError as exc:
        print(f"[incident] could not append: {exc}", file=sys.stderr)
        return False
    return True
