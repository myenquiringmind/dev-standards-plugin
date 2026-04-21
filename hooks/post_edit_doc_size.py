"""Block markdown edits that push a file past its configured line limit.

Per-pattern limits live in ``config/doc-size-limits.json``. The first
matching pattern wins, otherwise ``default`` applies. A limit of -1
means "no limit" and exempts the file.

Exit 2 when an edit lands a file over its limit — CC surfaces the
blocking error to the model so the next turn can split or compress.

Event: PostToolUse
Matcher: Edit|Write|MultiEdit
"""

from __future__ import annotations

import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any

from hooks._hook_shared import get_project_dir, read_hook_input
from hooks._os_safe import normalize_path

_DEFAULT_LIMIT: int = 200


def _extract_file_path(data: dict[str, object]) -> str | None:
    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        return None

    direct = tool_input.get("file_path")
    if isinstance(direct, str) and direct:
        return direct

    files = tool_input.get("files")
    if isinstance(files, list):
        for entry in files:
            if isinstance(entry, dict):
                value = entry.get("file_path")
                if isinstance(value, str) and value:
                    return value
    return None


def _load_config(project_dir: Path) -> dict[str, Any]:
    config_path = project_dir / "config" / "doc-size-limits.json"
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
    except (OSError, json.JSONDecodeError):
        return {}


def _matches(path: str, glob: str) -> bool:
    normalised = PurePosixPath(path.replace("\\", "/"))
    return normalised.full_match(glob)


def _limit_for(rel_path: str, config: dict[str, Any]) -> int:
    patterns = config.get("patterns", [])
    if isinstance(patterns, list):
        for entry in patterns:
            if not isinstance(entry, dict):
                continue
            glob = entry.get("glob")
            limit = entry.get("limit")
            if isinstance(glob, str) and isinstance(limit, int) and _matches(rel_path, glob):
                return limit
    default = config.get("default", _DEFAULT_LIMIT)
    return default if isinstance(default, int) else _DEFAULT_LIMIT


def main() -> int:
    data = read_hook_input()

    file_path = _extract_file_path(data)
    if file_path is None:
        return 0

    resolved = normalize_path(file_path)
    if resolved.suffix.lower() != ".md":
        return 0
    if not resolved.is_file():
        return 0

    project_dir = get_project_dir()
    try:
        rel = resolved.relative_to(project_dir.resolve())
    except ValueError:
        rel = Path(resolved.name)

    config = _load_config(project_dir)
    limit = _limit_for(str(rel), config)
    if limit < 0:
        return 0

    try:
        with resolved.open(encoding="utf-8") as handle:
            line_count = sum(1 for _ in handle)
    except OSError as exc:
        print(f"[post_edit_doc_size] could not read {resolved.name}: {exc}", file=sys.stderr)
        return 0

    if line_count > limit:
        print(
            f"[post_edit_doc_size] refusing {resolved.name} — {line_count} lines exceeds "
            f"limit {limit}. Split or compress before continuing.",
            file=sys.stderr,
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
