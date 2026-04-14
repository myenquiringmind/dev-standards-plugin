"""Session-state round-trip engine for dev-standards-plugin hooks.

Provides the primitives that session boundary hooks (session_start,
session_end, pre_compact, post_compact) use to persist and restore
state across session boundaries.

Public surface:

* ``get_memory_dir(project_dir)`` — derive the auto memory directory.
* ``extract_from_transcript(path)`` — parse a CC transcript (JSONL).
* ``get_git_state(project_dir)`` — capture status / diff / branch.
* ``write_session_state(data, project_dir, *, header_note="")`` — write
  ``session-state.md`` atomically.
* ``parse_todos_from_markdown(text)`` — recover todos from a
  previously written ``session-state.md`` so a restored session can
  reinstate them.
* ``archive_state_to_injected(memory_dir)`` — rename the state file
  to ``session-state.md.injected`` (never deletes — preserves state
  if a crash occurs during load).

Event: N/A (shared module, not a hook)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hooks._os_safe import atomic_write

# ---------------------------------------------------------------------------
# Memory directory resolution
# ---------------------------------------------------------------------------


def get_memory_dir(project_dir: str | Path) -> Path:
    """Derive the auto-memory directory for a project.

    The slug is produced by replacing ``/``, ``\\`` and ``:`` with
    ``-`` in the project's absolute path and stripping any leading
    ``-``. Result: ``~/.claude/projects/<slug>/memory/``.

    Args:
        project_dir: Project root path.

    Returns:
        Absolute ``Path`` to the memory directory (may not yet exist).
    """
    raw = str(project_dir)
    slug = raw.replace("/", "-").replace("\\", "-").replace(":", "-")
    slug = slug.lstrip("-")
    return Path.home() / ".claude" / "projects" / slug / "memory"


# ---------------------------------------------------------------------------
# Transcript parsing
# ---------------------------------------------------------------------------


def extract_from_transcript(path: str | Path) -> dict[str, Any]:
    """Parse a JSONL transcript for the key session-state fields.

    Reads the file line-by-line; malformed lines are skipped. The
    extraction is deliberately lenient — a partial transcript is
    better than nothing.

    Args:
        path: Path to the transcript JSONL file.

    Returns:
        Dict with keys ``modified_files`` (sorted list),
        ``last_user_prompt`` (str, truncated to 500 chars),
        ``todos`` (list of the last TodoWrite payload),
        ``errors`` (last 3 truncated error strings),
        ``recent_reasoning`` (last 2 truncated assistant messages).
    """
    modified_files: set[str] = set()
    last_user_prompt = ""
    todos: list[dict[str, Any]] = []
    errors: list[str] = []
    recent_reasoning: list[str] = []

    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                etype = entry.get("type", "")

                if etype == "tool_use":
                    tool = entry.get("tool_name", "")
                    tinput = entry.get("tool_input", {})
                    if tool in ("Write", "Edit") and "file_path" in tinput:
                        modified_files.add(tinput["file_path"])
                    if tool == "TodoWrite" and "todos" in tinput:
                        todos = tinput["todos"]

                elif etype == "human":
                    last_user_prompt = _extract_text(entry.get("content", ""))[:500]

                elif etype == "assistant":
                    text = _extract_text(entry.get("content", ""))
                    if text.strip():
                        recent_reasoning.append(text[:400])
                        recent_reasoning = recent_reasoning[-3:]

                elif etype == "tool_result" and entry.get("is_error"):
                    errors.append(str(entry.get("content", ""))[:200])
                    errors = errors[-5:]

    except OSError as exc:
        print(f"[session_state] Could not read transcript: {exc}", file=sys.stderr)

    return {
        "modified_files": sorted(modified_files),
        "last_user_prompt": last_user_prompt,
        "todos": todos,
        "errors": errors[-3:],
        "recent_reasoning": recent_reasoning[-2:],
    }


def _extract_text(content: Any) -> str:
    """Pull plain text from a string or a list of content blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "")
                if isinstance(text, str):
                    return text
    return ""


# ---------------------------------------------------------------------------
# Git state capture
# ---------------------------------------------------------------------------


def get_git_state(project_dir: str | Path) -> str:
    """Capture git status, diff stat, and current branch as markdown.

    Each git command has a 5-second timeout; failures are logged to
    stderr and skipped — the return value contains whichever sections
    succeeded. Empty string if nothing produced output.

    Args:
        project_dir: Working directory for the git commands.

    Returns:
        Markdown string with ``### Git Status`` / ``### Uncommitted
        Changes`` / ``### Current Branch`` sections, or ``""``.
    """
    lines: list[str] = []
    commands: list[tuple[list[str], str]] = [
        (["git", "status", "--short"], "Git Status"),
        (["git", "diff", "--stat"], "Uncommitted Changes"),
        (["git", "branch", "--show-current"], "Current Branch"),
    ]
    for cmd, header in commands:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(project_dir),
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            print(f"[session_state] git command failed: {exc}", file=sys.stderr)
            continue

        if result.returncode == 0 and result.stdout.strip():
            lines.append(f"### {header}")
            lines.append(f"```\n{result.stdout.strip()}\n```")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Session state writer
# ---------------------------------------------------------------------------

_TODO_ICONS: dict[str, str] = {
    "completed": "[x]",
    "in_progress": "[~]",
    "pending": "[ ]",
}


def write_session_state(
    data: dict[str, Any],
    project_dir: str | Path,
    *,
    header_note: str = "",
) -> Path:
    """Write ``session-state.md`` atomically to the memory directory.

    Uses :func:`hooks._os_safe.atomic_write` so concurrent session
    hooks cannot corrupt the file.

    Args:
        data: Output of :func:`extract_from_transcript`.
        project_dir: Project root — used to derive the memory dir.
        header_note: Optional note appended to the snapshot header
            (e.g. ``"Pre-compaction snapshot"``).

    Returns:
        Absolute ``Path`` to the written file.
    """
    mem_dir = get_memory_dir(project_dir)
    state_path = mem_dir / "session-state.md"

    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    header = f"# Session State Snapshot\n*Captured: {timestamp}*"
    if header_note:
        header += f"\n*{header_note}*"

    lines: list[str] = [header, ""]

    if data.get("last_user_prompt"):
        lines += ["## Active Request", data["last_user_prompt"], ""]

    if data.get("todos"):
        lines.append("## Task Progress")
        for todo in data["todos"]:
            icon = _TODO_ICONS.get(todo.get("status", ""), "[ ]")
            lines.append(f"- {icon} {todo.get('content', '?')}")
        lines.append("")

    if data.get("modified_files"):
        lines.append("## Files Modified")
        for file_path in data["modified_files"]:
            lines.append(f"- `{file_path}`")
        lines.append("")

    git = get_git_state(project_dir)
    if git:
        lines += ["## Repository State", git, ""]

    if data.get("errors"):
        lines.append("## Recent Errors")
        for err in data["errors"]:
            lines.append(f"- {err}")
        lines.append("")

    if data.get("recent_reasoning"):
        lines.append("## Recent Context")
        for msg in data["recent_reasoning"]:
            lines.append(f"> {msg[:300]}")
            lines.append("")

    content = "\n".join(lines)
    return atomic_write(state_path, content)


# ---------------------------------------------------------------------------
# Todo parsing (reverse of the writer)
# ---------------------------------------------------------------------------

_TODO_LINE_RE = re.compile(r"^- \[([ ~xX])\] (.+)$")
_STATUS_BY_MARKER: dict[str, str] = {
    " ": "pending",
    "~": "in_progress",
    "x": "completed",
    "X": "completed",
}


def parse_todos_from_markdown(text: str) -> list[dict[str, str]]:
    """Recover todos from a previously written ``session-state.md``.

    Scans the text for the ``## Task Progress`` section and extracts
    every ``- [ ] ...`` / ``- [~] ...`` / ``- [x] ...`` line until
    the next heading or blank section terminator.

    Args:
        text: Full contents of the markdown file.

    Returns:
        List of ``{"content": str, "status": str}`` dicts in the same
        order they appeared. ``status`` is one of ``"pending"``,
        ``"in_progress"``, ``"completed"``.
    """
    todos: list[dict[str, str]] = []
    in_section = False

    for raw_line in text.splitlines():
        line = raw_line.rstrip()

        if line.startswith("## "):
            # Entering Task Progress, or leaving it for another section.
            in_section = line.strip() == "## Task Progress"
            continue

        if not in_section:
            continue

        match = _TODO_LINE_RE.match(line)
        if match:
            marker, content = match.group(1), match.group(2)
            todos.append(
                {
                    "content": content.strip(),
                    "status": _STATUS_BY_MARKER[marker],
                }
            )

    return todos


# ---------------------------------------------------------------------------
# Archive helper
# ---------------------------------------------------------------------------


def archive_state_to_injected(memory_dir: str | Path) -> Path | None:
    """Rename ``session-state.md`` to ``session-state.md.injected``.

    Called by ``session_start.py`` once the state has been injected
    into the new session. The rename (rather than delete) preserves
    the file if CC crashes between injection and archival.

    Uses ``os.replace`` so any stale ``.injected`` from a prior
    session is overwritten atomically.

    Args:
        memory_dir: Directory containing ``session-state.md``.

    Returns:
        ``Path`` to the new ``.injected`` file, or ``None`` if the
        source did not exist (no-op).
    """
    mem_dir = Path(memory_dir)
    source = mem_dir / "session-state.md"
    target = mem_dir / "session-state.md.injected"

    if not source.exists():
        return None

    os.replace(str(source), str(target))
    return target
