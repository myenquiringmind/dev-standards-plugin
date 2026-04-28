"""Record an incident when CC reports a PermissionDenied event.

Sibling to ``stop_failure``. Both wrap ``_incident.write_incident``
to produce one append-only ``.claude/incidents/<YYYY-MM>/INC-<ulid>.jsonl``
record per failure event. The split:

- ``stop_failure`` → CC could not complete the Stop handshake.
- ``permission_denied`` → a tool call was rejected by user
  permission policy (allowlist miss, ``deny`` rule, manual deny).

The PermissionDenied trail is one of three Phase 4 ``incident-
retrospective-analyst`` inputs (the other two being ``stop_failure``
and ``post_tool_failure``). Clusters of denials on the same tool
or the same path drive the proposal of allowlist diffs.

Detail resolution: ``error`` → ``reason`` → ``message`` → ``detail``.
Extras: ``tool_name`` plus a small whitelist of identifying fields
from ``tool_input`` (``file_path``, ``command``, ``path``, ``url``,
``pattern``), plus ``session_id`` / ``transcript_path`` if present.
``bool`` is excluded from int extras (matches the ``stop_failure``
guard against ``True`` being recorded as an exit code).

Never blocks. Always exits 0.

Event: PermissionDenied
Matcher: *
"""

from __future__ import annotations

import sys
from typing import Any

from hooks._hook_shared import read_hook_input
from hooks._incident import write_incident

_DETAIL_CANDIDATE_KEYS: tuple[str, ...] = ("error", "reason", "message", "detail")

_TOOL_INPUT_FIELDS: tuple[str, ...] = (
    "file_path",
    "command",
    "path",
    "url",
    "pattern",
)

_TOP_LEVEL_EXTRA_FIELDS: tuple[str, ...] = (
    "tool_name",
    "session_id",
    "transcript_path",
)

_DEFAULT_DETAIL: str = "CC PermissionDenied event fired without a reported reason"


def _extract_detail(data: dict[str, object]) -> str:
    """Pull the most specific human-readable summary CC gave us."""
    for key in _DETAIL_CANDIDATE_KEYS:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return _DEFAULT_DETAIL


def _extract_extra(data: dict[str, object]) -> dict[str, str | int]:
    """Filter to JSON-safe scalars from a known whitelist of fields."""
    extra: dict[str, str | int] = {}

    for key in _TOP_LEVEL_EXTRA_FIELDS:
        _add_scalar(extra, key, data.get(key))

    tool_input = data.get("tool_input")
    if isinstance(tool_input, dict):
        for key in _TOOL_INPUT_FIELDS:
            _add_scalar(extra, key, tool_input.get(key))

    return extra


def _add_scalar(target: dict[str, str | int], key: str, value: Any) -> None:
    """Add *value* to *target* if it is a non-empty string or non-bool int."""
    if isinstance(value, str) and value.strip():
        target[key] = value.strip()
    elif isinstance(value, int) and not isinstance(value, bool):
        target[key] = value


def main() -> int:
    data = read_hook_input()
    detail = _extract_detail(data)
    extra = _extract_extra(data)
    write_incident("permission-denied", detail, severity="warn", **extra)
    return 0


if __name__ == "__main__":
    sys.exit(main())
