"""CLI: append agent-authored content to that agent's persistent memory.

Read-only agents (read/reason tiers) cannot write files themselves.
Instead they shell out to this script via Bash:

    echo "learning text" | uv run python -m hooks.write_agent_memory \
        --agent py-solid-dry-reviewer --append

The content (stdin) is appended (or replaces) the file at
``<memory_root>/<agent-name>/MEMORY.md`` where *memory_root* is the
first of:

* ``$CLAUDE_PLUGIN_DATA/agent-memory``
* ``$CLAUDE_PROJECT_DIR/.claude/agent-memory``
* ``<project_dir>/.claude/agent-memory`` (from ``get_project_dir()``)

Agent names must match ``^[a-z0-9][a-z0-9-]*$`` — no dots, no
slashes, no parent-directory escapes. This is the Phase 1 exit gate
assertion #8: ``--agent ../../etc/passwd`` must be rejected.

Exit codes:
* 0 — memory written
* 1 — validation failure (bad agent name, unsafe path, I/O error)

Event: N/A (CLI utility invoked by subagents; not a hook)
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from hooks._hook_shared import get_project_dir
from hooks._os_safe import atomic_write, safe_join

if TYPE_CHECKING:
    from collections.abc import Sequence


_AGENT_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="write_agent_memory")
    parser.add_argument(
        "--agent",
        required=True,
        help="Agent identifier. Must match ^[a-z0-9][a-z0-9-]*$.",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to the existing memory file (default; the flag is explicit for clarity).",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace the memory file instead of appending.",
    )
    return parser.parse_args(argv)


def _resolve_memory_root(project_dir: Path) -> Path:
    env_plugin = os.environ.get("CLAUDE_PLUGIN_DATA")
    if env_plugin:
        return Path(env_plugin) / "agent-memory"
    env_project = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_project:
        return Path(env_project) / ".claude" / "agent-memory"
    return project_dir / ".claude" / "agent-memory"


def _validate_agent_name(name: str) -> bool:
    return bool(_AGENT_NAME_RE.match(name))


def _compose_entry(content: str) -> str:
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"\n## {timestamp}\n\n{content.rstrip()}\n"


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 1

    if args.append and args.replace:
        print(
            "[write_agent_memory] --append and --replace are mutually exclusive", file=sys.stderr
        )
        return 1

    if not _validate_agent_name(args.agent):
        print(
            f"[write_agent_memory] refusing unsafe agent name: '{args.agent}'. "
            "Must match ^[a-z0-9][a-z0-9-]*$ (kebab-case, no dots, no slashes).",
            file=sys.stderr,
        )
        return 1

    content = sys.stdin.read()
    if not content.strip():
        print("[write_agent_memory] refusing empty content on stdin", file=sys.stderr)
        return 1

    project_dir = get_project_dir()
    memory_root = _resolve_memory_root(project_dir)
    try:
        target = safe_join(memory_root, args.agent, "MEMORY.md")
    except ValueError as exc:
        print(f"[write_agent_memory] unsafe path: {exc}", file=sys.stderr)
        return 1

    replace = args.replace
    try:
        if replace or not target.exists():
            body = content.rstrip() + "\n" if replace else _compose_entry(content)
            atomic_write(target, body)
        else:
            existing = target.read_text(encoding="utf-8")
            atomic_write(target, existing.rstrip() + _compose_entry(content))
    except OSError as exc:
        print(f"[write_agent_memory] could not write memory: {exc}", file=sys.stderr)
        return 1

    mode = "replaced" if replace else "appended"
    print(f"[write_agent_memory] {mode} {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
