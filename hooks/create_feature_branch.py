"""Auto-create a feature branch when a prompt lands on a protected branch.

If the session is currently on ``master``/``main``/etc., this hook
cuts ``feat/<YYYYMMDD-HHMMSS>-<slug>`` from the current HEAD and
checks it out before the prompt is processed, preventing direct
edits to protected branches.

Also writes the full prompt to ``.claude/current-objective.md`` so
downstream verification agents can read it without re-scraping the
transcript.

Exits 0 on every code path — never blocks the prompt. Failure to
cut a branch is logged to stderr; the prompt still lands.

Event: UserPromptSubmit
Matcher: *
"""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from hooks._hook_shared import (
    PROTECTED_BRANCHES,
    get_current_branch,
    get_project_dir,
    read_hook_input,
)
from hooks._os_safe import atomic_write, safe_join

_SLUG_SANITISE_RE = re.compile(r"[^a-z0-9-]+")
_SLUG_COLLAPSE_RE = re.compile(r"-+")


def _slugify(prompt: str, max_len: int = 50) -> str:
    text = prompt.strip().lower()[:max_len]
    text = _SLUG_SANITISE_RE.sub("-", text)
    text = _SLUG_COLLAPSE_RE.sub("-", text).strip("-")
    return text or "untitled"


def _new_branch_name(prompt: str) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return f"feat/{stamp}-{_slugify(prompt)}"


def _run_git(args: list[str], cwd: Path) -> bool:
    try:
        subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            check=True,
            capture_output=True,
            timeout=5,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        print(f"[create_feature_branch] git {' '.join(args)} failed: {exc}", file=sys.stderr)
        return False
    return True


def main() -> int:
    data = read_hook_input()
    prompt = str(data.get("prompt", "")).strip()

    project_dir = get_project_dir()
    branch = get_current_branch(project_dir)

    if branch in PROTECTED_BRANCHES and prompt:
        new_branch = _new_branch_name(prompt)
        if _run_git(["checkout", "-b", new_branch], project_dir):
            print(
                f"[create_feature_branch] cut {new_branch} from {branch}",
                file=sys.stderr,
            )

    if prompt:
        try:
            objective_path = safe_join(project_dir, ".claude", "current-objective.md")
            atomic_write(objective_path, prompt)
        except (OSError, ValueError) as exc:
            print(
                f"[create_feature_branch] could not write current-objective.md: {exc}",
                file=sys.stderr,
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
