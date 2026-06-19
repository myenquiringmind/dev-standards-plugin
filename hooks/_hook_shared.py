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
#
# These thresholds are expressed in **framework_pct** space — the value
# ``statusline.py`` writes to ``.claude/.context_pct``. ``framework_pct``
# is ``raw_window_pct / (CC_COMPACTION_FRACTION * HARD_CUT_FRACTION)``:
#
# * ``framework_pct == 100`` is exactly the framework hard cut
#   (``compute_hard_cut(window)``, ~62.625% of the active model window).
# * ``framework_pct >= 100`` means the session is at or past the hard cut
#   and ``context_budget.py`` must block (exit 2) until ``/handoff``.
# * ``framework_pct >= 133`` means CC auto-compaction has already fired —
#   too late for the framework to enforce its own principle.
#
# ``CRITICAL_CONTEXT_PCT`` is therefore pinned to 100 (the principle).
# ``WARN_CONTEXT_PCT`` sits at 80% of the hard cut, leaving the planner a
# few-turn cushion to land a clean ``/handoff`` before the block fires.

#: Context percentage at which advisory warnings begin (80% of hard cut).
WARN_CONTEXT_PCT: int = 80

#: Context percentage at which the hard block fires — exactly the framework
#: hard cut in framework_pct space. See ``compute_hard_cut`` and
#: ``compute_hard_cut_pct`` for the underlying token computation.
CRITICAL_CONTEXT_PCT: int = 100

#: Fraction of the active model's window where CC auto-compacts.
CC_COMPACTION_FRACTION: float = 0.835

#: The framework's hard cut is 75% of the compaction threshold.
HARD_CUT_FRACTION: float = 0.75

# ---------------------------------------------------------------------------
# Context-percentage fallback writer (TR-0004 step 3)
# ---------------------------------------------------------------------------
#
# ``statusline.py`` is a CC ``statusLine`` command, not a hook — plugins
# cannot ship the wiring, the user must add it to ``~/.claude/settings.json``
# (see ``docs/guides/statusline-wiring.md``). Until that happens (or when
# CC does not invoke the statusline at session start), ``.claude/.context_pct``
# does not exist and ``context_budget.py`` runs in advisory-only mode. The
# fallback writer (``hooks/context_pct_writer.py``) closes that gap by
# estimating ``framework_pct`` from the transcript file size.
#
# The constants below are deliberately conservative: a smaller bytes-per-
# token estimate over-counts tokens, and the smallest common window
# (Sonnet/Opus 200K) over-reports ``framework_pct`` when the actual model
# is Opus 1M. Both biases push the warn/block earlier, which is the safe
# failure mode for a monitoring fallback.

#: Default model window assumed when the active window is unknown.
#: Sonnet and Opus base both ship at 200K; Opus 1M is opt-in. Using the
#: smaller value over-reports framework_pct on a 1M session, which fires
#: the handoff earlier than strictly necessary — safe vs the alternative
#: (under-reporting and missing the cut).
FALLBACK_WINDOW_TOKENS: int = 200_000

#: Conservative bytes-per-token estimate for the JSONL transcript. Real
#: English text is closer to 3.5-4 bytes per token; JSON overhead pushes
#: this up. Picking 3 over-counts tokens, biasing framework_pct high.
BYTES_PER_TOKEN_ESTIMATE: int = 3

#: How recently ``.claude/.context_pct`` must have been written for the
#: fallback to defer to it. When ``statusline.py`` is wired it fires on
#: every CC turn, so a value newer than this is taken as evidence the
#: statusline is active and producing the authoritative reading.
STATUSLINE_STALENESS_SECONDS: int = 60

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
#
# Each tuple lists the *currently available* canonical validation steps for
# its gate. A stamp must cover every step here (superset check in
# ``pre_commit_cli_gate.py``).
#
# Growth history:
#
# * Phase 1 shipped the narrowed initial sets.
# * Phase 2 added ``agent-arch-doc-reviewer`` to ``AGENT_VALIDATION_STEPS``.
# * Phase 6 added the seven *universally-applicable* ``py-*`` stack reviewers
#   (solid-dry, security, doc-checker, arch-doc, code-simplifier, tdd-process,
#   logging) to ``PY_VALIDATION_STEPS``. The two *conditional* Python
#   reviewers — ``py-migration-reviewer`` and ``py-api-reviewer`` — are
#   deliberately NOT in the tuple: they scope themselves to migration / API
#   files and no-op on any other diff, so requiring them in every code stamp
#   would force wasted reviews (and a misleading "migration reviewed" claim)
#   on changes with no migrations or endpoints. ``/validate`` dispatches them
#   on demand and adds them to the stamp only when relevant files are staged.
#   The ``fe-*`` stack agents grow ``FE_VALIDATION_STEPS`` in the same way.
#
# A canonical step here is a *superset requirement*: every name must appear in
# the stamp (``pre_commit_cli_gate._validate_stamp``). The stamp may carry more
# (e.g. the conditional reviewers). Step names are the agent names verbatim —
# unlike the Phase 1 ``objective-verifier`` short form, the language-scoped
# ``py-`` prefix is part of the identity and kept 1:1 with the agent file.
#
# Pack-conditional enforcement: the ``py-*`` reviewers are profile-scoped,
# ``pack: python`` agents — they only load when the python pack is active. So
# ``pre_commit_cli_gate`` requires ``PY_PACK_VALIDATION_STEPS`` *only* when
# ``is_pack_active("python")``; the always-required floor is
# ``PY_CORE_VALIDATION_STEPS`` (the CLI checks + the core ``objective-verifier``).
# This keeps the gate honest: it never demands a reviewer step that the active
# configuration cannot produce. ``PY_VALIDATION_STEPS`` is the full set
# (core + pack) that ``/validate`` and the profile iterate.
#
# The narrow-now-grow-later approach keeps stamps honest (they cover exactly
# what exists) rather than carrying ``not-yet-implemented`` placeholder
# state through the schema. See project-canonical-step-phase-gap memory.
#
# ``PY_VALIDATION_STEPS`` is mirrored by ``config/profiles/python.json``'s
# ``validationSteps`` (the list ``/validate`` and ``run_cli_checks`` iterate);
# ``test__hook_shared`` asserts they stay in sync.

#: Code-gate steps required on *every* Python commit, pack-independent —
#: the CLI checks plus the core (``scope: core``) objective verifier.
PY_CORE_VALIDATION_STEPS: tuple[str, ...] = (
    "ruff-check",
    "ruff-format",
    "mypy-strict",
    "pytest",
    "objective-verifier",
)

#: The seven universally-applicable ``py-*`` reviewers — required by the code
#: gate only when the python pack is active (they are profile-scoped agents).
#: The two *conditional* reviewers (``py-migration-reviewer``,
#: ``py-api-reviewer``) are deliberately excluded even here: they scope to
#: migration / API files and no-op on any other diff, so ``/validate``
#: dispatches them on demand and stamps them only when relevant files stage.
PY_PACK_VALIDATION_STEPS: tuple[str, ...] = (
    "py-solid-dry-reviewer",
    "py-security-reviewer",
    "py-doc-checker",
    "py-arch-doc-reviewer",
    "py-code-simplifier",
    "py-tdd-process-reviewer",
    "py-logging-reviewer",
)

#: Full Python code validation gate — what ``/validate`` and the profile run.
PY_VALIDATION_STEPS: tuple[str, ...] = PY_CORE_VALIDATION_STEPS + PY_PACK_VALIDATION_STEPS

#: Frontend code validation gate — Phase 1 narrowed set (CLI-only).
FE_VALIDATION_STEPS: tuple[str, ...] = (
    "eslint",
    "tsc-strict",
    "vitest",
)

#: Agent infrastructure validation gate — Phase 1-2 set.
#:
#: Phase 2 added ``agent-arch-doc-reviewer`` (first tuple growth under the
#: narrow-now-grow-later plan) alongside the Phase 1 ``command-composition-reviewer``.
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

#: Staleness threshold for ``checkpoint_gate``. Subagent Bash is blocked when
#: the gap between ``now`` and ``session-checkpoint.state.json::last_write_ts``
#: exceeds this — the session has been doing Bash-only work (no Edit/Write
#: firing PostToolUse) long enough that session-state.md is certainly stale
#: and continuing without a forced checkpoint or ``/handoff`` risks losing
#: context on a crash. Sized at two ``CHECKPOINT_INTERVAL_SECONDS`` so one
#: missed interval is tolerated before the gate fires.
CHECKPOINT_STALENESS_THRESHOLD_SECONDS: int = 2 * CHECKPOINT_INTERVAL_SECONDS  # 30 minutes

#: Age threshold for ``post_temp_file_cleanup`` — a ``tmpclaude-*`` file
#: older than this in the project root is considered orphaned and removed
#: on the next PostToolUse Edit/Write. Five minutes is long enough that
#: in-flight CC tool calls cannot race against the sweeper but short enough
#: that crashed tool calls do not leave debris around for a session.
TMP_FILE_AGE_THRESHOLD_SECONDS: int = 300  # 5 minutes

#: How long a ``version_check`` result is reused before re-running the
#: comparison. 24 hours is the spec value: long enough that SessionStart
#: stays cheap on a busy day, short enough that a freshly-published
#: marketplace update is surfaced within one work cycle.
VERSION_CHECK_INTERVAL_SECONDS: int = 86_400  # 24 hours

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


def compute_hard_cut_pct(model_window: int) -> int:
    """Compute the framework's dynamic hard cut as a percentage of the window.

    For any positive ``model_window``, this returns ~62 — the
    constant ``int(CC_COMPACTION_FRACTION * HARD_CUT_FRACTION * 100)``.
    The function is exposed for hooks and agents that operate in raw
    window-pct space (where the cache is unavailable), so the
    threshold is derived from the same primitives as
    ``compute_hard_cut`` rather than rehardcoded.

    Args:
        model_window: The active model's context window in tokens.

    Returns:
        Hard cut as an integer percentage of the model window, or
        0 when ``model_window`` is non-positive.
    """
    if model_window <= 0:
        return 0
    return compute_hard_cut(model_window) * 100 // model_window


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
