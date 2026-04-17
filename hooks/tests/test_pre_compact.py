"""Tests for hooks/pre_compact.py."""

from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path

import pytest

from hooks import pre_compact


def _patch_io(
    monkeypatch: pytest.MonkeyPatch,
    stdin_payload: dict[str, object],
    project_dir: Path,
) -> None:
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(stdin_payload)))
    monkeypatch.setattr(pre_compact, "get_project_dir", lambda: project_dir)


class TestHappyPath:
    def test_writes_snapshot_and_emits_system_message(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        transcript = tmp_dir / "transcript.jsonl"
        transcript.write_text('{"type":"human","content":"before compaction"}\n', encoding="utf-8")

        captured_write: dict[str, object] = {}

        def fake_write(
            data: dict[str, object],
            project_dir: Path,
            *,
            header_note: str = "",
        ) -> Path:
            captured_write["data"] = data
            captured_write["header_note"] = header_note
            return tmp_dir / "session-state.md"

        monkeypatch.setattr(pre_compact, "write_session_state", fake_write)
        _patch_io(monkeypatch, {"transcript_path": str(transcript)}, tmp_dir)

        rc = pre_compact.main()

        captured = capsys.readouterr()
        assert rc == 0
        assert captured_write["header_note"] == "Pre-compaction snapshot"

        data = captured_write["data"]
        assert isinstance(data, dict)
        assert data.get("last_user_prompt") == "before compaction"

        out = json.loads(captured.out)
        assert "systemMessage" in out
        assert "session-state.md" in out["systemMessage"]


class TestWriteFailure:
    def test_oserror_swallowed_no_system_message_on_failure(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        def fake_write(*_args: object, **_kwargs: object) -> Path:
            raise OSError("io fail")

        monkeypatch.setattr(pre_compact, "write_session_state", fake_write)
        _patch_io(monkeypatch, {}, tmp_dir)

        rc = pre_compact.main()
        captured = capsys.readouterr()
        assert rc == 0
        assert "could not write state" in captured.err
        assert captured.out == ""
