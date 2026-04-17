"""Tests for hooks/create_feature_branch.py."""

from __future__ import annotations

import json
import subprocess
import sys
from io import StringIO
from pathlib import Path

import pytest

from hooks import create_feature_branch


def _patch_io(
    monkeypatch: pytest.MonkeyPatch,
    stdin_payload: dict[str, object],
    project_dir: Path,
) -> None:
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(stdin_payload)))
    monkeypatch.setattr(create_feature_branch, "get_project_dir", lambda: project_dir)


class TestSlugify:
    def test_basic_slug(self) -> None:
        assert create_feature_branch._slugify("Fix the login bug") == "fix-the-login-bug"

    def test_collapses_non_alnum_runs(self) -> None:
        assert create_feature_branch._slugify("Fix!!! the <login> bug???") == "fix-the-login-bug"

    def test_strips_edges(self) -> None:
        assert create_feature_branch._slugify("---hello---") == "hello"

    def test_empty_yields_untitled(self) -> None:
        assert create_feature_branch._slugify("   ") == "untitled"

    def test_truncates_to_max_len(self) -> None:
        text = "a" * 80
        result = create_feature_branch._slugify(text, max_len=50)
        assert len(result) == 50


class TestNewBranchName:
    def test_shape(self) -> None:
        name = create_feature_branch._new_branch_name("test prompt")
        assert name.startswith("feat/")
        assert name.endswith("-test-prompt")
        # feat/YYYYMMDD-HHMMSS-slug
        parts = name.removeprefix("feat/").split("-", 2)
        assert len(parts) == 3
        assert len(parts[0]) == 8  # YYYYMMDD
        assert len(parts[1]) == 6  # HHMMSS


class TestOnProtectedBranch:
    def test_cuts_branch_and_writes_objective(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        subprocess.run(
            ["git", "checkout", "-B", "master"],
            cwd=str(tmp_git_repo),
            check=True,
            capture_output=True,
        )

        (tmp_git_repo / ".claude").mkdir()
        _patch_io(monkeypatch, {"prompt": "Add the new widget"}, tmp_git_repo)

        rc = create_feature_branch.main()
        captured = capsys.readouterr()

        assert rc == 0
        new_branch = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=str(tmp_git_repo),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert new_branch.startswith("feat/")
        assert new_branch.endswith("-add-the-new-widget")
        assert "cut feat/" in captured.err

        objective = (tmp_git_repo / ".claude" / "current-objective.md").read_text(encoding="utf-8")
        assert objective == "Add the new widget"


class TestOnFeatureBranch:
    def test_no_branch_cut_writes_objective(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        subprocess.run(
            ["git", "checkout", "-B", "feat/existing-work"],
            cwd=str(tmp_git_repo),
            check=True,
            capture_output=True,
        )
        (tmp_git_repo / ".claude").mkdir()
        _patch_io(monkeypatch, {"prompt": "Continue the work"}, tmp_git_repo)

        rc = create_feature_branch.main()

        assert rc == 0
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=str(tmp_git_repo),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert branch == "feat/existing-work"
        objective = (tmp_git_repo / ".claude" / "current-objective.md").read_text(encoding="utf-8")
        assert objective == "Continue the work"


class TestEmptyPrompt:
    def test_noop_when_prompt_empty(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        subprocess.run(
            ["git", "checkout", "-B", "master"],
            cwd=str(tmp_git_repo),
            check=True,
            capture_output=True,
        )
        _patch_io(monkeypatch, {"prompt": "   "}, tmp_git_repo)

        rc = create_feature_branch.main()

        assert rc == 0
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=str(tmp_git_repo),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert branch == "master"
        assert not (tmp_git_repo / ".claude" / "current-objective.md").exists()


class TestGitFailureDoesNotBlock:
    def test_git_error_still_exits_zero(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # No git repo — get_current_branch returns "" so no checkout attempt.
        # But simulate a protected-branch scenario with a failing _run_git.
        monkeypatch.setattr(create_feature_branch, "get_current_branch", lambda _d: "master")
        monkeypatch.setattr(create_feature_branch, "_run_git", lambda _args, _cwd: False)
        (tmp_dir / ".claude").mkdir()

        _patch_io(monkeypatch, {"prompt": "test"}, tmp_dir)

        rc = create_feature_branch.main()
        captured = capsys.readouterr()

        assert rc == 0
        # Objective still written despite branch-cut failure
        objective = (tmp_dir / ".claude" / "current-objective.md").read_text(encoding="utf-8")
        assert objective == "test"
        # No "cut" success message (since _run_git returned False)
        assert "cut feat/" not in captured.err
