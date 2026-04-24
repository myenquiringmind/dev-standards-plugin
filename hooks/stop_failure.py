"""Record a ULID-keyed incident whenever CC fires a StopFailure event.

Sibling to ``post_tool_failure`` — both are observability recorders that
never block, never raise, and produce a durable trail the Phase 4
closed-loop agents later consume. The split:

- ``post_tool_failure`` → rolling in-memory log for the *current* session
  (quick-glance debugging breadcrumbs, capped at 50 entries).
- ``stop_failure`` → append-only ``.claude/incidents/<YYYY-MM>/INC-<ulid>.jsonl``
  record meant to survive the session (incident-retrospective input).

A StopFailure event only fires when CC itself is unable to cleanly
complete the Stop handshake — API error, tool-run exception, unhandled
exit. Those are exactly the failures the Phase 4 ``incident-retrospective``
agent is designed to cluster into prompt/rule PRs, so the record needs to
persist beyond the session that produced it.

Never blocks. Always exits 0. ``_incident.write_incident`` silently
swallows I/O failures per its own contract; this hook does not add a
second error-handling layer.

Event: StopFailure
Matcher: *
"""

from __future__ import annotations

import sys

from hooks._hook_shared import read_hook_input
from hooks._incident import write_incident

_DETAIL_CANDIDATE_KEYS: tuple[str, ...] = ("error", "reason", "message", "detail")
_EXTRA_CANDIDATE_KEYS: tuple[str, ...] = (
    "session_id",
    "transcript_path",
    "error_type",
    "stop_reason",
    "exit_code",
)
_DEFAULT_DETAIL: str = "CC StopFailure event fired without a reported reason"


def _extract_detail(data: dict[str, object]) -> str:
    """Pull the most specific human-readable summary CC gave us."""
    for key in _DETAIL_CANDIDATE_KEYS:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return _DEFAULT_DETAIL


def _extract_extra(data: dict[str, object]) -> dict[str, str | int]:
    """Filter the hook payload to JSON-serialisable scalar context fields."""
    extra: dict[str, str | int] = {}
    for key in _EXTRA_CANDIDATE_KEYS:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            extra[key] = value.strip()
        elif isinstance(value, int) and not isinstance(value, bool):
            extra[key] = value
    return extra


def main() -> int:
    data = read_hook_input()
    detail = _extract_detail(data)
    extra = _extract_extra(data)
    write_incident("stop-failure", detail, severity="error", **extra)
    return 0


if __name__ == "__main__":
    sys.exit(main())
