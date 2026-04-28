"""Bridge CC TaskCreated events to ``session-state.md``'s task graph.

When CC fires ``TaskCreated``, this hook appends a ``- [ ] <subject>``
line to the ``## Task Progress`` section of ``<memory>/session-state.md``,
matching the line format that ``_session_state_common.parse_todos_from_markdown``
recognises. The result: any agent that later reads session-state — a
restored session, a rolling summarizer, the meta-session-planner —
sees the new task without it having to be re-derived from the
transcript.

Design constraints lifted from ``agents/meta/meta-session-planner.md``:

> The file is append-only per-section and shared across hooks;
> rewriting the whole file would conflict with
> ``_session_state_common.write_session_state()``.

So the hook only ever modifies the ``## Task Progress`` section.
Other sections — Active Request, Files Modified, Repository State,
etc. — pass through unchanged. ``atomic_write`` provides the
sidecar lock around the replace step, so a concurrent
``write_session_state`` from ``session_checkpoint`` cannot tear the
file. The read-modify-write window itself is racy: a checkpoint
flushed between this hook's read and write would lose the appended
task. That tradeoff is accepted — the hook fires once per task and
a lost line is a single ``- [ ] ...`` entry the user can re-add.

Idempotent on duplicate fires: an exact ``- [ ] <subject>`` line
already present in the section is treated as a no-op.

Never blocks. Always exits 0. Missing payload, missing state file,
lock timeout, OSError — all fail-open. The hook is a recorder, not
a gate.

Event: TaskCreated
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


def _splice_into_task_progress(text: str, new_line: str) -> str:
    """Return *text* with *new_line* inserted at the end of the
    ``## Task Progress`` section.

    Adds the section if missing. Returns *text* unchanged if *new_line*
    already appears in the section (idempotent guard).
    """
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
        # No section yet — append a fresh one.
        suffix: list[str] = []
        if lines and lines[-1].strip():
            suffix.append("")
        suffix.extend([_SECTION_HEADING, new_line, ""])
        joined = "\n".join(lines + suffix)
        return joined + "\n" if text.endswith("\n") or text == "" else joined

    # Idempotent guard: bail if the line already exists in the section.
    for i in range(section_start + 1, section_end):
        if lines[i].rstrip() == new_line:
            return text

    # Insert before any trailing blank lines that separate the section
    # from the next heading or EOF.
    insert_at = section_end
    while insert_at > section_start + 1 and not lines[insert_at - 1].strip():
        insert_at -= 1

    new_lines = [*lines[:insert_at], new_line, *lines[insert_at:]]
    joined = "\n".join(new_lines)
    return joined + "\n" if text.endswith("\n") else joined


def _update_state_file(state_path: Path, new_line: str) -> None:
    """Read-modify-write the state file.

    No outer lock is acquired: ``atomic_write`` already locks the
    sidecar ``<target>.lock`` for its replace step, and acquiring an
    outer lock on the *same* sidecar would deadlock against that
    internal acquisition. The read-modify-write window is therefore
    racy against any concurrent ``write_session_state`` call (e.g.,
    from ``session_checkpoint``); the race is acceptable here because
    the hook fires at most once per ``TaskCreated`` event and a lost
    update only drops a single ``- [ ] ...`` line that the user can
    trivially re-add.
    """
    try:
        text = state_path.read_text(encoding="utf-8")
    except OSError:
        return

    updated = _splice_into_task_progress(text, new_line)
    if updated == text:
        return

    try:
        atomic_write(state_path, updated)
    except OSError as exc:
        print(f"[task_created] could not write state: {exc}", file=sys.stderr)


def main() -> int:
    data = read_hook_input()

    subject = _extract_subject(data)
    if not subject:
        return 0

    state_path = get_memory_dir(get_project_dir()) / _STATE_FILENAME
    if not state_path.exists():
        return 0

    new_line = f"- [ ] {subject}"
    _update_state_file(state_path, new_line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
