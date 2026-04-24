"""Tests for hooks/stop_failure.py."""

from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from hooks import stop_failure


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    incidents_root: Path,
    payload: dict[str, Any],
) -> None:
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(payload)))
    monkeypatch.setenv("CLAUDE_INCIDENTS_DIR", str(incidents_root))


def _first_incident_record(incidents_root: Path) -> dict[str, Any]:
    files = list(incidents_root.rglob("INC-*.jsonl"))
    assert len(files) == 1, f"expected one incident file, found {len(files)}"
    lines = [line for line in files[0].read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) >= 1
    raw = json.loads(lines[0])
    assert isinstance(raw, dict)
    return raw


class TestDetailExtraction:
    def test_explicit_error_becomes_detail(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _patch(monkeypatch, tmp_dir, {"error": "Rate limit exceeded"})

        rc = stop_failure.main()

        assert rc == 0
        rec = _first_incident_record(tmp_dir)
        assert rec["detail"] == "Rate limit exceeded"
        assert rec["category"] == "stop-failure"
        assert rec["severity"] == "error"

    def test_reason_field_used_when_error_missing(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _patch(monkeypatch, tmp_dir, {"reason": "User interrupted"})

        assert stop_failure.main() == 0
        assert _first_incident_record(tmp_dir)["detail"] == "User interrupted"

    def test_detail_priority_order(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # ``error`` wins over ``reason`` wins over ``message``.
        _patch(
            monkeypatch,
            tmp_dir,
            {"error": "E", "reason": "R", "message": "M"},
        )
        stop_failure.main()
        assert _first_incident_record(tmp_dir)["detail"] == "E"

    def test_empty_detail_fields_fall_back(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _patch(monkeypatch, tmp_dir, {"error": "", "reason": "   "})

        assert stop_failure.main() == 0
        rec = _first_incident_record(tmp_dir)
        assert "without a reported reason" in rec["detail"]


class TestExtraExtraction:
    def test_known_string_fields_included(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _patch(
            monkeypatch,
            tmp_dir,
            {
                "error": "boom",
                "session_id": "sess-abc",
                "transcript_path": "/tmp/t.jsonl",
                "error_type": "api",
                "unexpected_field": "ignored",
            },
        )

        assert stop_failure.main() == 0
        extra = _first_incident_record(tmp_dir)["extra"]
        assert extra["session_id"] == "sess-abc"
        assert extra["transcript_path"] == "/tmp/t.jsonl"
        assert extra["error_type"] == "api"
        assert "unexpected_field" not in extra

    def test_integer_exit_code_preserved(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _patch(monkeypatch, tmp_dir, {"error": "boom", "exit_code": 137})

        stop_failure.main()
        extra = _first_incident_record(tmp_dir)["extra"]
        assert extra["exit_code"] == 137

    def test_boolean_exit_code_rejected(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # ``isinstance(True, int)`` is True — guard against that coercion.
        _patch(monkeypatch, tmp_dir, {"error": "boom", "exit_code": True})

        stop_failure.main()
        extra = _first_incident_record(tmp_dir)["extra"]
        assert "exit_code" not in extra


class TestNeverBlocks:
    def test_empty_payload_still_returns_zero(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _patch(monkeypatch, tmp_dir, {})

        assert stop_failure.main() == 0
        # Incident is still written — default detail captures the gap.
        rec = _first_incident_record(tmp_dir)
        assert "without a reported reason" in rec["detail"]

    def test_empty_stdin_returns_zero(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(sys, "stdin", StringIO(""))
        monkeypatch.setenv("CLAUDE_INCIDENTS_DIR", str(tmp_dir))

        assert stop_failure.main() == 0


class TestFileLayout:
    def test_incident_file_lives_under_month_subdir(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _patch(monkeypatch, tmp_dir, {"error": "boom"})
        stop_failure.main()

        files = list(tmp_dir.rglob("INC-*.jsonl"))
        assert len(files) == 1
        # Parent is a ``YYYY-MM`` directory.
        parent = files[0].parent.name
        assert len(parent) == 7 and parent[4] == "-"
