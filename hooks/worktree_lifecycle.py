"""Maintain framework state across CC worktree create / remove events.

Single hook file dispatching on ``hook_event_name`` to two
operations:

- **WorktreeCreate** — seed the new worktree's
  ``.language_profile.json`` from the source worktree if present,
  so the new tree shares the detected language profile without
  re-running ``detect_language``.
- **WorktreeRemove** — clean up framework artifacts from the
  leaving worktree: the five validation-stamp files (per
  ``pre_commit_cli_gate._STAMP_FILENAMES``) plus the language
  profile stamp. Anything else in the worktree is git's concern.

Why both in one file: the two operations are inverses of each
other on a single concept (per-worktree framework state). Keeping
them in one module documents the symmetry and lets future stamps
get added in one place.

Never blocks. Always exits 0. Per-file unlink / read failures log
to stderr and continue — the rest of the operation is not short-
circuited. Unknown or missing event name → safe no-op (we do not
guess which side to run).

Event: WorktreeCreate, WorktreeRemove
Matcher: *
"""

from __future__ import annotations

import sys
from pathlib import Path

from hooks._hook_shared import get_project_dir, read_hook_input

_LANGUAGE_PROFILE: str = ".language_profile.json"

#: Validation stamp filenames managed by ``pre_commit_cli_gate``. Listed
#: explicitly here (rather than imported) to keep this hook independent
#: of the cli_gate's internal layout — both lists move together when a
#: new gate lands.
_STAMP_FILES: tuple[str, ...] = (
    ".validation_stamp",
    ".frontend_validation_stamp",
    ".agent_validation_stamp",
    ".db_validation_stamp",
    ".api_validation_stamp",
)

_FRAMEWORK_FILES_TO_CLEAN: tuple[str, ...] = (*_STAMP_FILES, _LANGUAGE_PROFILE)

_EVENT_CREATE: str = "WorktreeCreate"
_EVENT_REMOVE: str = "WorktreeRemove"


def _extract_event(data: dict[str, object]) -> str:
    """Pull the event name from the payload, normalising minor variations."""
    for key in ("hook_event_name", "event", "event_name"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _extract_path(data: dict[str, object], *keys: str) -> Path | None:
    """Pull a non-empty path from the first matching payload field."""
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return Path(value.strip())
    return None


def _seed_profile(source: Path, worktree: Path) -> None:
    """Copy the language profile from *source* to *worktree* if present."""
    src_file = source / _LANGUAGE_PROFILE
    if not src_file.is_file():
        return
    target = worktree / _LANGUAGE_PROFILE
    try:
        worktree.mkdir(parents=True, exist_ok=True)
        target.write_text(src_file.read_text(encoding="utf-8"), encoding="utf-8")
    except OSError as exc:
        print(
            f"[worktree_lifecycle] could not seed {target}: {exc}",
            file=sys.stderr,
        )


def _cleanup_worktree(worktree: Path) -> None:
    """Remove framework artifacts from *worktree*."""
    for name in _FRAMEWORK_FILES_TO_CLEAN:
        target = worktree / name
        try:
            target.unlink(missing_ok=True)
        except OSError as exc:
            print(
                f"[worktree_lifecycle] could not remove {target}: {exc}",
                file=sys.stderr,
            )


def main() -> int:
    data = read_hook_input()
    event = _extract_event(data)

    if event == _EVENT_CREATE:
        worktree = _extract_path(data, "path", "worktree_path", "cwd")
        if worktree is None:
            return 0
        source = _extract_path(data, "source_path", "source_worktree") or get_project_dir()
        _seed_profile(source, worktree)
        return 0

    if event == _EVENT_REMOVE:
        worktree = _extract_path(data, "path", "worktree_path", "cwd")
        if worktree is None or not worktree.is_dir():
            return 0
        _cleanup_worktree(worktree)
        return 0

    # Unknown event — safe no-op rather than guessing which side to run.
    return 0


if __name__ == "__main__":
    sys.exit(main())
