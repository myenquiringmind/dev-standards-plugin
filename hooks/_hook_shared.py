"""Shared utilities and constants for dev-standards-plugin hooks.

Single source of truth for hook input parsing, branch detection,
project directory resolution, context budget thresholds, validation
step tuples, and pack activation checks.

Event: N/A (shared module, not a hook)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Context budget thresholds
# ---------------------------------------------------------------------------

#: Context percentage at which advisory warnings begin.
WARN_CONTEXT_PCT: int = 80

#: Context percentage at which the hard block fires (must /handoff).
CRITICAL_CONTEXT_PCT: int = 95

#: Fraction of the active model's window where CC auto-compacts.
CC_COMPACTION_FRACTION: float = 0.835

#: The framework's hard cut is 75% of the compaction threshold.
HARD_CUT_FRACTION: float = 0.75

# ---------------------------------------------------------------------------
# Handoff protocol steps
# ---------------------------------------------------------------------------

HANDOFF_STEPS: str = (
    "1. Commit current work (WIP if incomplete)\n"
    "2. Update session memory with: what was done, what remains, current git state\n"
    "3. Note the current branch and commit hash\n"
    "4. List the next objective and its acceptance criteria\n"
    "5. Signal ready for /clear"
)

# ---------------------------------------------------------------------------
# Validation step tuples — single source of truth
# ---------------------------------------------------------------------------

#: Python code validation gate.
PY_VALIDATION_STEPS: tuple[str, ...] = (
    "ruff-check",
    "ruff-format",
    "mypy-strict",
    "pytest",
    "objective-verifier",
    "py-solid-dry-reviewer",
    "py-security-reviewer",
    "py-doc-checker",
    "py-arch-doc-reviewer",
    "py-code-simplifier",
    "py-tdd-process-reviewer",
)

#: Frontend code validation gate.
FE_VALIDATION_STEPS: tuple[str, ...] = (
    "eslint",
    "tsc-strict",
    "vitest",
    "fe-code-simplifier",
    "fe-security-reviewer",
    "fe-doc-checker",
    "fe-component-reviewer",
)

#: Agent infrastructure validation gate.
AGENT_VALIDATION_STEPS: tuple[str, ...] = (
    "agent-arch-doc-reviewer",
    "command-composition-reviewer",
)

# ---------------------------------------------------------------------------
# Cache intervals (seconds)
# ---------------------------------------------------------------------------

#: How long a validation stamp remains valid.
STAMP_TTL: int = 900  # 15 minutes

#: How often session_checkpoint writes state (in qualifying edit events).
CHECKPOINT_INTERVAL_EVENTS: int = 5

#: How often session_checkpoint writes state (seconds).
CHECKPOINT_INTERVAL_SECONDS: int = 900  # 15 minutes

# ---------------------------------------------------------------------------
# Protected branches
# ---------------------------------------------------------------------------

PROTECTED_BRANCHES: frozenset[str] = frozenset(
    {
        "master",
        "main",
        "production",
        "develop",
        "staging",
        "release",
    }
)


# ---------------------------------------------------------------------------
# Hook input parsing
# ---------------------------------------------------------------------------


def read_hook_input() -> dict[str, Any]:
    """Read and parse JSON from stdin (the CC hook input payload).

    Returns:
        Parsed dict. Returns an empty dict if stdin is empty or
        contains malformed JSON — hooks must handle missing keys
        defensively.
    """
    try:
        raw = sys.stdin.read()
    except Exception:
        return {}

    if not raw.strip():
        return {}

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}

    if not isinstance(data, dict):
        return {}

    return data


# ---------------------------------------------------------------------------
# Project and git helpers
# ---------------------------------------------------------------------------


def get_project_dir() -> Path:
    """Resolve the project root directory.

    Reads ``CLAUDE_PROJECT_DIR`` if set, otherwise walks up from
    ``hooks/`` to find the repo root.

    Returns:
        Absolute ``Path`` to the project root.
    """
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env).resolve()
    # Fallback: this file is hooks/_hook_shared.py → parent.parent is project root
    return Path(__file__).resolve().parent.parent


def get_current_branch(project_dir: str | Path | None = None) -> str:
    """Read the current git branch from ``.git/HEAD``.

    Reads the file directly to avoid subprocess overhead.

    Args:
        project_dir: Project root containing ``.git/``. Defaults to
            ``get_project_dir()``.

    Returns:
        Branch name (e.g. ``feat/phase-0b-shared-modules``), the
        commit hash if HEAD is detached, or ``""`` if unreadable.
    """
    if project_dir is None:
        project_dir = get_project_dir()

    head_path = Path(project_dir) / ".git" / "HEAD"
    try:
        ref = head_path.read_text(encoding="utf-8").strip()
    except (FileNotFoundError, OSError):
        return ""

    if ref.startswith("ref: refs/heads/"):
        return ref.removeprefix("ref: refs/heads/")
    return ref  # detached HEAD — return the hash


def read_cached_pct(project_dir: str | Path | None = None) -> int | None:
    """Read the cached context usage percentage.

    Written by ``statusline.py`` to ``.claude/.context_pct``.

    Returns:
        Integer 0-100, or ``None`` if the cache is unavailable.
    """
    if project_dir is None:
        project_dir = get_project_dir()

    cache_path = Path(project_dir) / ".claude" / ".context_pct"
    try:
        return int(cache_path.read_text(encoding="utf-8").strip())
    except (FileNotFoundError, ValueError, OSError):
        return None


# ---------------------------------------------------------------------------
# Context budget computation
# ---------------------------------------------------------------------------


def compute_hard_cut(model_window: int) -> int:
    """Compute the framework's dynamic hard cut in tokens.

    The hard cut is 75% of CC's compaction threshold, which itself
    is ~83.5% of the active model's window.

    Args:
        model_window: The active model's context window in tokens.

    Returns:
        Token count at which the hard cut fires.
    """
    compaction_threshold = int(model_window * CC_COMPACTION_FRACTION)
    return int(compaction_threshold * HARD_CUT_FRACTION)


# ---------------------------------------------------------------------------
# Feature pack activation
# ---------------------------------------------------------------------------


def is_pack_active(pack_name: str, project_dir: str | Path | None = None) -> bool:
    """Check whether a feature pack is active for this project.

    Reads ``config/user-config.json`` (if it exists) for the list of
    active packs. The ``core`` pack is always active.

    Args:
        pack_name: Pack name (e.g. ``"python"``, ``"frontend"``).
        project_dir: Project root. Defaults to ``get_project_dir()``.

    Returns:
        ``True`` if the pack is active, ``False`` otherwise.
    """
    if pack_name == "core":
        return True

    if project_dir is None:
        project_dir = get_project_dir()

    config_path = Path(project_dir) / "config" / "user-config.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        # No config file → only core is active.
        return False

    active_packs = config.get("activePacks", [])
    if not isinstance(active_packs, list):
        return False

    return pack_name in active_packs
