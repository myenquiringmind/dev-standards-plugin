"""Track objective-lifecycle phase transitions in session-state.md.

Fires on UserPromptSubmit. Scans the prompt text for one of the
seven canonical lifecycle phase names defined in
``.claude/rules/session-lifecycle.md``:

    OBJECTIVE, GAP, DESIGN, IMPLEMENT, VALIDATE, OBSERVE, COMMIT, REFLECT

If the prompt contains one or more uppercase phase tokens, the
**last** match wins (most-recent-intent semantics — a prompt like
"DESIGN done, now IMPLEMENT" picks IMPLEMENT). The detected phase
is then written to ``<memory>/session-state.md``'s
``## Current Phase`` section, replacing whatever was there.

Heuristic justification: uppercase phase tokens are rare in
normal English and the lifecycle rule itself uses these literal
uppercase markers (``### 1. OBJECTIVE`` etc.). False positives are
bounded; false negatives mean the section just doesn't update,
which is harmless.

Section semantics, per ``agents/meta/meta-session-planner.md``:
this hook only ever modifies ``## Current Phase``. Other sections
pass through unchanged. ``atomic_write`` provides the replace-step
lock; no outer lock (matches the pattern from PR #57). The
read-modify-write window is bounded-racy against
``write_session_state``; a lost transition is recovered the next
time the user types the phase name.

Idempotent: if ``## Current Phase`` already contains the detected
phase, the file is not rewritten.

No-op cases:
- No phase token in the prompt.
- Missing state file (let ``session_start`` bootstrap it).
- Empty / non-string prompt field.
- Empty stdin.

Never blocks. Always exits 0.

Event: UserPromptSubmit
Matcher: *
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from hooks._hook_shared import get_project_dir, read_hook_input
from hooks._os_safe import atomic_write
from hooks._session_state_common import get_memory_dir

_STATE_FILENAME: str = "session-state.md"
_SECTION_HEADING: str = "## Current Phase"
_PROMPT_KEYS: tuple[str, ...] = ("prompt", "user_prompt", "message")
_PHASE_NAMES: tuple[str, ...] = (
    "OBJECTIVE",
    "GAP",
    "DESIGN",
    "IMPLEMENT",
    "VALIDATE",
    "OBSERVE",
    "COMMIT",
    "REFLECT",
)
_PHASE_RE = re.compile(r"\b(" + "|".join(_PHASE_NAMES) + r")\b")


def _extract_prompt(data: dict[str, object]) -> str:
    """Pull a non-empty prompt string from the first matching key."""
    for key in _PROMPT_KEYS:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _detect_phase(prompt: str) -> str:
    """Return the last phase token in *prompt*, or ``""`` if none."""
    matches = _PHASE_RE.findall(prompt)
    return matches[-1] if matches else ""


def _splice_current_phase(text: str, phase: str) -> str:
    """Return *text* with the ``## Current Phase`` section's body replaced.

    Adds the section if missing. Returns *text* unchanged when the
    section already contains exactly *phase* (idempotent guard).
    """
    new_body = phase
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
        # Append a fresh section.
        suffix: list[str] = []
        if lines and lines[-1].strip():
            suffix.append("")
        suffix.extend([_SECTION_HEADING, new_body, ""])
        joined = "\n".join(lines + suffix)
        return joined + "\n" if text.endswith("\n") or text == "" else joined

    # Strip leading/trailing blank lines from the existing body for the
    # idempotency check.
    body_lines = [line for line in lines[section_start + 1 : section_end] if line.strip()]
    if body_lines == [new_body]:
        return text

    # Replace the body. Preserve any trailing blank line that separated the
    # section from the next heading.
    trailing_blank = section_end > section_start + 1 and not lines[section_end - 1].strip()
    replacement: list[str] = [_SECTION_HEADING, new_body]
    if trailing_blank:
        replacement.append("")
    new_lines = [*lines[:section_start], *replacement, *lines[section_end:]]
    joined = "\n".join(new_lines)
    return joined + "\n" if text.endswith("\n") else joined


def _update_state_file(state_path: Path, phase: str) -> None:
    """Read-modify-write the state file; ``atomic_write`` guards the replace."""
    try:
        text = state_path.read_text(encoding="utf-8")
    except OSError:
        return

    updated = _splice_current_phase(text, phase)
    if updated == text:
        return

    try:
        atomic_write(state_path, updated)
    except OSError as exc:
        print(f"[phase_transition] could not write state: {exc}", file=sys.stderr)


def main() -> int:
    data = read_hook_input()

    prompt = _extract_prompt(data)
    if not prompt:
        return 0

    phase = _detect_phase(prompt)
    if not phase:
        return 0

    state_path = get_memory_dir(get_project_dir()) / _STATE_FILENAME
    if not state_path.exists():
        return 0

    _update_state_file(state_path, phase)
    return 0


if __name__ == "__main__":
    sys.exit(main())
