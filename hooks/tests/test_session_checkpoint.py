"""Tests for hooks/session_checkpoint.py."""

from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path

import pytest

from hooks import session_checkpoint
from hooks._hook_shared import (
    CHECKPOINT_INTERVAL_EVENTS,
    CHECKPOINT_INTERVAL_SECONDS,
)

_STATE_FILENAME = "session-checkpoint.state.json"


def _patch_io(
    monkeypatch: pytest.MonkeyPatch,
    stdin_payload: dict[str, object],
    project_dir: Path,
    *,
    branch: str = "feat/example",
    fixed_time: float = 1_000_000.0,
) -> None:
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(stdin_payload)))
    monkeypatch.setattr(session_checkpoint, "get_project_dir", lambda: project_dir)
    monkeypatch.setattr(session_checkpoint, "get_memory_dir", lambda _d: project_dir)
    monkeypatch.setattr(session_checkpoint, "get_current_branch", lambda _d: branch)
    monkeypatch.setattr("time.time", lambda: fixed_time)


def _read_state(project_dir: Path) -> dict[str, object]:
    text = (project_dir / _STATE_FILENAME).read_text(encoding="utf-8")
    data = json.loads(text)
    assert isinstance(data, dict)
    return data


def _write_state(project_dir: Path, state: dict[str, object]) -> None:
    (project_dir / _STATE_FILENAME).write_text(json.dumps(state), encoding="utf-8")


def _install_fake_write(
    monkeypatch: pytest.MonkeyPatch,
    captured: dict[str, object],
    return_path: Path,
) -> None:
    def fake_write(
        data: dict[str, object],
        project_dir: Path,
        *,
        header_note: str = "",
    ) -> Path:
        captured["data"] = data
        captured["project_dir"] = project_dir
        captured["header_note"] = header_note
        return return_path

    monkeypatch.setattr(session_checkpoint, "write_session_state", fake_write)


class TestQualifyingTools:
    def test_non_edit_tool_is_no_op(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        captured: dict[str, object] = {}
        _install_fake_write(monkeypatch, captured, tmp_dir / "session-state.md")
        _patch_io(monkeypatch, {"tool_name": "Bash"}, tmp_dir)

        rc = session_checkpoint.main()

        assert rc == 0
        assert captured == {}
        # No state file created for non-qualifying tools.
        assert not (tmp_dir / _STATE_FILENAME).exists()

    @pytest.mark.parametrize("tool", ["Edit", "Write", "MultiEdit"])
    def test_qualifying_tools_create_state(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        tool: str,
    ) -> None:
        captured: dict[str, object] = {}
        _install_fake_write(monkeypatch, captured, tmp_dir / "session-state.md")
        _patch_io(monkeypatch, {"tool_name": tool}, tmp_dir)

        rc = session_checkpoint.main()

        assert rc == 0
        state = _read_state(tmp_dir)
        assert state["event_count"] == 1


class TestEventCountTrigger:
    def test_first_edit_does_not_fire(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        captured: dict[str, object] = {}
        _install_fake_write(monkeypatch, captured, tmp_dir / "session-state.md")
        _patch_io(monkeypatch, {"tool_name": "Edit"}, tmp_dir)

        rc = session_checkpoint.main()

        assert rc == 0
        assert captured == {}
        state = _read_state(tmp_dir)
        assert state["event_count"] == 1
        assert state["last_write_ts"] == 0.0

    def test_fifth_edit_fires_checkpoint(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_state(
            tmp_dir,
            {
                "event_count": CHECKPOINT_INTERVAL_EVENTS - 1,
                "last_write_ts": 0.0,
                "last_branch": "feat/example",
            },
        )

        captured: dict[str, object] = {}
        _install_fake_write(monkeypatch, captured, tmp_dir / "session-state.md")
        _patch_io(monkeypatch, {"tool_name": "Edit"}, tmp_dir, fixed_time=2000.0)

        rc = session_checkpoint.main()

        assert rc == 0
        assert captured["header_note"] == f"Auto-checkpoint ({CHECKPOINT_INTERVAL_EVENTS} edits)"
        # Counter resets after write; timestamp and branch recorded.
        state = _read_state(tmp_dir)
        assert state["event_count"] == 0
        assert state["last_write_ts"] == 2000.0
        assert state["last_branch"] == "feat/example"


class TestTimeTrigger:
    def test_time_elapsed_fires_checkpoint(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_state(
            tmp_dir,
            {
                "event_count": 0,
                "last_write_ts": 1000.0,
                "last_branch": "feat/example",
            },
        )

        captured: dict[str, object] = {}
        _install_fake_write(monkeypatch, captured, tmp_dir / "session-state.md")
        _patch_io(
            monkeypatch,
            {"tool_name": "Edit"},
            tmp_dir,
            fixed_time=1000.0 + CHECKPOINT_INTERVAL_SECONDS,
        )

        rc = session_checkpoint.main()

        assert rc == 0
        assert "elapsed" in str(captured["header_note"])
        state = _read_state(tmp_dir)
        assert state["event_count"] == 0

    def test_zero_last_write_does_not_trigger_time(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_state(
            tmp_dir,
            {
                "event_count": 0,
                "last_write_ts": 0.0,
                "last_branch": "feat/example",
            },
        )

        captured: dict[str, object] = {}
        _install_fake_write(monkeypatch, captured, tmp_dir / "session-state.md")
        _patch_io(monkeypatch, {"tool_name": "Edit"}, tmp_dir, fixed_time=9_999_999.0)

        rc = session_checkpoint.main()

        assert rc == 0
        assert captured == {}


class TestBranchTrigger:
    def test_branch_change_fires_checkpoint(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_state(
            tmp_dir,
            {
                "event_count": 0,
                "last_write_ts": 1000.0,
                "last_branch": "feat/old",
            },
        )

        captured: dict[str, object] = {}
        _install_fake_write(monkeypatch, captured, tmp_dir / "session-state.md")
        _patch_io(
            monkeypatch,
            {"tool_name": "Edit"},
            tmp_dir,
            branch="feat/new",
            fixed_time=1001.0,
        )

        rc = session_checkpoint.main()

        assert rc == 0
        header = str(captured["header_note"])
        assert "feat/old" in header
        assert "feat/new" in header
        state = _read_state(tmp_dir)
        assert state["last_branch"] == "feat/new"

    def test_first_invocation_empty_last_branch_no_transition(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        captured: dict[str, object] = {}
        _install_fake_write(monkeypatch, captured, tmp_dir / "session-state.md")
        _patch_io(monkeypatch, {"tool_name": "Edit"}, tmp_dir, branch="feat/example")

        rc = session_checkpoint.main()

        assert rc == 0
        assert captured == {}

    def test_missing_current_branch_does_not_transition(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_state(
            tmp_dir,
            {
                "event_count": 0,
                "last_write_ts": 1000.0,
                "last_branch": "feat/old",
            },
        )

        captured: dict[str, object] = {}
        _install_fake_write(monkeypatch, captured, tmp_dir / "session-state.md")
        _patch_io(monkeypatch, {"tool_name": "Edit"}, tmp_dir, branch="", fixed_time=1001.0)

        rc = session_checkpoint.main()

        assert rc == 0
        assert captured == {}


class TestTranscriptExtraction:
    def test_transcript_content_feeds_write(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        transcript = tmp_dir / "transcript.jsonl"
        transcript.write_text(
            '{"type":"human","content":"do the thing"}\n',
            encoding="utf-8",
        )
        _write_state(
            tmp_dir,
            {
                "event_count": CHECKPOINT_INTERVAL_EVENTS - 1,
                "last_write_ts": 0.0,
                "last_branch": "feat/example",
            },
        )

        captured: dict[str, object] = {}
        _install_fake_write(monkeypatch, captured, tmp_dir / "session-state.md")
        _patch_io(
            monkeypatch,
            {"tool_name": "Edit", "transcript_path": str(transcript)},
            tmp_dir,
        )

        rc = session_checkpoint.main()

        assert rc == 0
        data = captured["data"]
        assert isinstance(data, dict)
        assert data.get("last_user_prompt") == "do the thing"

    def test_missing_transcript_still_writes_empty_extract(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_state(
            tmp_dir,
            {
                "event_count": CHECKPOINT_INTERVAL_EVENTS - 1,
                "last_write_ts": 0.0,
                "last_branch": "feat/example",
            },
        )

        captured: dict[str, object] = {}
        _install_fake_write(monkeypatch, captured, tmp_dir / "session-state.md")
        _patch_io(monkeypatch, {"tool_name": "Edit"}, tmp_dir)

        rc = session_checkpoint.main()

        assert rc == 0
        assert captured["data"] == {}


class TestStateResilience:
    def test_malformed_state_file_is_reset(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_dir / _STATE_FILENAME).write_text("{not json", encoding="utf-8")
        captured: dict[str, object] = {}
        _install_fake_write(monkeypatch, captured, tmp_dir / "session-state.md")
        _patch_io(monkeypatch, {"tool_name": "Edit"}, tmp_dir)

        rc = session_checkpoint.main()

        assert rc == 0
        assert captured == {}
        state = _read_state(tmp_dir)
        assert state["event_count"] == 1

    def test_non_dict_state_file_is_reset(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_dir / _STATE_FILENAME).write_text("[1,2,3]", encoding="utf-8")
        captured: dict[str, object] = {}
        _install_fake_write(monkeypatch, captured, tmp_dir / "session-state.md")
        _patch_io(monkeypatch, {"tool_name": "Edit"}, tmp_dir)

        rc = session_checkpoint.main()

        assert rc == 0
        state = _read_state(tmp_dir)
        assert state["event_count"] == 1

    def test_write_failure_does_not_raise(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _write_state(
            tmp_dir,
            {
                "event_count": CHECKPOINT_INTERVAL_EVENTS - 1,
                "last_write_ts": 0.0,
                "last_branch": "feat/example",
            },
        )

        def fake_write(*_args: object, **_kwargs: object) -> Path:
            raise OSError("disk full")

        monkeypatch.setattr(session_checkpoint, "write_session_state", fake_write)
        _patch_io(monkeypatch, {"tool_name": "Edit"}, tmp_dir)

        rc = session_checkpoint.main()

        captured = capsys.readouterr()
        assert rc == 0
        assert "could not write state" in captured.err
        # Counter preserved on failure so the next call can still retry.
        state = _read_state(tmp_dir)
        assert state["event_count"] == CHECKPOINT_INTERVAL_EVENTS


class TestEmptyInput:
    def test_empty_stdin_returns_zero(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(sys, "stdin", StringIO(""))
        monkeypatch.setattr(session_checkpoint, "get_project_dir", lambda: tmp_dir)
        monkeypatch.setattr(session_checkpoint, "get_memory_dir", lambda _d: tmp_dir)

        rc = session_checkpoint.main()

        assert rc == 0
        assert not (tmp_dir / _STATE_FILENAME).exists()
