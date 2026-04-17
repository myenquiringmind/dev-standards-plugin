"""Block Edit/Write when content contains a known-secret pattern.

Catches the common credential shapes before they touch disk:

* AWS access key IDs   ``AKIA[A-Z0-9]{16}``
* GitHub tokens        ``gh[posr]_[A-Za-z0-9]{20,}``
* OpenAI keys          ``sk-[A-Za-z0-9]{48,}``
* Anthropic keys       ``sk-ant-[A-Za-z0-9\\-]{20,}``
* PEM private keys     ``-----BEGIN ... PRIVATE KEY-----``

Also refuses writes to forbidden filenames (``.env``, ``*.pem``,
``credentials.json``, ``secrets.json``, ``*.key``) regardless of
content — such files should not exist in the repo at all.

Not exhaustive. Supplements, not replaces, human review.

Event: PreToolUse
Matcher: Edit|Write|MultiEdit
"""

from __future__ import annotations

import re
import sys
from fnmatch import fnmatch
from pathlib import PurePosixPath

from hooks._hook_shared import read_hook_input

_EDIT_TOOLS: frozenset[str] = frozenset({"Edit", "Write", "MultiEdit"})

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

_FORBIDDEN_FILENAME_GLOBS: tuple[str, ...] = (
    ".env",
    ".env.*",
    "credentials.json",
    "secrets.json",
    "*.pem",
    "*.key",
)


def _filename_is_forbidden(path: str) -> bool:
    if not path:
        return False
    name = PurePosixPath(path.replace("\\", "/")).name
    return any(fnmatch(name, pattern) for pattern in _FORBIDDEN_FILENAME_GLOBS)


def _scan(text: str) -> str | None:
    if not text:
        return None
    for label, pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            return label
    return None


def _collect_content(tool_input: dict[str, object]) -> str:
    parts: list[str] = []
    for key in ("content", "new_string", "old_string"):
        value = tool_input.get(key)
        if isinstance(value, str):
            parts.append(value)
    edits = tool_input.get("edits")
    if isinstance(edits, list):
        for edit in edits:
            if isinstance(edit, dict):
                for key in ("new_string", "old_string"):
                    value = edit.get(key)
                    if isinstance(value, str):
                        parts.append(value)
    return "\n".join(parts)


def main() -> int:
    data = read_hook_input()
    tool_name = str(data.get("tool_name", ""))
    if tool_name not in _EDIT_TOOLS:
        return 0

    tool_input = data.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return 0

    file_path = str(tool_input.get("file_path", ""))
    if _filename_is_forbidden(file_path):
        print(
            f"[secret_scan] refusing {tool_name} on forbidden filename '{file_path}'. "
            f"Secret-bearing files must not be committed.",
            file=sys.stderr,
        )
        return 2

    found = _scan(_collect_content(tool_input))
    if found:
        print(
            f"[secret_scan] refusing {tool_name} — detected {found} pattern in the "
            f"content. Remove the secret or route it through env vars / a vault.",
            file=sys.stderr,
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
