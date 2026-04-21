"""Auto-save session state periodically during long work sessions.

Fires after every Edit/Write/MultiEdit. Maintains a tiny JSON counter
at ``<memory>/session-checkpoint.state.json`` (event count, last
write timestamp, last branch) and writes a fresh ``session-state.md``
when any of three triggers fires:

* **Edit count:** ``CHECKPOINT_INTERVAL_EVENTS`` qualifying edits
  since the last checkpoint (default 5).
* **Time:** ``CHECKPOINT_INTERVAL_SECONDS`` elapsed since the last
  checkpoint (default 900 = 15 minutes).
* **Phase transition:** the current git branch differs from the
  branch recorded at the last checkpoint.

This is the middle ground between ``session_end`` (end of session)
and ``pre_compact`` (compaction boundary): a crash or hard kill
between those events must not lose the user's work in progress.
Never blocks — always exits 0.

Event: PostToolUse
Matcher: Edit|Write|MultiEdit
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

from hooks._hook_shared import (
    CHECKPOINT_INTERVAL_EVENTS,
    CHECKPOINT_INTERVAL_SECONDS,
    get_current_branch,
    get_project_dir,
    read_hook_input,
)
from hooks._os_safe import atomic_write
from hooks._session_state_common import (
    extract_from_transcript,
    get_memory_dir,
    write_session_state,
)

_STATE_FILENAME: str = "session-checkpoint.state.json"
_QUALIFYING_TOOLS: frozenset[str] = frozenset({"Edit", "Write", "MultiEdit"})


def _load_state(state_path: Path) -> dict[str, Any]:
    """Read the checkpoint state file, returning defaults on any fault."""
    default: dict[str, Any] = {
        "event_count": 0,
        "last_write_ts": 0.0,
        "last_branch": "",
    }
    try:
        raw = state_path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return default

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return default

    if not isinstance(parsed, dict):
        return default

    count = parsed.get("event_count", 0)
    ts = parsed.get("last_write_ts", 0.0)
    branch = parsed.get("last_branch", "")
    return {
        "event_count": int(count) if isinstance(count, int) else 0,
        "last_write_ts": float(ts) if isinstance(ts, (int, float)) else 0.0,
        "last_branch": branch if isinstance(branch, str) else "",
    }


def _save_state(state_path: Path, state: dict[str, Any]) -> None:
    """Write the checkpoint state file atomically; log but don't raise."""
    try:
        atomic_write(state_path, json.dumps(state, indent=2))
    except OSError as exc:
        print(f"[session_checkpoint] could not write state file: {exc}", file=sys.stderr)


def _should_checkpoint(
    state: dict[str, Any],
    now: float,
    current_branch: str,
) -> tuple[bool, str]:
    """Return (fires, reason) for the checkpoint trigger triad."""
    if state["event_count"] >= CHECKPOINT_INTERVAL_EVENTS:
        return True, f"{state['event_count']} edits"

    elapsed = now - state["last_write_ts"]
    if state["last_write_ts"] > 0 and elapsed >= CHECKPOINT_INTERVAL_SECONDS:
        return True, f"{int(elapsed)}s elapsed"

    last_branch = state["last_branch"]
    if last_branch and current_branch and current_branch != last_branch:
        return True, f"branch {last_branch} → {current_branch}"

    return False, ""


def main() -> int:
    data = read_hook_input()

    tool_name = data.get("tool_name")
    if tool_name not in _QUALIFYING_TOOLS:
        return 0

    project_dir = get_project_dir()
    memory_dir = get_memory_dir(project_dir)
    state_path = memory_dir / _STATE_FILENAME

    state = _load_state(state_path)
    state["event_count"] = int(state["event_count"]) + 1

    now = time.time()
    current_branch = get_current_branch(project_dir)

    fires, reason = _should_checkpoint(state, now, current_branch)

    if fires:
        transcript_path = data.get("transcript_path")
        extracted: dict[str, Any] = {}
        if isinstance(transcript_path, str) and transcript_path:
            extracted = dict(extract_from_transcript(transcript_path))

        try:
            write_session_state(
                extracted,
                project_dir,
                header_note=f"Auto-checkpoint ({reason})",
            )
        except OSError as exc:
            print(f"[session_checkpoint] could not write state: {exc}", file=sys.stderr)
            _save_state(state_path, state)
            return 0

        state = {
            "event_count": 0,
            "last_write_ts": now,
            "last_branch": current_branch,
        }

    _save_state(state_path, state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
