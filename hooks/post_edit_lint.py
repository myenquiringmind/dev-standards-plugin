"""Run the profile's linter on a file after CC edits it.

Post-edit feedback only — never blocks the tool. When a supported
file lands (language detected from its extension matches a profile
in ``config/profiles/``), this hook runs the profile's ``linter``
tool and surfaces any output on stderr. Files with no matching
profile are silently skipped.

Event: PostToolUse
Matcher: Edit|Write|MultiEdit
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from hooks._hook_shared import get_project_dir, read_hook_input
from hooks._os_safe import normalize_path
from hooks._profiles import build_tool_argv, detect_language, load_profile

_SUBPROCESS_TIMEOUT: int = 5


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


def main() -> int:
    data = read_hook_input()

    file_path = _extract_file_path(data)
    if file_path is None:
        return 0

    resolved = normalize_path(file_path)
    if not resolved.is_file():
        return 0

    project_dir: Path = get_project_dir()
    language = detect_language(resolved, project_dir)
    if language is None:
        return 0

    profile = load_profile(language, project_dir)
    if profile is None:
        return 0

    linter_spec = None
    tools = profile.get("tools")
    if isinstance(tools, dict):
        linter_spec = tools.get("linter")

    argv = build_tool_argv(linter_spec, str(resolved))
    if argv is None:
        return 0

    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
            check=False,
        )
    except FileNotFoundError:
        print(
            f"[post_edit_lint] {language} linter '{argv[0]}' not found on PATH",
            file=sys.stderr,
        )
        return 0
    except subprocess.TimeoutExpired:
        print(
            f"[post_edit_lint] {language} linter timed out after {_SUBPROCESS_TIMEOUT}s",
            file=sys.stderr,
        )
        return 0
    except OSError as exc:
        print(f"[post_edit_lint] could not run linter: {exc}", file=sys.stderr)
        return 0

    if result.returncode != 0:
        output = (result.stdout + result.stderr).strip()
        if output:
            print(
                f"[post_edit_lint] {language} issues in {resolved.name}:\n{output}",
                file=sys.stderr,
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
