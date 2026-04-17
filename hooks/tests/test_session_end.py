"""Tests for hooks/session_end.py."""

from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path

import pytest

from hooks import session_end


def _patch_io(
    monkeypatch: pytest.MonkeyPatch,
    stdin_payload: dict[str, object],
    project_dir: Path,
) -> None:
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(stdin_payload)))
    monkeypatch.setattr(session_end, "get_project_dir", lambda: project_dir)


class TestHappyPath:
    def test_writes_state_file(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        memory_dir = tmp_dir / "memory"
        memory_dir.mkdir()
        transcript = tmp_dir / "transcript.jsonl"
        transcript.write_text(
            '{"type":"human","content":"do the thing"}\n'
            '{"type":"tool_use","tool_name":"TodoWrite","tool_input":{"todos":[{"content":"t","status":"pending"}]}}\n',
            encoding="utf-8",
        )

        captured: dict[str, object] = {}

        def fake_write(
            data: dict[str, object],
            project_dir: Path,
            *,
            header_note: str = "",
        ) -> Path:
            captured["data"] = data
            captured["project_dir"] = project_dir
            captured["header_note"] = header_note
            return memory_dir / "session-state.md"

        monkeypatch.setattr(session_end, "write_session_state", fake_write)

        _patch_io(
            monkeypatch,
            {"transcript_path": str(transcript), "reason": "user-ended"},
            tmp_dir,
        )

        rc = session_end.main()

        assert rc == 0
        assert captured["header_note"] == "Session ended: user-ended"
        assert captured["project_dir"] == tmp_dir
        data = captured["data"]
        assert isinstance(data, dict)
        assert data.get("last_user_prompt") == "do the thing"
        assert data.get("todos") == [{"content": "t", "status": "pending"}]


class TestMissingInputs:
    def test_no_transcript_still_writes_with_empty_extract(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        captured: dict[str, object] = {}

        def fake_write(
            data: dict[str, object],
            project_dir: Path,
            *,
            header_note: str = "",
        ) -> Path:
            captured["data"] = data
            captured["header_note"] = header_note
            return tmp_dir / "session-state.md"

        monkeypatch.setattr(session_end, "write_session_state", fake_write)
        _patch_io(monkeypatch, {}, tmp_dir)

        rc = session_end.main()

        assert rc == 0
        assert captured["data"] == {}
        assert captured["header_note"] == "Session ended"


class TestWriteFailure:
    def test_oserror_is_logged_not_raised(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        def fake_write(*_args: object, **_kwargs: object) -> Path:
            raise OSError("disk full")

        monkeypatch.setattr(session_end, "write_session_state", fake_write)
        _patch_io(monkeypatch, {"reason": "crash"}, tmp_dir)

        rc = session_end.main()

        captured = capsys.readouterr()
        assert rc == 0
        assert "could not write state" in captured.err
