"""Tests for hooks/post_tool_failure.py."""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from io import StringIO
from pathlib import Path

import pytest

from hooks import post_tool_failure


def _patch_io(
    monkeypatch: pytest.MonkeyPatch,
    payload: Mapping[str, object],
    memory_dir: Path,
) -> None:
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(payload)))
    monkeypatch.setattr(post_tool_failure, "get_project_dir", lambda: memory_dir.parent)
    monkeypatch.setattr(post_tool_failure, "get_memory_dir", lambda _d: memory_dir)


class TestNotAnError:
    def test_no_error_field_is_noop(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        memory_dir = tmp_dir / "memory"
        memory_dir.mkdir()
        _patch_io(monkeypatch, {"tool_name": "Edit"}, memory_dir)
        assert post_tool_failure.main() == 0
        assert not (memory_dir / "error-log.md").exists()

    def test_is_error_false_is_noop(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        memory_dir = tmp_dir / "memory"
        memory_dir.mkdir()
        _patch_io(
            monkeypatch,
            {"tool_name": "Edit", "tool_result": {"is_error": False}},
            memory_dir,
        )
        assert post_tool_failure.main() == 0
        assert not (memory_dir / "error-log.md").exists()


class TestErrorLogged:
    def test_creates_log_with_entry(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        memory_dir = tmp_dir / "memory"
        memory_dir.mkdir()
        payload = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "/app/main.py"},
            "tool_result": {
                "is_error": True,
                "content": "FileNotFoundError: missing",
            },
        }
        _patch_io(monkeypatch, payload, memory_dir)

        assert post_tool_failure.main() == 0
        log = (memory_dir / "error-log.md").read_text(encoding="utf-8")
        assert "— Edit failure" in log
        assert "file_path=/app/main.py" in log
        assert "FileNotFoundError" in log

    def test_picks_up_is_error_top_level(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        memory_dir = tmp_dir / "memory"
        memory_dir.mkdir()
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "false"},
            "is_error": True,
            "error": "exit code 1",
        }
        _patch_io(monkeypatch, payload, memory_dir)
        assert post_tool_failure.main() == 0
        log = (memory_dir / "error-log.md").read_text(encoding="utf-8")
        assert "Bash failure" in log
        assert "command=false" in log
        assert "exit code 1" in log

    def test_content_list_shape_is_extracted(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        memory_dir = tmp_dir / "memory"
        memory_dir.mkdir()
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": "/x.py"},
            "tool_result": {
                "is_error": True,
                "content": [{"type": "text", "text": "permission denied\nmore detail"}],
            },
        }
        _patch_io(monkeypatch, payload, memory_dir)
        assert post_tool_failure.main() == 0
        log = (memory_dir / "error-log.md").read_text(encoding="utf-8")
        assert "permission denied" in log
        assert "more detail" not in log  # only first line kept

    def test_long_error_is_truncated(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        memory_dir = tmp_dir / "memory"
        memory_dir.mkdir()
        big = "X" * 500
        payload = {
            "tool_name": "Bash",
            "is_error": True,
            "tool_result": {"is_error": True, "content": big},
        }
        _patch_io(monkeypatch, payload, memory_dir)
        assert post_tool_failure.main() == 0
        log = (memory_dir / "error-log.md").read_text(encoding="utf-8")
        assert "…" in log
        assert "X" * 500 not in log


class TestRotation:
    def test_appends_above_existing(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        memory_dir = tmp_dir / "memory"
        memory_dir.mkdir()
        log_path = memory_dir / "error-log.md"
        log_path.write_text(
            "### 2024-01-01 00:00:00 UTC — OldTool failure\n- earlier\n",
            encoding="utf-8",
        )
        payload = {
            "tool_name": "Edit",
            "is_error": True,
            "error": "new failure",
        }
        _patch_io(monkeypatch, payload, memory_dir)
        assert post_tool_failure.main() == 0
        log = log_path.read_text(encoding="utf-8")
        assert log.index("Edit failure") < log.index("OldTool failure")

    def test_caps_at_50_entries(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        memory_dir = tmp_dir / "memory"
        memory_dir.mkdir()
        log_path = memory_dir / "error-log.md"

        existing_blocks = [
            f"### 2024-01-01 00:{i:02d}:00 UTC — Tool{i} failure\n- existing entry {i}\n"
            for i in range(55)
        ]
        log_path.write_text("\n".join(existing_blocks), encoding="utf-8")

        payload = {"tool_name": "Edit", "is_error": True, "error": "newest"}
        _patch_io(monkeypatch, payload, memory_dir)
        assert post_tool_failure.main() == 0

        log = log_path.read_text(encoding="utf-8")
        # Count entries — should be at most 50
        entry_count = log.count("### ")
        assert entry_count <= 50
        # Newest entry is present
        assert "newest" in log
        # Oldest 5+ should be trimmed
        assert "Tool0 failure" not in log
        assert "Tool4 failure" not in log
        # Most recent of the existing should still be there
        assert "Tool54 failure" in log


class TestWriteFailure:
    def test_oserror_logged_not_raised(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        memory_dir = tmp_dir / "memory"
        memory_dir.mkdir()
        _patch_io(
            monkeypatch,
            {"tool_name": "Edit", "is_error": True, "error": "x"},
            memory_dir,
        )

        def boom(*_args: object, **_kwargs: object) -> Path:
            raise OSError("disk full")

        monkeypatch.setattr("hooks.post_tool_failure.atomic_write", boom)
        assert post_tool_failure.main() == 0
        captured = capsys.readouterr()
        assert "could not write log" in captured.err
