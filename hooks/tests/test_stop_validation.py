"""Tests for hooks/stop_validation.py."""

from __future__ import annotations

import json
import subprocess
import sys
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from hooks import stop_validation


def _patch_stdin(monkeypatch: pytest.MonkeyPatch, payload: dict[str, Any]) -> None:
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(payload)))


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True)


# ---------------------------------------------------------------------------
# Fail-open: clean tree, no repo, git broken
# ---------------------------------------------------------------------------


class TestFailOpen:
    def test_clean_tree_passes(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(stop_validation, "get_project_dir", lambda: tmp_git_repo)
        _patch_stdin(monkeypatch, {})

        assert stop_validation.main() == 0

    def test_not_a_git_repo_passes(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # ``tmp_dir`` is not a repo — ``git status`` exits non-zero.
        monkeypatch.setattr(stop_validation, "get_project_dir", lambda: tmp_dir)
        _patch_stdin(monkeypatch, {})

        assert stop_validation.main() == 0

    def test_git_missing_passes(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Simulate ``git`` not on PATH — subprocess.run raises FileNotFoundError.
        def raise_missing(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
            raise FileNotFoundError("git")

        monkeypatch.setattr(stop_validation, "get_project_dir", lambda: tmp_dir)
        monkeypatch.setattr(subprocess, "run", raise_missing)
        _patch_stdin(monkeypatch, {})

        assert stop_validation.main() == 0

    def test_git_timeout_passes(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def raise_timeout(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
            raise subprocess.TimeoutExpired(cmd="git status", timeout=5.0)

        monkeypatch.setattr(stop_validation, "get_project_dir", lambda: tmp_dir)
        monkeypatch.setattr(subprocess, "run", raise_timeout)
        _patch_stdin(monkeypatch, {})

        assert stop_validation.main() == 0

    def test_empty_stdin_passes_on_clean(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(sys, "stdin", StringIO(""))
        monkeypatch.setattr(stop_validation, "get_project_dir", lambda: tmp_git_repo)

        assert stop_validation.main() == 0


# ---------------------------------------------------------------------------
# Fail-closed: dirty tree
# ---------------------------------------------------------------------------


class TestBlocksDirtyTree:
    def test_modified_tracked_file_blocks(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        tracked = tmp_git_repo / "README.md"
        tracked.write_text("hello\n", encoding="utf-8")
        _git(tmp_git_repo, "add", "README.md")
        _git(tmp_git_repo, "commit", "-m", "seed")
        tracked.write_text("world\n", encoding="utf-8")

        monkeypatch.setattr(stop_validation, "get_project_dir", lambda: tmp_git_repo)
        _patch_stdin(monkeypatch, {})

        rc = stop_validation.main()
        err = capsys.readouterr().err

        assert rc == 2
        assert "refusing Stop" in err
        assert "README.md" in err
        assert "[WIP]" in err

    def test_untracked_file_blocks(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        (tmp_git_repo / "new.py").write_text("x = 1\n", encoding="utf-8")

        monkeypatch.setattr(stop_validation, "get_project_dir", lambda: tmp_git_repo)
        _patch_stdin(monkeypatch, {})

        rc = stop_validation.main()
        err = capsys.readouterr().err

        assert rc == 2
        assert "new.py" in err

    def test_staged_only_file_blocks(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_git_repo / "staged.py").write_text("x = 1\n", encoding="utf-8")
        _git(tmp_git_repo, "add", "staged.py")

        monkeypatch.setattr(stop_validation, "get_project_dir", lambda: tmp_git_repo)
        _patch_stdin(monkeypatch, {})

        assert stop_validation.main() == 2

    def test_message_truncates_large_dirty_listing(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        for i in range(15):
            (tmp_git_repo / f"f{i}.txt").write_text("x", encoding="utf-8")

        monkeypatch.setattr(stop_validation, "get_project_dir", lambda: tmp_git_repo)
        _patch_stdin(monkeypatch, {})

        stop_validation.main()
        err = capsys.readouterr().err
        assert "and 5 more" in err
        assert "15 uncommitted change(s)" in err
