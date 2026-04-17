"""Persist session state when CC ends or pauses the session.

Extracts the key fields (modified files, last prompt, active todos,
recent errors, recent reasoning) from the CC transcript and writes
them to ``<memory>/session-state.md`` via
:func:`hooks._session_state_common.write_session_state`. The matching
``session_start.py`` hook reads this file at next launch.

Event: SessionEnd
Matcher: *
"""

from __future__ import annotations

import sys

from hooks._hook_shared import get_project_dir, read_hook_input
from hooks._session_state_common import extract_from_transcript, write_session_state


def main() -> int:
    data = read_hook_input()
    transcript_path = data.get("transcript_path")
    reason = str(data.get("reason", "")).strip()

    project_dir = get_project_dir()

    extracted: dict[str, object] = {}
    if isinstance(transcript_path, str) and transcript_path:
        extracted = dict(extract_from_transcript(transcript_path))

    header = f"Session ended: {reason}" if reason else "Session ended"

    try:
        write_session_state(extracted, project_dir, header_note=header)
    except OSError as exc:
        print(f"[session_end] could not write state: {exc}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
