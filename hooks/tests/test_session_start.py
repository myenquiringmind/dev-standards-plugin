"""Tests for hooks/session_start.py."""

from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path

import pytest

from hooks import session_start


def _patch_io(
    monkeypatch: pytest.MonkeyPatch, stdin_payload: dict[str, object], memory_dir: Path
) -> None:
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(stdin_payload)))
    monkeypatch.setattr(session_start, "get_project_dir", lambda: memory_dir.parent)
    monkeypatch.setattr(session_start, "get_memory_dir", lambda _project_dir: memory_dir)


class TestNoStateFile:
    def test_exits_zero_and_emits_nothing(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        memory_dir = tmp_dir / "memory"
        memory_dir.mkdir()
        _patch_io(monkeypatch, {"source": "startup"}, memory_dir)

        rc = session_start.main()

        captured = capsys.readouterr()
        assert rc == 0
        assert captured.out == ""
        assert captured.err == ""


class TestStateFilePresent:
    def test_injects_context_and_archives(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        memory_dir = tmp_dir / "memory"
        memory_dir.mkdir()
        state = memory_dir / "session-state.md"
        state.write_text(
            "# Session State Snapshot\n\n## Task Progress\n- [~] finish the widget\n- [ ] ship it\n- [x] done thing\n",
            encoding="utf-8",
        )

        _patch_io(monkeypatch, {"source": "clear"}, memory_dir)

        rc = session_start.main()

        captured = capsys.readouterr()
        assert rc == 0

        payload = json.loads(captured.out)
        assert "additionalContext" in payload
        ctx = payload["additionalContext"]
        assert "Session was cleared" in ctx
        assert "Restore Active Todos" in ctx
        assert "finish the widget" in ctx
        assert "ship it" in ctx
        restore_block = ctx.split("## Restore Active Todos")[-1]
        assert "done thing" not in restore_block  # completed todos filtered from restore block
        assert "in_progress" in restore_block
        assert "pending" in restore_block

        assert not state.exists()
        assert (memory_dir / "session-state.md.injected").exists()

    def test_default_source_is_startup(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        memory_dir = tmp_dir / "memory"
        memory_dir.mkdir()
        (memory_dir / "session-state.md").write_text("# snapshot\n", encoding="utf-8")
        _patch_io(monkeypatch, {}, memory_dir)

        rc = session_start.main()
        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert rc == 0
        assert "Resuming work from the prior session" in payload["additionalContext"]

    def test_no_active_todos_skips_restore_block(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        memory_dir = tmp_dir / "memory"
        memory_dir.mkdir()
        state = memory_dir / "session-state.md"
        state.write_text(
            "# snap\n\n## Task Progress\n- [x] all done\n",
            encoding="utf-8",
        )
        _patch_io(monkeypatch, {"source": "resume"}, memory_dir)

        rc = session_start.main()
        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert rc == 0
        assert "Restore Active Todos" not in payload["additionalContext"]


class TestArchiveFailure:
    def test_archive_failure_does_not_block(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        memory_dir = tmp_dir / "memory"
        memory_dir.mkdir()
        (memory_dir / "session-state.md").write_text("# snap\n", encoding="utf-8")

        def boom(_mem_dir: Path | str) -> None:
            raise OSError("permission denied")

        _patch_io(monkeypatch, {"source": "startup"}, memory_dir)
        monkeypatch.setattr(session_start, "archive_state_to_injected", boom)

        rc = session_start.main()
        captured = capsys.readouterr()
        assert rc == 0
        assert "archive failed" in captured.err
        payload = json.loads(captured.out)
        assert "additionalContext" in payload
