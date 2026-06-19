"""Tests for hooks/_hook_shared.py."""

from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path

import pytest

from hooks._hook_shared import (
    AGENT_VALIDATION_STEPS,
    CC_COMPACTION_FRACTION,
    CRITICAL_CONTEXT_PCT,
    FE_VALIDATION_STEPS,
    HARD_CUT_FRACTION,
    PROTECTED_BRANCHES,
    PY_CORE_VALIDATION_STEPS,
    PY_PACK_VALIDATION_STEPS,
    PY_VALIDATION_STEPS,
    STAMP_TTL,
    WARN_CONTEXT_PCT,
    compute_hard_cut,
    compute_hard_cut_pct,
    get_current_branch,
    get_project_dir,
    is_pack_active,
    read_cached_pct,
    read_hook_input,
)

# ---------------------------------------------------------------------------
# read_hook_input
# ---------------------------------------------------------------------------


class TestReadHookInput:
    def test_valid_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        payload = {"tool_name": "Edit", "tool_input": {"file_path": "/tmp/x.py"}}
        monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(payload)))
        result = read_hook_input()
        assert result == payload

    def test_empty_stdin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "stdin", StringIO(""))
        result = read_hook_input()
        assert result == {}

    def test_malformed_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "stdin", StringIO("{not valid json"))
        result = read_hook_input()
        assert result == {}

    def test_non_dict_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "stdin", StringIO('"just a string"'))
        result = read_hook_input()
        assert result == {}

    def test_whitespace_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "stdin", StringIO("   \n\t  "))
        result = read_hook_input()
        assert result == {}

    def test_array_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "stdin", StringIO("[1, 2, 3]"))
        result = read_hook_input()
        assert result == {}


# ---------------------------------------------------------------------------
# get_current_branch
# ---------------------------------------------------------------------------


class TestGetCurrentBranch:
    def test_reads_branch_from_git_head(self, tmp_git_repo: Path) -> None:
        branch = get_current_branch(tmp_git_repo)
        # Default branch after git init — could be main or master depending on config
        assert branch in ("main", "master")

    def test_feature_branch(self, tmp_git_repo: Path) -> None:
        import subprocess

        subprocess.run(
            ["git", "checkout", "-b", "feat/test-branch"],
            cwd=str(tmp_git_repo),
            check=True,
            capture_output=True,
        )
        branch = get_current_branch(tmp_git_repo)
        assert branch == "feat/test-branch"

    def test_detached_head(self, tmp_git_repo: Path) -> None:
        import subprocess

        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(tmp_git_repo),
            check=True,
            capture_output=True,
            text=True,
        )
        commit_hash = result.stdout.strip()
        subprocess.run(
            ["git", "checkout", commit_hash],
            cwd=str(tmp_git_repo),
            check=True,
            capture_output=True,
        )
        branch = get_current_branch(tmp_git_repo)
        assert branch == commit_hash

    def test_no_git_dir(self, tmp_dir: Path) -> None:
        branch = get_current_branch(tmp_dir)
        assert branch == ""


# ---------------------------------------------------------------------------
# get_project_dir
# ---------------------------------------------------------------------------


class TestGetProjectDir:
    def test_from_env_var(self, monkeypatch: pytest.MonkeyPatch, tmp_dir: Path) -> None:
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_dir))
        result = get_project_dir()
        assert result == tmp_dir.resolve()

    def test_fallback_to_file_location(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
        result = get_project_dir()
        # Should be the repo root (parent of hooks/)
        assert result.is_dir()
        assert (result / "hooks").is_dir()


# ---------------------------------------------------------------------------
# read_cached_pct
# ---------------------------------------------------------------------------


class TestReadCachedPct:
    def test_reads_valid_cache(self, tmp_dir: Path) -> None:
        claude_dir = tmp_dir / ".claude"
        claude_dir.mkdir()
        (claude_dir / ".context_pct").write_text("72", encoding="utf-8")
        result = read_cached_pct(tmp_dir)
        assert result == 72

    def test_missing_file(self, tmp_dir: Path) -> None:
        result = read_cached_pct(tmp_dir)
        assert result is None

    def test_invalid_content(self, tmp_dir: Path) -> None:
        claude_dir = tmp_dir / ".claude"
        claude_dir.mkdir()
        (claude_dir / ".context_pct").write_text("not a number", encoding="utf-8")
        result = read_cached_pct(tmp_dir)
        assert result is None


# ---------------------------------------------------------------------------
# compute_hard_cut
# ---------------------------------------------------------------------------


class TestComputeHardCut:
    def test_200k_window(self) -> None:
        """Opus/Sonnet 200K → hard cut at ~125K."""
        cut = compute_hard_cut(200_000)
        assert cut == int(200_000 * CC_COMPACTION_FRACTION * HARD_CUT_FRACTION)
        # Approximately 125,250
        assert 125_000 <= cut <= 126_000

    def test_1m_window(self) -> None:
        """Opus 1M → hard cut at ~625K."""
        cut = compute_hard_cut(1_000_000)
        assert cut == int(1_000_000 * CC_COMPACTION_FRACTION * HARD_CUT_FRACTION)
        assert 625_000 <= cut <= 627_000

    def test_zero_window(self) -> None:
        assert compute_hard_cut(0) == 0

    def test_returns_int(self) -> None:
        result = compute_hard_cut(200_000)
        assert isinstance(result, int)


# ---------------------------------------------------------------------------
# compute_hard_cut_pct
# ---------------------------------------------------------------------------


class TestComputeHardCutPct:
    def test_200k_window(self) -> None:
        """Hard cut as percentage of any normal window is ~62."""
        assert compute_hard_cut_pct(200_000) == 62

    def test_1m_window(self) -> None:
        assert compute_hard_cut_pct(1_000_000) == 62

    def test_zero_window(self) -> None:
        assert compute_hard_cut_pct(0) == 0

    def test_negative_window(self) -> None:
        assert compute_hard_cut_pct(-1) == 0

    def test_returns_int(self) -> None:
        assert isinstance(compute_hard_cut_pct(200_000), int)

    def test_consistent_with_compute_hard_cut(self) -> None:
        """compute_hard_cut_pct must agree with compute_hard_cut for any window."""
        for window in (100_000, 200_000, 500_000, 1_000_000):
            expected_pct = compute_hard_cut(window) * 100 // window
            assert compute_hard_cut_pct(window) == expected_pct


# ---------------------------------------------------------------------------
# is_pack_active
# ---------------------------------------------------------------------------


class TestIsPackActive:
    def test_core_always_active(self, tmp_dir: Path) -> None:
        assert is_pack_active("core", tmp_dir) is True

    def test_active_pack(self, tmp_dir: Path) -> None:
        config_dir = tmp_dir / "config"
        config_dir.mkdir()
        config = {"activePacks": ["python", "frontend"]}
        (config_dir / "user-config.json").write_text(json.dumps(config), encoding="utf-8")
        assert is_pack_active("python", tmp_dir) is True
        assert is_pack_active("frontend", tmp_dir) is True

    def test_inactive_pack(self, tmp_dir: Path) -> None:
        config_dir = tmp_dir / "config"
        config_dir.mkdir()
        config = {"activePacks": ["python"]}
        (config_dir / "user-config.json").write_text(json.dumps(config), encoding="utf-8")
        assert is_pack_active("frontend", tmp_dir) is False

    def test_no_config_file(self, tmp_dir: Path) -> None:
        assert is_pack_active("python", tmp_dir) is False

    def test_malformed_config(self, tmp_dir: Path) -> None:
        config_dir = tmp_dir / "config"
        config_dir.mkdir()
        (config_dir / "user-config.json").write_text("{bad json", encoding="utf-8")
        assert is_pack_active("python", tmp_dir) is False

    def test_active_packs_not_list(self, tmp_dir: Path) -> None:
        config_dir = tmp_dir / "config"
        config_dir.mkdir()
        config = {"activePacks": "python"}
        (config_dir / "user-config.json").write_text(json.dumps(config), encoding="utf-8")
        assert is_pack_active("python", tmp_dir) is False


# ---------------------------------------------------------------------------
# Constants sanity checks
# ---------------------------------------------------------------------------


class TestConstants:
    def test_thresholds_ordered(self) -> None:
        assert WARN_CONTEXT_PCT < CRITICAL_CONTEXT_PCT

    def test_validation_steps_not_empty(self) -> None:
        assert len(PY_VALIDATION_STEPS) > 0
        assert len(FE_VALIDATION_STEPS) > 0
        assert len(AGENT_VALIDATION_STEPS) > 0

    def test_validation_steps_unique(self) -> None:
        assert len(PY_VALIDATION_STEPS) == len(set(PY_VALIDATION_STEPS))
        assert len(FE_VALIDATION_STEPS) == len(set(FE_VALIDATION_STEPS))
        assert len(AGENT_VALIDATION_STEPS) == len(set(AGENT_VALIDATION_STEPS))

    def test_stamp_ttl_positive(self) -> None:
        assert STAMP_TTL > 0

    def test_protected_branches_include_master(self) -> None:
        assert "master" in PROTECTED_BRANCHES
        assert "main" in PROTECTED_BRANCHES


# ---------------------------------------------------------------------------
# Python validation-step wiring (Phase 6)
# ---------------------------------------------------------------------------

#: The seven universally-applicable py-* reviewers required on every code stamp.
_UNIVERSAL_PY_REVIEWERS: frozenset[str] = frozenset(
    {
        "py-solid-dry-reviewer",
        "py-security-reviewer",
        "py-doc-checker",
        "py-arch-doc-reviewer",
        "py-code-simplifier",
        "py-tdd-process-reviewer",
        "py-logging-reviewer",
    }
)

#: The conditional reviewers that must NOT be in the required tuple — they
#: scope to migration / API files and are dispatched on demand by /validate.
_CONDITIONAL_PY_REVIEWERS: frozenset[str] = frozenset({"py-migration-reviewer", "py-api-reviewer"})


def _repo_root() -> Path:
    # hooks/tests/test__hook_shared.py -> repo root is parents[2].
    return Path(__file__).resolve().parents[2]


class TestPyValidationStepWiring:
    def test_universal_reviewers_are_the_pack_steps(self) -> None:
        assert set(PY_PACK_VALIDATION_STEPS) == _UNIVERSAL_PY_REVIEWERS

    def test_universal_reviewers_are_canonical(self) -> None:
        assert _UNIVERSAL_PY_REVIEWERS.issubset(PY_VALIDATION_STEPS)

    def test_conditional_reviewers_are_not_canonical(self) -> None:
        # Requiring these in every stamp would force wasted reviews on diffs
        # with no migrations / endpoints. They are stamped on demand instead.
        assert _CONDITIONAL_PY_REVIEWERS.isdisjoint(PY_VALIDATION_STEPS)

    def test_full_tuple_is_core_plus_pack(self) -> None:
        assert PY_VALIDATION_STEPS == PY_CORE_VALIDATION_STEPS + PY_PACK_VALIDATION_STEPS

    def test_core_and_pack_are_disjoint(self) -> None:
        assert set(PY_CORE_VALIDATION_STEPS).isdisjoint(PY_PACK_VALIDATION_STEPS)

    def test_cli_and_objective_steps_are_the_core_floor(self) -> None:
        # The pack-independent floor the gate always requires.
        assert set(PY_CORE_VALIDATION_STEPS) == {
            "ruff-check",
            "ruff-format",
            "mypy-strict",
            "pytest",
            "objective-verifier",
        }

    def test_tuple_matches_python_profile(self) -> None:
        """The profile's validationSteps must mirror the canonical tuple.

        run_cli_checks and /validate iterate the profile list; the gate's
        superset check uses the tuple. Drift between them is the bug that
        once left py-logging-reviewer out of the profile.
        """
        profile = json.loads(
            (_repo_root() / "config" / "profiles" / "python.json").read_text(encoding="utf-8")
        )
        assert set(profile["validationSteps"]) == set(PY_VALIDATION_STEPS)
