"""Tests for hooks/worktree_lifecycle.py."""

from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from hooks import worktree_lifecycle

_LANGUAGE_PROFILE = ".language_profile.json"
_STAMP_FILES = (
    ".validation_stamp",
    ".frontend_validation_stamp",
    ".agent_validation_stamp",
    ".db_validation_stamp",
    ".api_validation_stamp",
)


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    project_dir: Path,
    payload: dict[str, Any] | None = None,
) -> None:
    body = json.dumps(payload) if payload is not None else ""
    monkeypatch.setattr(sys, "stdin", StringIO(body))
    monkeypatch.setattr(worktree_lifecycle, "get_project_dir", lambda: project_dir)


def _seed_profile(directory: Path, content: str = '{"name": "python"}') -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / _LANGUAGE_PROFILE
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# WorktreeCreate — seed profile from source
# ---------------------------------------------------------------------------


class TestWorktreeCreate:
    def test_existing_profile_copied(self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        source = tmp_dir / "main"
        worktree = tmp_dir / "feature"
        worktree.mkdir()
        _seed_profile(source, '{"name": "python", "priority": "P0"}')
        _patch(
            monkeypatch,
            tmp_dir,
            {
                "hook_event_name": "WorktreeCreate",
                "path": str(worktree),
                "source_path": str(source),
            },
        )

        assert worktree_lifecycle.main() == 0
        seeded = worktree / _LANGUAGE_PROFILE
        assert seeded.exists()
        assert "python" in seeded.read_text(encoding="utf-8")

    def test_missing_source_profile_silent_noop(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Source has no profile — new worktree shouldn't get one either.
        source = tmp_dir / "main"
        source.mkdir()
        worktree = tmp_dir / "feature"
        worktree.mkdir()
        _patch(
            monkeypatch,
            tmp_dir,
            {
                "hook_event_name": "WorktreeCreate",
                "path": str(worktree),
                "source_path": str(source),
            },
        )

        assert worktree_lifecycle.main() == 0
        assert not (worktree / _LANGUAGE_PROFILE).exists()
        assert capsys.readouterr().err == ""

    def test_source_falls_back_to_project_dir(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # When ``source_path`` is missing, the project dir provides the seed.
        _seed_profile(tmp_dir, '{"name": "javascript"}')
        worktree = tmp_dir / "wt"
        worktree.mkdir()
        _patch(
            monkeypatch,
            tmp_dir,
            {"hook_event_name": "WorktreeCreate", "path": str(worktree)},
        )

        worktree_lifecycle.main()
        assert (worktree / _LANGUAGE_PROFILE).exists()

    def test_create_creates_worktree_dir_if_missing(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # CC may emit WorktreeCreate before the dir is fully realised on
        # disk — the seed step must mkdir as needed.
        _seed_profile(tmp_dir, '{"name": "python"}')
        worktree = tmp_dir / "not-yet" / "wt"
        # Do NOT pre-create.
        _patch(
            monkeypatch,
            tmp_dir,
            {"hook_event_name": "WorktreeCreate", "path": str(worktree)},
        )

        worktree_lifecycle.main()
        assert (worktree / _LANGUAGE_PROFILE).exists()

    def test_create_without_path_is_noop(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _seed_profile(tmp_dir)
        _patch(monkeypatch, tmp_dir, {"hook_event_name": "WorktreeCreate"})

        assert worktree_lifecycle.main() == 0


# ---------------------------------------------------------------------------
# WorktreeRemove — clean up framework artifacts
# ---------------------------------------------------------------------------


class TestWorktreeRemove:
    def test_all_framework_files_removed(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        worktree = tmp_dir / "departing"
        worktree.mkdir()
        # Seed every framework file.
        for name in _STAMP_FILES:
            (worktree / name).write_text("stamp", encoding="utf-8")
        (worktree / _LANGUAGE_PROFILE).write_text("{}", encoding="utf-8")
        # And one user file that should NOT be touched.
        (worktree / "README.md").write_text("# user", encoding="utf-8")

        _patch(
            monkeypatch,
            tmp_dir,
            {"hook_event_name": "WorktreeRemove", "path": str(worktree)},
        )

        assert worktree_lifecycle.main() == 0
        for name in _STAMP_FILES:
            assert not (worktree / name).exists(), f"{name} should be removed"
        assert not (worktree / _LANGUAGE_PROFILE).exists()
        # User file untouched.
        assert (worktree / "README.md").exists()

    def test_remove_with_partial_state_is_silent(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Only one stamp present; missing files should not produce errors.
        worktree = tmp_dir / "departing"
        worktree.mkdir()
        (worktree / ".validation_stamp").write_text("x", encoding="utf-8")

        _patch(
            monkeypatch,
            tmp_dir,
            {"hook_event_name": "WorktreeRemove", "path": str(worktree)},
        )

        assert worktree_lifecycle.main() == 0
        assert capsys.readouterr().err == ""

    def test_remove_with_already_gone_dir_is_noop(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Dir does not exist (git already removed it).
        worktree = tmp_dir / "ghost"
        _patch(
            monkeypatch,
            tmp_dir,
            {"hook_event_name": "WorktreeRemove", "path": str(worktree)},
        )

        assert worktree_lifecycle.main() == 0

    def test_remove_unlink_failure_logged(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        worktree = tmp_dir / "departing"
        worktree.mkdir()
        # Make ``.validation_stamp`` a directory so unlink raises.
        (worktree / ".validation_stamp").mkdir()
        # Other framework files normal.
        (worktree / _LANGUAGE_PROFILE).write_text("{}", encoding="utf-8")

        _patch(
            monkeypatch,
            tmp_dir,
            {"hook_event_name": "WorktreeRemove", "path": str(worktree)},
        )

        assert worktree_lifecycle.main() == 0
        err = capsys.readouterr().err
        assert "could not remove" in err
        # Other files were still cleaned despite the error.
        assert not (worktree / _LANGUAGE_PROFILE).exists()


# ---------------------------------------------------------------------------
# Event dispatch — unknown / missing
# ---------------------------------------------------------------------------


class TestEventDispatch:
    def test_unknown_event_is_noop(self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        worktree = tmp_dir / "wt"
        worktree.mkdir()
        (worktree / _LANGUAGE_PROFILE).write_text("{}", encoding="utf-8")
        _patch(
            monkeypatch,
            tmp_dir,
            {"hook_event_name": "SomeOtherEvent", "path": str(worktree)},
        )

        worktree_lifecycle.main()
        # Cleanup did not run.
        assert (worktree / _LANGUAGE_PROFILE).exists()

    def test_missing_event_is_noop(self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch(monkeypatch, tmp_dir, {"path": str(tmp_dir / "wt")})

        assert worktree_lifecycle.main() == 0

    @pytest.mark.parametrize("key", ["hook_event_name", "event", "event_name"])
    def test_event_recognised_under_each_key(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch, key: str
    ) -> None:
        worktree = tmp_dir / "wt"
        worktree.mkdir()
        (worktree / _LANGUAGE_PROFILE).write_text("{}", encoding="utf-8")
        _patch(
            monkeypatch,
            tmp_dir,
            {key: "WorktreeRemove", "path": str(worktree)},
        )

        worktree_lifecycle.main()
        assert not (worktree / _LANGUAGE_PROFILE).exists()


class TestResilience:
    def test_empty_stdin(self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "stdin", StringIO(""))
        monkeypatch.setattr(worktree_lifecycle, "get_project_dir", lambda: tmp_dir)
        assert worktree_lifecycle.main() == 0
