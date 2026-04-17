"""Language-profile discovery and command-shape helpers for post_* hooks.

Reads ``config/profiles/<lang>.json`` and maps an edited file to the
profile whose ``detection.extensions`` claim it. Consumed by
``post_edit_lint.py`` and ``post_auto_format.py``; both want the
same "given a file path, what should I run on it?" answer.

Event: N/A (shared module, not a hook)
"""

from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Any


def _iter_profile_paths(project_dir: Path) -> list[Path]:
    profiles_dir = project_dir / "config" / "profiles"
    if not profiles_dir.is_dir():
        return []
    return sorted(profiles_dir.glob("*.json"))


def _load_profile_file(path: Path) -> dict[str, Any] | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def detect_language(file_path: str | Path, project_dir: str | Path) -> str | None:
    """Return the profile name whose detection claims ``file_path``.

    Matching is by file extension (``.py``, ``.ts``, etc.). The first
    profile (alphabetically) that lists the extension wins.

    Args:
        file_path: Path of the edited file.
        project_dir: Project root containing ``config/profiles/``.

    Returns:
        Profile ``name`` (e.g. ``"python"``) or ``None`` if no profile
        claims the file.
    """
    ext = Path(file_path).suffix.lower()
    if not ext:
        return None

    for profile_path in _iter_profile_paths(Path(project_dir)):
        data = _load_profile_file(profile_path)
        if data is None:
            continue
        detection = data.get("detection", {})
        if not isinstance(detection, dict):
            continue
        extensions = detection.get("extensions", [])
        if isinstance(extensions, list) and ext in extensions:
            name = data.get("name")
            return str(name) if isinstance(name, str) else profile_path.stem

    return None


def load_profile(language: str, project_dir: str | Path) -> dict[str, Any] | None:
    """Return the parsed profile JSON for *language*, or ``None``.

    Args:
        language: Profile name (e.g. ``"python"``).
        project_dir: Project root containing ``config/profiles/``.

    Returns:
        Parsed profile dict, or ``None`` if the file does not exist,
        is unreadable, or is not valid JSON.
    """
    path = Path(project_dir) / "config" / "profiles" / f"{language}.json"
    return _load_profile_file(path)


def build_tool_argv(
    tool_spec: dict[str, Any] | None,
    file_path: str,
) -> list[str] | None:
    """Turn a profile tool-spec into a subprocess argv list.

    Substitutes ``{file}`` in the command template with *file_path*.
    Any ``args`` array in the tool-spec is appended after the
    substituted command. Uses :func:`shlex.split` with ``posix=False``
    so Windows paths with backslashes survive tokenisation.

    Args:
        tool_spec: The ``tools.formatter`` / ``tools.linter`` block
            from a profile, or ``None`` (convenience — returns ``None``).
        file_path: Absolute path of the file to feed in for ``{file}``.

    Returns:
        A list of argv tokens, or ``None`` if *tool_spec* is missing
        a usable ``command`` field.
    """
    if not isinstance(tool_spec, dict):
        return None
    template = tool_spec.get("command")
    if not isinstance(template, str) or not template.strip():
        return None

    substituted = template.replace("{file}", file_path)
    argv = shlex.split(substituted, posix=False)

    args = tool_spec.get("args")
    if isinstance(args, list):
        argv.extend(str(a) for a in args if isinstance(a, str))

    return argv
