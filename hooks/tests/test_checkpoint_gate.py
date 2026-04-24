"""Tests for hooks/checkpoint_gate.py."""

from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from hooks import checkpoint_gate
from hooks._hook_shared import (
    CHECKPOINT_INTERVAL_SECONDS,
    CHECKPOINT_STALENESS_THRESHOLD_SECONDS,
)

_STATE_FILENAME = "session-checkpoint.state.json"


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    memory_dir: Path,
    *,
    payload: dict[str, Any],
    fixed_time: float = 1_000_000.0,
) -> None:
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(payload)))
    monkeypatch.setattr(checkpoint_gate, "get_project_dir", lambda: memory_dir)
    monkeypatch.setattr(checkpoint_gate, "get_memory_dir", lambda _d: memory_dir)
    monkeypatch.setattr("time.time", lambda: fixed_time)


def _write_state(memory_dir: Path, state: dict[str, Any]) -> None:
    (memory_dir / _STATE_FILENAME).write_text(json.dumps(state), encoding="utf-8")


def _bash(agent_type: str, command: str = "git status") -> dict[str, Any]:
    return {
        "tool_name": "Bash",
        "agent_type": agent_type,
        "tool_input": {"command": command},
    }


# ---------------------------------------------------------------------------
# Fail-open: out-of-scope tool / missing agent context / no state / fresh
# ---------------------------------------------------------------------------


class TestFailOpen:
    def test_non_bash_tool_is_no_op(self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_state(tmp_dir, {"last_write_ts": 1.0})
        _patch(
            monkeypatch,
            tmp_dir,
            payload={"tool_name": "Edit", "agent_type": "scanner"},
            fixed_time=9_999_999.0,
        )

        assert checkpoint_gate.main() == 0

    def test_missing_agent_type_is_no_op(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Main-thread Bash — no ``agent_type`` — passes even when stale.
        _write_state(tmp_dir, {"last_write_ts": 1.0})
        _patch(
            monkeypatch,
            tmp_dir,
            payload={"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}},
            fixed_time=9_999_999.0,
        )

        assert checkpoint_gate.main() == 0

    def test_empty_agent_type_is_no_op(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_state(tmp_dir, {"last_write_ts": 1.0})
        _patch(
            monkeypatch,
            tmp_dir,
            payload={"tool_name": "Bash", "agent_type": ""},
            fixed_time=9_999_999.0,
        )

        assert checkpoint_gate.main() == 0

    def test_missing_state_file_is_no_op(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # No file at all — fresh session, no checkpoint ever.
        _patch(monkeypatch, tmp_dir, payload=_bash("scanner"), fixed_time=9_999_999.0)

        assert checkpoint_gate.main() == 0

    def test_last_write_ts_zero_is_no_op(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Counter accumulating but no checkpoint has flushed yet.
        _write_state(
            tmp_dir,
            {"event_count": 3, "last_write_ts": 0.0, "last_branch": "feat/x"},
        )
        _patch(monkeypatch, tmp_dir, payload=_bash("scanner"), fixed_time=9_999_999.0)

        assert checkpoint_gate.main() == 0

    def test_missing_last_write_ts_field_is_no_op(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_state(tmp_dir, {"event_count": 2})
        _patch(monkeypatch, tmp_dir, payload=_bash("scanner"), fixed_time=9_999_999.0)

        assert checkpoint_gate.main() == 0

    def test_non_numeric_last_write_ts_is_no_op(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_state(tmp_dir, {"last_write_ts": "yesterday"})
        _patch(monkeypatch, tmp_dir, payload=_bash("scanner"), fixed_time=9_999_999.0)

        assert checkpoint_gate.main() == 0

    def test_malformed_state_file_is_no_op(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_dir / _STATE_FILENAME).write_text("{not json", encoding="utf-8")
        _patch(monkeypatch, tmp_dir, payload=_bash("scanner"), fixed_time=9_999_999.0)

        assert checkpoint_gate.main() == 0

    def test_non_dict_state_file_is_no_op(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_dir / _STATE_FILENAME).write_text("[1, 2, 3]", encoding="utf-8")
        _patch(monkeypatch, tmp_dir, payload=_bash("scanner"), fixed_time=9_999_999.0)

        assert checkpoint_gate.main() == 0

    def test_fresh_checkpoint_passes(self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Within the threshold — a checkpoint flushed recently.
        _write_state(tmp_dir, {"last_write_ts": 1_000.0})
        _patch(
            monkeypatch,
            tmp_dir,
            payload=_bash("scanner"),
            fixed_time=1_000.0 + CHECKPOINT_INTERVAL_SECONDS,  # 15 min — still fresh
        )

        assert checkpoint_gate.main() == 0

    def test_threshold_boundary_passes(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Exactly at the threshold — does not fire (strict ``>=``).
        _write_state(tmp_dir, {"last_write_ts": 1_000.0})
        _patch(
            monkeypatch,
            tmp_dir,
            payload=_bash("scanner"),
            fixed_time=1_000.0 + CHECKPOINT_STALENESS_THRESHOLD_SECONDS - 1,
        )

        assert checkpoint_gate.main() == 0


# ---------------------------------------------------------------------------
# Fail-closed: subagent Bash when state is stale
# ---------------------------------------------------------------------------


class TestBlocksStaleCheckpoint:
    def test_stale_state_blocks_subagent(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _write_state(tmp_dir, {"last_write_ts": 1_000.0})
        fixed = 1_000.0 + CHECKPOINT_STALENESS_THRESHOLD_SECONDS + 1
        _patch(monkeypatch, tmp_dir, payload=_bash("scanner"), fixed_time=fixed)

        rc = checkpoint_gate.main()

        err = capsys.readouterr().err
        assert rc == 2
        assert "refusing" in err
        assert "scanner" in err
        assert str(CHECKPOINT_STALENESS_THRESHOLD_SECONDS) in err
        # Elapsed count appears as whole seconds.
        assert str(CHECKPOINT_STALENESS_THRESHOLD_SECONDS + 1) in err

    def test_blocks_regardless_of_command(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Staleness, not command content, drives the block. Even a
        # read-only ``git status`` is refused when the gate fires.
        _write_state(tmp_dir, {"last_write_ts": 1_000.0})
        fixed = 1_000.0 + CHECKPOINT_STALENESS_THRESHOLD_SECONDS + 1
        _patch(
            monkeypatch,
            tmp_dir,
            payload=_bash("scanner", command="git status"),
            fixed_time=fixed,
        )

        assert checkpoint_gate.main() == 2

    def test_block_message_names_remediation(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _write_state(tmp_dir, {"last_write_ts": 1_000.0})
        fixed = 1_000.0 + CHECKPOINT_STALENESS_THRESHOLD_SECONDS + 1
        _patch(monkeypatch, tmp_dir, payload=_bash("planner"), fixed_time=fixed)

        checkpoint_gate.main()
        err = capsys.readouterr().err
        # The message points the caller at both recovery paths.
        assert "AskUserQuestion" in err
        assert "/handoff" in err
        assert "Edit/Write" in err


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestInputResilience:
    def test_empty_stdin_returns_zero(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sys, "stdin", StringIO(""))
        monkeypatch.setattr(checkpoint_gate, "get_project_dir", lambda: tmp_dir)
        monkeypatch.setattr(checkpoint_gate, "get_memory_dir", lambda _d: tmp_dir)

        assert checkpoint_gate.main() == 0

    def test_missing_tool_name_returns_zero(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch(monkeypatch, tmp_dir, payload={"agent_type": "scanner"})
        assert checkpoint_gate.main() == 0
