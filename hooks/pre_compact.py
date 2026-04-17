"""Snapshot session state before CC compacts the transcript.

CC fires PreCompact when the conversation is about to be summarised
and trimmed. This hook writes a fresh ``session-state.md`` so that
whatever the compaction drops, the next ``session_start`` can
restore. It also emits a short ``systemMessage`` reminding the model
to keep the next turn narrow.

Event: PreCompact
Matcher: *
"""

from __future__ import annotations

import json
import sys

from hooks._hook_shared import get_project_dir, read_hook_input
from hooks._session_state_common import extract_from_transcript, write_session_state

_SYSTEM_MESSAGE: str = (
    "Pre-compaction snapshot written to session-state.md. "
    "After compaction completes, prioritise: (1) committing any uncommitted work, "
    "(2) confirming the branch and next objective from the snapshot, "
    "(3) only then resuming new work."
)


def main() -> int:
    data = read_hook_input()
    transcript_path = data.get("transcript_path")

    project_dir = get_project_dir()

    extracted: dict[str, object] = {}
    if isinstance(transcript_path, str) and transcript_path:
        extracted = dict(extract_from_transcript(transcript_path))

    try:
        write_session_state(extracted, project_dir, header_note="Pre-compaction snapshot")
    except OSError as exc:
        print(f"[pre_compact] could not write state: {exc}", file=sys.stderr)
        return 0

    print(json.dumps({"systemMessage": _SYSTEM_MESSAGE}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
