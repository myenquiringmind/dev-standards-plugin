"""Sweep orphaned ``tmpclaude-*`` files from the project root.

Fires after every Edit/Write/MultiEdit. Lists ``tmpclaude-*`` files
in the project root (non-recursive — blast radius stays bounded)
and unlinks any whose mtime is older than
``TMP_FILE_AGE_THRESHOLD_SECONDS`` (5 minutes by default).

Why this threshold:

- Long enough that an in-flight CC tool call cannot race the
  sweeper and lose its own working file.
- Short enough that a crashed or aborted tool call does not leave
  debris sitting in the repo root for a whole session.

Never blocks. Always exits 0. Per-file unlink failures log to
stderr (typically Windows AV holding a stale handle) but do not
short-circuit the rest of the sweep.

Event: PostToolUse
Matcher: Edit|Write|MultiEdit
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from hooks._hook_shared import (
    TMP_FILE_AGE_THRESHOLD_SECONDS,
    get_project_dir,
    read_hook_input,
)

_QUALIFYING_TOOLS: frozenset[str] = frozenset({"Edit", "Write", "MultiEdit"})
_GLOB_PATTERN: str = "tmpclaude-*"


def _sweep(project_dir: Path, now: float) -> None:
    """Unlink stale ``tmpclaude-*`` files in *project_dir*."""
    threshold = now - TMP_FILE_AGE_THRESHOLD_SECONDS
    try:
        candidates = list(project_dir.glob(_GLOB_PATTERN))
    except OSError as exc:
        print(f"[post_temp_file_cleanup] could not enumerate: {exc}", file=sys.stderr)
        return

    for path in candidates:
        try:
            if not path.is_file():
                continue
            if path.stat().st_mtime >= threshold:
                continue
            path.unlink()
        except OSError as exc:
            print(
                f"[post_temp_file_cleanup] could not remove {path}: {exc}",
                file=sys.stderr,
            )


def main() -> int:
    data = read_hook_input()

    tool_name = str(data.get("tool_name", ""))
    if tool_name not in _QUALIFYING_TOOLS:
        return 0

    _sweep(get_project_dir(), time.time())
    return 0


if __name__ == "__main__":
    sys.exit(main())
