"""Advisory + hard-block context budget gate at prompt time.

Reads the ``.claude/.context_pct`` cache written by ``statusline.py``
(Phase 1) to compute how close the session is to CC's auto-compaction
threshold. Emits a stderr advisory at ``WARN_CONTEXT_PCT`` (80%) and
exits 2 at ``CRITICAL_CONTEXT_PCT`` (95%) with the canonical handoff
protocol message.

In Phase 0b the cache is not yet populated — ``read_cached_pct``
returns ``None`` and this hook exits 0 silently. Once ``statusline.py``
lands in Phase 1 the hook becomes live without any config change.

Event: UserPromptSubmit
Matcher: *
"""

from __future__ import annotations

import sys

from hooks._hook_shared import (
    CRITICAL_CONTEXT_PCT,
    HANDOFF_STEPS,
    WARN_CONTEXT_PCT,
    get_project_dir,
    read_cached_pct,
    read_hook_input,
)


def main() -> int:
    read_hook_input()  # drain stdin; payload unused

    pct = read_cached_pct(get_project_dir())
    if pct is None:
        return 0

    if pct >= CRITICAL_CONTEXT_PCT:
        print(
            f"[context_budget] context usage {pct}% — at or above "
            f"{CRITICAL_CONTEXT_PCT}% critical threshold. Handoff before continuing:\n"
            f"{HANDOFF_STEPS}",
            file=sys.stderr,
        )
        return 2

    if pct >= WARN_CONTEXT_PCT:
        print(
            f"[context_budget] context usage {pct}% — approaching the "
            f"{CRITICAL_CONTEXT_PCT}% hard cut. Start planning a /handoff.",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
