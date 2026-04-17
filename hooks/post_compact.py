"""Post-compaction hygiene — verify the snapshot exists and drop stale caches.

Runs after CC finishes compacting. Responsibilities:

* Confirm ``<memory>/session-state.md`` exists (written by
  ``pre_compact.py``). If missing, log a warning — the next
  ``session_start`` will have nothing to restore.
* Delete the ephemeral ``.claude/.context_pct`` cache so that the
  first statusline run after compaction recomputes the percentage
  against the new (shorter) transcript.

Event: PostCompact
Matcher: *
"""

from __future__ import annotations

import sys
from pathlib import Path

from hooks._hook_shared import get_project_dir, read_hook_input
from hooks._session_state_common import get_memory_dir


def main() -> int:
    read_hook_input()  # drain stdin; payload unused

    project_dir: Path = get_project_dir()
    memory_dir = get_memory_dir(project_dir)
    state_path = memory_dir / "session-state.md"

    if not state_path.exists():
        print(
            "[post_compact] no session-state.md found — pre_compact may not have run",
            file=sys.stderr,
        )

    context_cache = project_dir / ".claude" / ".context_pct"
    if context_cache.exists():
        try:
            context_cache.unlink()
        except OSError as exc:
            print(f"[post_compact] could not delete {context_cache}: {exc}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
