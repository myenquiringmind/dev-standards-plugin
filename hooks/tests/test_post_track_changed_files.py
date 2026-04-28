"""Tests for hooks/post_track_changed_files.py."""

from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from hooks import post_track_changed_files

_LOG_FILENAME = "changed-files.log"


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    memory_dir: Path,
    payload: dict[str, Any],
) -> None:
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(payload)))
    monkeypatch.setattr(post_track_changed_files, "get_project_dir", lambda: memory_dir)
    monkeypatch.setattr(post_track_changed_files, "get_memory_dir", lambda _d: memory_dir)


def _read_log(memory_dir: Path) -> list[str]:
    path = memory_dir / _LOG_FILENAME
    if not path.exists():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestAppend:
    @pytest.mark.parametrize("tool", ["Edit", "Write", "MultiEdit"])
    def test_qualifying_tool_appends_one_line(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        tool: str,
    ) -> None:
        _patch(
            monkeypatch,
            tmp_dir,
            {
                "tool_name": tool,
                "tool_input": {"file_path": "/abs/path.py"},
            },
        )

        assert post_track_changed_files.main() == 0

        lines = _read_log(tmp_dir)
        assert len(lines) == 1
        parts = lines[0].split("\t")
        assert len(parts) == 3
        timestamp, recorded_tool, recorded_path = parts
        assert recorded_tool == tool
        assert recorded_path == "/abs/path.py"
        # Timestamp follows the ISO-8601 UTC pattern (Z suffix).
        assert timestamp.endswith("Z")
        assert "T" in timestamp

    def test_repeated_edits_produce_multiple_lines(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for _ in range(3):
            _patch(
                monkeypatch,
                tmp_dir,
                {"tool_name": "Edit", "tool_input": {"file_path": "/x.py"}},
            )
            post_track_changed_files.main()

        lines = _read_log(tmp_dir)
        assert len(lines) == 3
        assert all("\t/x.py" in line for line in lines)

    def test_log_appended_not_overwritten(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pre-seed an existing log line. The hook must not clobber it.
        existing = "2026-01-01T00:00:00Z\tEdit\t/old.py\n"
        (tmp_dir / _LOG_FILENAME).write_text(existing, encoding="utf-8")

        _patch(
            monkeypatch,
            tmp_dir,
            {"tool_name": "Write", "tool_input": {"file_path": "/new.py"}},
        )
        post_track_changed_files.main()

        lines = _read_log(tmp_dir)
        assert len(lines) == 2
        assert "/old.py" in lines[0]
        assert "/new.py" in lines[1]

    def test_memory_dir_created_if_missing(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        nested = tmp_dir / "deep" / "nested" / "memory"
        # Do not pre-create.
        monkeypatch.setattr(
            sys,
            "stdin",
            StringIO(json.dumps({"tool_name": "Edit", "tool_input": {"file_path": "/x.py"}})),
        )
        monkeypatch.setattr(post_track_changed_files, "get_project_dir", lambda: tmp_dir)
        monkeypatch.setattr(post_track_changed_files, "get_memory_dir", lambda _d: nested)

        assert post_track_changed_files.main() == 0
        assert (nested / _LOG_FILENAME).exists()


# ---------------------------------------------------------------------------
# Tool-name and payload gates — no-op cases
# ---------------------------------------------------------------------------


class TestNoOpCases:
    @pytest.mark.parametrize("tool", ["Bash", "Read", "Grep", "TodoWrite", ""])
    def test_non_qualifying_tools_skip(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        tool: str,
    ) -> None:
        _patch(
            monkeypatch,
            tmp_dir,
            {"tool_name": tool, "tool_input": {"file_path": "/x.py"}},
        )

        assert post_track_changed_files.main() == 0
        assert _read_log(tmp_dir) == []

    def test_missing_tool_input_is_no_op(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch(monkeypatch, tmp_dir, {"tool_name": "Edit"})

        assert post_track_changed_files.main() == 0
        assert _read_log(tmp_dir) == []

    def test_missing_file_path_is_no_op(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch(
            monkeypatch,
            tmp_dir,
            {"tool_name": "Edit", "tool_input": {"old_string": "x"}},
        )

        assert post_track_changed_files.main() == 0
        assert _read_log(tmp_dir) == []

    def test_empty_file_path_is_no_op(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch(
            monkeypatch,
            tmp_dir,
            {"tool_name": "Edit", "tool_input": {"file_path": "   "}},
        )

        assert post_track_changed_files.main() == 0
        assert _read_log(tmp_dir) == []

    def test_non_string_file_path_is_no_op(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch(
            monkeypatch,
            tmp_dir,
            {"tool_name": "Edit", "tool_input": {"file_path": 42}},
        )

        assert post_track_changed_files.main() == 0
        assert _read_log(tmp_dir) == []

    def test_non_dict_tool_input_is_no_op(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch(monkeypatch, tmp_dir, {"tool_name": "Edit", "tool_input": "not a dict"})

        assert post_track_changed_files.main() == 0
        assert _read_log(tmp_dir) == []


# ---------------------------------------------------------------------------
# Resilience
# ---------------------------------------------------------------------------


class TestResilience:
    def test_empty_stdin_returns_zero(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sys, "stdin", StringIO(""))
        monkeypatch.setattr(post_track_changed_files, "get_project_dir", lambda: tmp_dir)
        monkeypatch.setattr(post_track_changed_files, "get_memory_dir", lambda _d: tmp_dir)

        assert post_track_changed_files.main() == 0
        assert _read_log(tmp_dir) == []

    def test_append_failure_is_logged_not_raised(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Make the log path a directory so ``open(..., "a")`` raises OSError
        # (IsADirectoryError on POSIX, PermissionError on Windows — both
        # subclasses of OSError). The hook's catch path should run and
        # surface a stderr message; the hook itself must still exit 0.
        (tmp_dir / _LOG_FILENAME).mkdir()

        _patch(
            monkeypatch,
            tmp_dir,
            {"tool_name": "Edit", "tool_input": {"file_path": "/x.py"}},
        )

        assert post_track_changed_files.main() == 0
        err = capsys.readouterr().err
        assert "could not append" in err
