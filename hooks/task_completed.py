"""Bridge CC TaskCompleted events to ``session-state.md``'s task graph.

Sibling to ``task_created.py``. When CC fires ``TaskCompleted``,
this hook flips the matching ``- [ ] <subject>`` line in the
``## Task Progress`` section to ``- [x] <subject>`` so the round-
tripped session state shows the task as done. The closed-loop
``quality-scorer`` consumes the ``[x]`` markers in Phase 4 to
weigh task completion against telemetry.

Match key: line text. The ``- [ ] <subject>`` written by
``task_created`` is the only place the subject lives in the file —
there is no id channel. If two tasks share a subject the first
line found in the section is flipped; the second remains pending.
That edge case is accepted for Phase 2; the closed-loop scorer
tolerates duplicate subjects on the assumption they are uncommon.

No outer sidecar lock around ``atomic_write`` (lesson from PR #57:
``_os_safe.atomic_write`` reserves ``<target>.lock`` for its
internal replace lock, so an outer caller-level lock on the same
file would deadlock). The read-modify-write window is therefore
racy against a concurrent ``write_session_state`` (e.g. a
``session_checkpoint`` flush) — a collision drops a single
``[ ] → [x]`` flip the user can re-trigger.

No-op cases:
- Empty / missing subject in the payload.
- Missing state file.
- Subject not present in ``## Task Progress`` — the hook does not
  add a new ``[x]`` line for a task that was never tracked.
- Subject already marked ``[x]`` — idempotent.

Never blocks. Always exits 0.

Event: TaskCompleted
Matcher: *
"""

from __future__ import annotations

import sys
from pathlib import Path

from hooks._hook_shared import get_project_dir, read_hook_input
from hooks._os_safe import atomic_write
from hooks._session_state_common import get_memory_dir

_STATE_FILENAME: str = "session-state.md"
_SECTION_HEADING: str = "## Task Progress"


def _extract_subject(data: dict[str, object]) -> str:
    """Pull a non-empty subject from the first matching payload field."""
    task = data.get("task")
    if isinstance(task, dict):
        for key in ("subject", "content"):
            value = task.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    for key in ("subject", "content"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _flip_in_task_progress(text: str, subject: str) -> str:
    """Return *text* with the first matching ``- [ ] <subject>`` flipped to
    ``- [x] <subject>`` inside the ``## Task Progress`` section.

    Returns *text* unchanged if no matching pending line exists in the
    section (already completed, never created, or section absent).
    """
    open_marker = f"- [ ] {subject}"
    closed_marker = f"- [x] {subject}"

    lines = text.splitlines()
    section_start: int | None = None
    section_end = len(lines)

    for i, line in enumerate(lines):
        if line.strip() == _SECTION_HEADING:
            section_start = i
            continue
        if section_start is not None and line.startswith("## "):
            section_end = i
            break

    if section_start is None:
        return text

    for i in range(section_start + 1, section_end):
        stripped = lines[i].rstrip()
        if stripped == open_marker:
            lines[i] = closed_marker
            joined = "\n".join(lines)
            return joined + "\n" if text.endswith("\n") else joined
        if stripped == closed_marker:
            return text  # Already completed — idempotent.

    return text  # Subject not in section — do not invent a new line.


def _update_state_file(state_path: Path, subject: str) -> None:
    """Read-modify-write the state file via ``atomic_write``.

    See ``task_created.py`` for the locking rationale: no outer lock,
    ``atomic_write`` handles the replace.
    """
    try:
        text = state_path.read_text(encoding="utf-8")
    except OSError:
        return

    updated = _flip_in_task_progress(text, subject)
    if updated == text:
        return

    try:
        atomic_write(state_path, updated)
    except OSError as exc:
        print(f"[task_completed] could not write state: {exc}", file=sys.stderr)


def main() -> int:
    data = read_hook_input()

    subject = _extract_subject(data)
    if not subject:
        return 0

    state_path = get_memory_dir(get_project_dir()) / _STATE_FILENAME
    if not state_path.exists():
        return 0

    _update_state_file(state_path, subject)
    return 0


if __name__ == "__main__":
    sys.exit(main())
