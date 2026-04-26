"""Block CC Stop when the working tree has uncommitted changes.

The framework's cardinal rule from ``.claude/rules/session-lifecycle.md``:
*never let validated work sit uncommitted.* A ``Stop`` event with a dirty
tree is about to drop that work on the floor — the next session, a crash,
or a ``/clear`` will lose it. This hook is the last-chance gate.

Remediation is always one of:
- Finish and commit the work normally.
- ``git commit -m "[WIP] ..."`` to checkpoint mid-objective (see the
  session-lifecycle rule's WIP protocol + the stewardship-ratchet
  validation footer).

After either, ``git status --porcelain`` goes empty and the Stop passes.

Fail-open on:
- Git unavailable, no ``.git`` directory, or ``git status`` failing for
  any reason. If we cannot reason about the tree, we do not block —
  the user may be mid-merge, mid-rebase, or in an unusual state we do
  not want to compound with a surprise stop block.

Event: Stop
Matcher: *
"""

from __future__ import annotations

import subprocess
import sys

from hooks._hook_shared import get_project_dir, read_hook_input

_STATUS_TIMEOUT: float = 5.0
_MAX_DIRTY_LISTED: int = 10


def _porcelain_status() -> list[str] | None:
    """Return ``git status --porcelain`` lines, or ``None`` on any failure.

    ``None`` is the fail-open signal — the caller treats it as "we do not
    know, let the stop proceed."
    """
    project_dir = get_project_dir()
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=_STATUS_TIMEOUT,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None

    if result.returncode != 0:
        return None

    return [line for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    # Read stdin to drain the hook payload even though we don't use fields
    # from it — Stop events may carry reason/context the framework does not
    # surface through environment.
    read_hook_input()

    dirty = _porcelain_status()
    if not dirty:
        # Either the tree is clean, or we cannot tell (fail-open).
        return 0

    shown = dirty[:_MAX_DIRTY_LISTED]
    more = len(dirty) - len(shown)
    listing = "\n".join(f"  {line}" for line in shown)
    if more > 0:
        listing += f"\n  … and {more} more"

    print(
        f"[stop_validation] refusing Stop — working tree has "
        f"{len(dirty)} uncommitted change(s):\n"
        f"{listing}\n"
        f"Commit the work before stopping. Use a ``[WIP]`` commit to "
        f"checkpoint mid-objective:\n"
        f"  git add -A && git commit -m '[WIP] <what is done, what remains>'\n"
        f"See ``.claude/rules/session-lifecycle.md`` for the WIP protocol.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
