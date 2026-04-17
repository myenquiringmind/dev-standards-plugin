"""Restore session state at SessionStart by injecting persisted context.

Reads ``<memory>/session-state.md`` written by the prior session's
``session_end.py`` or ``pre_compact.py``, formats it as an
``additionalContext`` payload that CC injects into the new session,
then archives the source file to ``.injected`` so the file survives
a crash during injection but is not re-read next time.

Event: SessionStart
Matcher: *
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from hooks._hook_shared import get_project_dir, read_hook_input
from hooks._session_state_common import (
    archive_state_to_injected,
    get_memory_dir,
    parse_todos_from_markdown,
)

_SOURCE_PREAMBLES: dict[str, str] = {
    "startup": "Resuming work from the prior session.",
    "resume": "Resuming a previously paused session.",
    "clear": "Session was cleared. Restoring the prior snapshot so work can continue.",
    "compact": "Session was compacted. Restoring the prior snapshot from the pre-compaction state.",
}


def _build_context(state_text: str, source: str) -> str:
    preamble = _SOURCE_PREAMBLES.get(source, _SOURCE_PREAMBLES["startup"])
    todos = parse_todos_from_markdown(state_text)

    parts: list[str] = [f"## Session Continuity\n\n{preamble}", state_text.strip()]

    if todos:
        active = [t for t in todos if t["status"] != "completed"]
        if active:
            parts.append(
                "\n## Restore Active Todos\n\n"
                "The prior session left the following todos in-flight. "
                "Call TodoWrite now to reinstate them so progress tracking continues:"
            )
            rendered = [
                {"content": t["content"], "status": t["status"], "activeForm": t["content"]}
                for t in active
            ]
            parts.append(f"```json\n{json.dumps(rendered, indent=2)}\n```")

    return "\n\n".join(parts)


def main() -> int:
    data = read_hook_input()
    source = str(data.get("source", "startup"))

    project_dir = get_project_dir()
    memory_dir: Path = get_memory_dir(project_dir)
    state_path = memory_dir / "session-state.md"

    if not state_path.exists():
        return 0

    try:
        state_text = state_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"[session_start] could not read state file: {exc}", file=sys.stderr)
        return 0

    context = _build_context(state_text, source)

    try:
        archive_state_to_injected(memory_dir)
    except OSError as exc:
        print(f"[session_start] archive failed (non-fatal): {exc}", file=sys.stderr)

    print(json.dumps({"additionalContext": context}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
