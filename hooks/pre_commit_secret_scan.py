"""Block ``git commit`` when the staged diff adds a known-secret pattern.

Complements ``pre_write_secret_scan.py`` (which guards Edit/Write at
input time) by catching secrets that slipped in through other paths
— direct file writes, ``git add`` of pre-existing files, merges from
other branches — before the commit lands.

Only scans **added lines** (lines starting with ``+`` but not
``+++``). Context lines (pre-existing content) are not re-scanned,
so a secret already in master produces no noise here — that is a
separate rotation/history-rewrite problem.

Bypasses:

* ``[WIP]`` in the commit message.
* ``.git/MERGE_HEAD`` present (conflict resolution commit).

Event: PreToolUse
Matcher: Bash
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from hooks._hook_shared import get_project_dir, read_hook_input

_GIT_COMMIT = re.compile(r"\bgit\s+(?:-[cC]\s+\S+\s+)*commit\b(?!-)")
_WIP_MARKER = re.compile(r"\[WIP\]")

_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("AWS access key ID", re.compile(r"AKIA[A-Z0-9]{16}")),
    ("GitHub token", re.compile(r"gh[posr]_[A-Za-z0-9]{20,}")),
    ("OpenAI API key", re.compile(r"sk-[A-Za-z0-9]{48,}")),
    ("Anthropic API key", re.compile(r"sk-ant-[A-Za-z0-9\-]{20,}")),
    (
        "PEM private key header",
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ),
)

_DIFF_TIMEOUT: int = 5


def _is_git_commit(command: str) -> bool:
    return bool(_GIT_COMMIT.search(command))


def _has_wip_bypass(command: str) -> bool:
    return bool(_WIP_MARKER.search(command))


def _has_merge_head(project_dir: Path) -> bool:
    return (project_dir / ".git" / "MERGE_HEAD").is_file()


def _staged_diff(project_dir: Path) -> str | None:
    """Return the full staged diff, or None on git failure."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--no-color"],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            check=False,
            timeout=_DIFF_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"[secret_scan] could not read staged diff: {exc}", file=sys.stderr)
        return None

    if result.returncode != 0:
        return None
    return result.stdout


def _extract_added_lines(diff: str) -> str:
    """Keep only lines added by the staging (``+`` prefix, not ``+++``)."""
    added: list[str] = []
    for raw in diff.splitlines():
        if raw.startswith("+") and not raw.startswith("+++"):
            added.append(raw[1:])
    return "\n".join(added)


def _scan(text: str) -> str | None:
    for label, pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            return label
    return None


def _extract_command(data: dict[str, object]) -> str:
    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        return ""
    cmd = tool_input.get("command")
    return cmd if isinstance(cmd, str) else ""


def main() -> int:
    data = read_hook_input()

    tool_name = str(data.get("tool_name", ""))
    if tool_name != "Bash":
        return 0

    command = _extract_command(data)
    if not _is_git_commit(command):
        return 0

    if _has_wip_bypass(command):
        return 0

    project_dir = get_project_dir()
    if _has_merge_head(project_dir):
        return 0

    diff = _staged_diff(project_dir)
    if not diff:
        return 0

    added = _extract_added_lines(diff)
    if not added:
        return 0

    found = _scan(added)
    if found:
        print(
            f"[secret_scan] refusing git commit — staged diff adds a {found} pattern. "
            f"Unstage the file (`git reset HEAD <path>`), remove the secret, and "
            f"route it through env vars or a vault before retrying.",
            file=sys.stderr,
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
