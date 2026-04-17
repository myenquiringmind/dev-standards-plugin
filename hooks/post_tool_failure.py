"""Append a rolling log of tool failures to the memory directory.

When CC reports ``is_error: true`` on a tool result, this hook grabs
the tool name, a small slice of relevant context (file path, command,
or pattern), and the first line of the error message, and appends a
timestamped entry to ``<memory>/error-log.md``. The log is capped at
the most recent 50 entries — older ones roll off.

The file is intended as a debugging breadcrumb trail, not a long-term
audit log. A session that hits a run of similar failures can read
the log to spot a pattern without re-scraping the transcript.

Event: PostToolUse
Matcher: *
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

from hooks._hook_shared import get_project_dir, read_hook_input
from hooks._os_safe import atomic_write
from hooks._session_state_common import get_memory_dir

_MAX_ENTRIES: int = 50
_MESSAGE_TRUNCATE: int = 240


def _is_error(data: dict[str, object]) -> bool:
    for key in ("tool_result", "toolResult"):
        value = data.get(key)
        if isinstance(value, dict) and value.get("is_error") is True:
            return True
    return bool(data.get("is_error"))


def _context_snippet(tool_input: object) -> str:
    if not isinstance(tool_input, dict):
        return ""
    parts: list[str] = []
    for key in ("file_path", "command", "pattern", "url", "path"):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            parts.append(f"{key}={value}")
    return " ".join(parts)


def _error_message(data: dict[str, object]) -> str:
    for key in ("tool_result", "toolResult"):
        result = data.get(key)
        if isinstance(result, dict):
            content = result.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        text = block.get("text")
                        if isinstance(text, str) and text.strip():
                            return text.strip()
    error = data.get("error")
    if isinstance(error, str) and error.strip():
        return error.strip()
    return ""


def _truncate_first_line(text: str, limit: int = _MESSAGE_TRUNCATE) -> str:
    if not text:
        return ""
    first = text.splitlines()[0]
    return first if len(first) <= limit else first[: limit - 1] + "…"


def _build_entry(data: dict[str, object]) -> str:
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    tool_name = str(data.get("tool_name", "unknown"))
    header = f"### {timestamp} — {tool_name} failure"

    lines: list[str] = [header]
    context = _context_snippet(data.get("tool_input"))
    if context:
        lines.append(f"- {context}")

    message = _truncate_first_line(_error_message(data))
    if message:
        lines.append(f"- error: {message}")

    lines.append("")
    return "\n".join(lines)


def _split_into_entries(text: str) -> list[str]:
    if not text.strip():
        return []
    entries: list[str] = []
    buffer: list[str] = []
    for line in text.splitlines():
        if line.startswith("### ") and buffer:
            entries.append("\n".join(buffer).rstrip() + "\n")
            buffer = []
        buffer.append(line)
    if buffer:
        entries.append("\n".join(buffer).rstrip() + "\n")
    return entries


def main() -> int:
    data = read_hook_input()
    if not _is_error(data):
        return 0

    memory_dir = get_memory_dir(get_project_dir())
    log_path: Path = memory_dir / "error-log.md"

    existing = ""
    if log_path.exists():
        try:
            existing = log_path.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"[post_tool_failure] could not read log: {exc}", file=sys.stderr)

    entry = _build_entry(data)
    previous = _split_into_entries(existing)[-(_MAX_ENTRIES - 1) :]
    content = entry + "\n".join(previous).rstrip()
    if not content.endswith("\n"):
        content += "\n"

    try:
        atomic_write(log_path, content)
    except OSError as exc:
        print(f"[post_tool_failure] could not write log: {exc}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
