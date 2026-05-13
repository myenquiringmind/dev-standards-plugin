"""Fallback writer for ``.claude/.context_pct`` when statusline is silent.

``hooks/statusline.py`` is a Claude Code ``statusLine`` command, not a
hook. Plugins cannot ship a top-level ``statusLine`` entry (only
``agent`` and ``subagentStatusLine`` are plugin-shippable), so the
user must wire it in ``~/.claude/settings.json`` (see
``docs/guides/statusline-wiring.md``). Until that happens — and even
afterwards, between statusline invocations — ``.claude/.context_pct``
may not exist, leaving ``context_budget.py`` in advisory-only mode.

This hook closes the gap. Dispatches on ``hook_event_name`` to two
operations on the same concept (per-session context-percentage cache):

- **SessionStart** — write a framework_pct estimate from the
  transcript file size. New sessions write ``0`` (no transcript yet);
  resumed sessions get a non-zero estimate immediately. This
  guarantees the cache exists from turn 1.
- **PostToolUse** (matcher ``*``) — re-estimate from the current
  transcript size, but defer to a fresh ``.context_pct`` (mtime within
  ``STATUSLINE_STALENESS_SECONDS``) so ``statusline.py``'s accurate
  readings win when wired.

The estimate is deliberately conservative: ``BYTES_PER_TOKEN_ESTIMATE``
over-counts tokens, and ``FALLBACK_WINDOW_TOKENS`` (200K) over-reports
``framework_pct`` on a 1M-window session. Both biases push the warn
and hard-cut earlier, which is the safe failure mode for monitoring.

Never blocks. Always exits 0.

Event: SessionStart, PostToolUse
Matcher: *
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

from hooks._hook_shared import (
    BYTES_PER_TOKEN_ESTIMATE,
    FALLBACK_WINDOW_TOKENS,
    STATUSLINE_STALENESS_SECONDS,
    compute_hard_cut,
    get_project_dir,
    read_hook_input,
)
from hooks._os_safe import atomic_write

_EVENT_SESSION_START: str = "SessionStart"
_EVENT_POST_TOOL_USE: str = "PostToolUse"

_CACHE_RELATIVE_PATH: tuple[str, str] = (".claude", ".context_pct")


def _extract_event(data: dict[str, Any]) -> str:
    for key in ("hook_event_name", "event", "event_name"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _extract_transcript_path(data: dict[str, Any]) -> str:
    value = data.get("transcript_path")
    if isinstance(value, str):
        return value.strip()
    return ""


def _transcript_size(path: str) -> int | None:
    if not path:
        return None
    try:
        return Path(path).stat().st_size
    except (FileNotFoundError, OSError):
        return None


def _estimate_framework_pct(transcript_bytes: int) -> int:
    """Convert transcript size to framework_pct using fallback assumptions."""
    if transcript_bytes <= 0:
        return 0
    hard_cut_tokens = compute_hard_cut(FALLBACK_WINDOW_TOKENS)
    if hard_cut_tokens <= 0:
        return 0
    estimated_tokens = transcript_bytes // BYTES_PER_TOKEN_ESTIMATE
    pct = estimated_tokens * 100 // hard_cut_tokens
    return max(0, pct)


def _cache_is_fresh(cache_path: Path, now: float) -> bool:
    try:
        mtime = cache_path.stat().st_mtime
    except (FileNotFoundError, OSError):
        return False
    return (now - mtime) < STATUSLINE_STALENESS_SECONDS


def _write_cache(cache_path: Path, pct: int) -> None:
    try:
        atomic_write(cache_path, str(pct))
    except OSError as exc:
        print(
            f"[context_pct_writer] could not write {cache_path.name}: {exc}",
            file=sys.stderr,
        )


def main() -> int:
    data = read_hook_input()
    event = _extract_event(data)

    if event not in (_EVENT_SESSION_START, _EVENT_POST_TOOL_USE):
        return 0

    project_dir = get_project_dir()
    cache_path = project_dir / _CACHE_RELATIVE_PATH[0] / _CACHE_RELATIVE_PATH[1]

    # PostToolUse defers to statusline.py when its write is fresh. SessionStart
    # always writes (a stale value from the prior session must be reset).
    if event == _EVENT_POST_TOOL_USE and _cache_is_fresh(cache_path, time.time()):
        return 0

    transcript_path = _extract_transcript_path(data)
    size = _transcript_size(transcript_path)

    pct = _estimate_framework_pct(size or 0)
    _write_cache(cache_path, pct)
    return 0


if __name__ == "__main__":
    sys.exit(main())
