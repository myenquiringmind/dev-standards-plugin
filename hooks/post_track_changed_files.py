"""Append every edited file path to an in-session change log.

Fires after every Edit/Write/MultiEdit. Records one tab-separated
line per qualifying tool call to ``<memory>/changed-files.log``:

    <ISO-8601 UTC timestamp>\\t<tool_name>\\t<absolute file path>

The log feeds two consumers:

- The orchestrator (Phase 4+) reads it to derive the touched-files
  set without re-scraping the transcript.
- A restored session can replay it to rebuild the ``Files Modified``
  section of ``session-state.md`` if the transcript is unavailable.

Append-only. Never deduplicates — repeat edits to one file produce
multiple lines, preserving the timeline. Consumers dedupe on read.
No size cap in the initial version; sessions are bounded by handoff
discipline so unbounded growth is not a real risk.

Never blocks. Always exits 0. ``OSError`` on append is logged to
stderr and swallowed — this hook is observability infrastructure,
not a gate.

Event: PostToolUse
Matcher: Edit|Write|MultiEdit
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

from hooks._hook_shared import get_project_dir, read_hook_input
from hooks._session_state_common import get_memory_dir

_QUALIFYING_TOOLS: frozenset[str] = frozenset({"Edit", "Write", "MultiEdit"})
_LOG_FILENAME: str = "changed-files.log"


def _extract_file_path(data: dict[str, object]) -> str:
    """Pull a non-empty file path from the tool input payload."""
    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        return ""
    value = tool_input.get("file_path")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return ""


def _append(log_path: Path, line: str) -> None:
    """Append *line* to *log_path*, creating the parent dir if needed."""
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError as exc:
        print(
            f"[post_track_changed_files] could not append to {log_path}: {exc}",
            file=sys.stderr,
        )


def main() -> int:
    data = read_hook_input()

    tool_name = str(data.get("tool_name", ""))
    if tool_name not in _QUALIFYING_TOOLS:
        return 0

    file_path = _extract_file_path(data)
    if not file_path:
        return 0

    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"{timestamp}\t{tool_name}\t{file_path}\n"

    log_path = get_memory_dir(get_project_dir()) / _LOG_FILENAME
    _append(log_path, line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
