"""Tests for hooks/session_start_framework_memory.py."""

from __future__ import annotations

import sys
from io import StringIO
from pathlib import Path

import pytest

from hooks import session_start_framework_memory


def _patch_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdin", StringIO("{}"))


class TestHappyPath:
    def test_creates_full_tree(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_dir))
        monkeypatch.delenv("CLAUDE_INCIDENTS_DIR", raising=False)
        monkeypatch.delenv("CLAUDE_TELEMETRY_DIR", raising=False)
        _patch_stdin(monkeypatch)

        rc = session_start_framework_memory.main()
        captured = capsys.readouterr()

        assert rc == 0
        assert captured.err == ""

        framework = (tmp_dir / "framework-memory").resolve()
        assert framework.is_dir()
        for sub in ("incidents", "telemetry", "graph-history", "principles", "retrospectives"):
            assert (framework / sub).is_dir(), f"{sub} not created"

    def test_writes_gitignore_with_exclusion(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_dir))
        monkeypatch.delenv("CLAUDE_INCIDENTS_DIR", raising=False)
        monkeypatch.delenv("CLAUDE_TELEMETRY_DIR", raising=False)
        _patch_stdin(monkeypatch)

        rc = session_start_framework_memory.main()

        assert rc == 0
        gitignore = (tmp_dir / "framework-memory" / ".gitignore").resolve()
        assert gitignore.is_file()
        content = gitignore.read_text(encoding="utf-8")
        assert "*" in content
        assert "!.gitignore" in content

    def test_idempotent(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Re-running on an existing tree must not error or churn the file."""
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_dir))
        monkeypatch.delenv("CLAUDE_INCIDENTS_DIR", raising=False)
        monkeypatch.delenv("CLAUDE_TELEMETRY_DIR", raising=False)
        _patch_stdin(monkeypatch)

        rc1 = session_start_framework_memory.main()
        gitignore = (tmp_dir / "framework-memory" / ".gitignore").resolve()
        first_mtime = gitignore.stat().st_mtime_ns

        # Reset stdin between invocations.
        _patch_stdin(monkeypatch)
        rc2 = session_start_framework_memory.main()
        captured = capsys.readouterr()

        assert rc1 == 0
        assert rc2 == 0
        assert captured.err == ""
        # Existing .gitignore is untouched (mtime unchanged).
        assert gitignore.stat().st_mtime_ns == first_mtime


class TestFailureModes:
    def test_unwritable_root_warns_but_returns_zero(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Point at a path whose parent is a regular file — mkdir cannot create.
        blocker = tmp_dir / "blocker"
        blocker.write_text("not a dir", encoding="utf-8")
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(blocker / "child"))
        monkeypatch.delenv("CLAUDE_INCIDENTS_DIR", raising=False)
        monkeypatch.delenv("CLAUDE_TELEMETRY_DIR", raising=False)
        _patch_stdin(monkeypatch)

        rc = session_start_framework_memory.main()
        captured = capsys.readouterr()

        assert rc == 0  # Advisory — never blocks.
        assert "could not initialise tree" in captured.err

    def test_existing_gitignore_not_overwritten(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_dir))
        monkeypatch.delenv("CLAUDE_INCIDENTS_DIR", raising=False)
        monkeypatch.delenv("CLAUDE_TELEMETRY_DIR", raising=False)
        _patch_stdin(monkeypatch)

        # Pre-populate a customised .gitignore — the hook must not overwrite it.
        framework = tmp_dir / "framework-memory"
        framework.mkdir(parents=True)
        custom = framework / ".gitignore"
        custom.write_text("# customised by user\nfoo/\n", encoding="utf-8")

        rc = session_start_framework_memory.main()

        assert rc == 0
        assert custom.read_text(encoding="utf-8") == "# customised by user\nfoo/\n"
