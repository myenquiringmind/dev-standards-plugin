"""Tests for hooks/permission_denied.py."""

from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from hooks import permission_denied


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    incidents_root: Path,
    payload: dict[str, Any],
) -> None:
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(payload)))
    monkeypatch.setenv("CLAUDE_INCIDENTS_DIR", str(incidents_root))


def _first_record(incidents_root: Path) -> dict[str, Any]:
    files = list(incidents_root.rglob("INC-*.jsonl"))
    assert len(files) == 1
    raw = json.loads(files[0].read_text(encoding="utf-8").splitlines()[0])
    assert isinstance(raw, dict)
    return raw


# ---------------------------------------------------------------------------
# Detail extraction
# ---------------------------------------------------------------------------


class TestDetailExtraction:
    def test_error_field_used(self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch(monkeypatch, tmp_dir, {"error": "denied by deny-list"})

        assert permission_denied.main() == 0
        rec = _first_record(tmp_dir)
        assert rec["detail"] == "denied by deny-list"
        assert rec["category"] == "permission-denied"
        assert rec["severity"] == "warn"

    def test_detail_priority_order(self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch(
            monkeypatch,
            tmp_dir,
            {"error": "E", "reason": "R", "message": "M", "detail": "D"},
        )
        permission_denied.main()
        assert _first_record(tmp_dir)["detail"] == "E"

    def test_empty_strings_fall_through(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch(monkeypatch, tmp_dir, {"error": "", "reason": "   ", "message": "actually here"})

        permission_denied.main()
        assert _first_record(tmp_dir)["detail"] == "actually here"

    def test_default_detail_when_all_missing(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch(monkeypatch, tmp_dir, {})

        permission_denied.main()
        rec = _first_record(tmp_dir)
        assert "without a reported reason" in rec["detail"]


# ---------------------------------------------------------------------------
# Extra extraction
# ---------------------------------------------------------------------------


class TestExtraExtraction:
    def test_top_level_string_fields(self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch(
            monkeypatch,
            tmp_dir,
            {
                "error": "denied",
                "tool_name": "Bash",
                "session_id": "sess-abc",
                "transcript_path": "/tmp/t.jsonl",
                "ignored": "should not appear",
            },
        )

        permission_denied.main()
        extra = _first_record(tmp_dir)["extra"]
        assert extra["tool_name"] == "Bash"
        assert extra["session_id"] == "sess-abc"
        assert extra["transcript_path"] == "/tmp/t.jsonl"
        assert "ignored" not in extra

    def test_tool_input_fields_pulled(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch(
            monkeypatch,
            tmp_dir,
            {
                "error": "denied",
                "tool_name": "Edit",
                "tool_input": {
                    "file_path": "/abs/path.py",
                    "command": "rm -rf /tmp/x",
                    "url": "https://example.com",
                    "pattern": "secret.*",
                    "extra_random": "ignored",
                },
            },
        )

        permission_denied.main()
        extra = _first_record(tmp_dir)["extra"]
        assert extra["file_path"] == "/abs/path.py"
        assert extra["command"] == "rm -rf /tmp/x"
        assert extra["url"] == "https://example.com"
        assert extra["pattern"] == "secret.*"
        assert "extra_random" not in extra

    def test_tool_input_non_dict_safely_skipped(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch(
            monkeypatch,
            tmp_dir,
            {"error": "denied", "tool_name": "Bash", "tool_input": "not a dict"},
        )

        assert permission_denied.main() == 0
        rec = _first_record(tmp_dir)
        assert rec["extra"]["tool_name"] == "Bash"

    def test_boolean_excluded_from_int_extras(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Construct a payload where a boolean might sneak into the int branch
        # via the int-isinstance check. The hook must guard against True/False.
        _patch(
            monkeypatch,
            tmp_dir,
            {
                "error": "denied",
                "tool_name": True,
            },
        )

        permission_denied.main()
        extra = _first_record(tmp_dir)["extra"]
        assert "tool_name" not in extra

    def test_empty_strings_not_recorded(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch(
            monkeypatch,
            tmp_dir,
            {"error": "denied", "tool_name": "", "session_id": "   "},
        )

        permission_denied.main()
        extra = _first_record(tmp_dir)["extra"]
        assert "tool_name" not in extra
        assert "session_id" not in extra


# ---------------------------------------------------------------------------
# Never blocks
# ---------------------------------------------------------------------------


class TestNeverBlocks:
    def test_empty_payload_records_default(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch(monkeypatch, tmp_dir, {})

        assert permission_denied.main() == 0
        # Default record still gets written.
        rec = _first_record(tmp_dir)
        assert rec["category"] == "permission-denied"

    def test_empty_stdin_returns_zero(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sys, "stdin", StringIO(""))
        monkeypatch.setenv("CLAUDE_INCIDENTS_DIR", str(tmp_dir))

        assert permission_denied.main() == 0


class TestFileLayout:
    def test_record_under_month_subdir(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch(monkeypatch, tmp_dir, {"error": "denied"})
        permission_denied.main()

        files = list(tmp_dir.rglob("INC-*.jsonl"))
        assert len(files) == 1
        parent = files[0].parent.name
        assert len(parent) == 7 and parent[4] == "-"
