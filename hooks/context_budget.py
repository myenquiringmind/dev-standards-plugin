"""Advisory + hard-block context budget gate at prompt time.

Reads the ``.claude/.context_pct`` cache written by ``statusline.py``
to obtain the running ``framework_pct`` — the session's position in
units where ``100`` is exactly the framework hard cut returned by
``_hook_shared.compute_hard_cut`` (≈62.625% of the active model's
window). Emits a stderr advisory at ``WARN_CONTEXT_PCT`` (80% of
hard cut) and exits 2 at ``CRITICAL_CONTEXT_PCT`` (100% — the cut)
with the canonical handoff protocol message. CC auto-compaction
fires at ``framework_pct ≈ 133``; the hard cut at 100 leaves a
deliberate cushion the agent can spend on a clean handoff.

If ``.claude/.context_pct`` is missing the cache is offline. The
hook still exits 0 (this is a UserPromptSubmit gate — never block
on monitoring failure) but emits a one-line stderr advisory so the
silent-failure mode that produced TR-0004 is observable. Once
``statusline.py`` is wired into ``~/.claude/settings.json`` the
advisory disappears.

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
        print(
            "[context_budget] context monitoring offline "
            "(.claude/.context_pct missing) — install the statusline command "
            "in ~/.claude/settings.json to enable budget tracking.",
            file=sys.stderr,
        )
        return 0

    if pct >= CRITICAL_CONTEXT_PCT:
        print(
            f"[context_budget] context usage {pct}% — at or above "
            f"{CRITICAL_CONTEXT_PCT}% framework hard cut. Handoff before continuing:\n"
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
