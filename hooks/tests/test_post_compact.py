"""Tests for hooks/post_compact.py."""

from __future__ import annotations

import sys
from io import StringIO
from pathlib import Path

import pytest

from hooks import post_compact


def _patch_io(
    monkeypatch: pytest.MonkeyPatch,
    project_dir: Path,
    memory_dir: Path,
) -> None:
    monkeypatch.setattr(sys, "stdin", StringIO("{}"))
    monkeypatch.setattr(post_compact, "get_project_dir", lambda: project_dir)
    monkeypatch.setattr(post_compact, "get_memory_dir", lambda _project_dir: memory_dir)


class TestStateFilePresent:
    def test_exits_zero_and_deletes_cache(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        memory_dir = tmp_dir / "memory"
        memory_dir.mkdir()
        (memory_dir / "session-state.md").write_text("# snap\n", encoding="utf-8")

        claude_dir = tmp_dir / ".claude"
        claude_dir.mkdir()
        cache = claude_dir / ".context_pct"
        cache.write_text("80", encoding="utf-8")

        _patch_io(monkeypatch, tmp_dir, memory_dir)

        rc = post_compact.main()
        captured = capsys.readouterr()

        assert rc == 0
        assert captured.err == ""
        assert not cache.exists()


class TestStateFileMissing:
    def test_logs_warning_but_exits_zero(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        memory_dir = tmp_dir / "memory"
        memory_dir.mkdir()
        _patch_io(monkeypatch, tmp_dir, memory_dir)

        rc = post_compact.main()
        captured = capsys.readouterr()

        assert rc == 0
        assert "no session-state.md found" in captured.err


class TestCacheAbsent:
    def test_noop_when_cache_missing(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        memory_dir = tmp_dir / "memory"
        memory_dir.mkdir()
        (memory_dir / "session-state.md").write_text("# snap\n", encoding="utf-8")
        _patch_io(monkeypatch, tmp_dir, memory_dir)

        rc = post_compact.main()
        captured = capsys.readouterr()
        assert rc == 0
        assert captured.err == ""


class TestCacheDeleteFailure:
    def test_oserror_on_unlink_is_logged(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        memory_dir = tmp_dir / "memory"
        memory_dir.mkdir()
        (memory_dir / "session-state.md").write_text("# snap\n", encoding="utf-8")

        claude_dir = tmp_dir / ".claude"
        claude_dir.mkdir()
        cache = claude_dir / ".context_pct"
        cache.write_text("80", encoding="utf-8")

        _patch_io(monkeypatch, tmp_dir, memory_dir)

        def boom(_self: Path) -> None:
            raise OSError("locked")

        monkeypatch.setattr(Path, "unlink", boom)

        rc = post_compact.main()
        captured = capsys.readouterr()
        assert rc == 0
        assert "could not delete" in captured.err
