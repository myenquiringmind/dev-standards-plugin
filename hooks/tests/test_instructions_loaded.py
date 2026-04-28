"""Tests for hooks/instructions_loaded.py."""

from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from hooks import instructions_loaded


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    telemetry_dir: Path,
    payload: dict[str, Any] | None = None,
) -> None:
    body = json.dumps(payload) if payload is not None else ""
    monkeypatch.setattr(sys, "stdin", StringIO(body))
    monkeypatch.setenv("CLAUDE_TELEMETRY_DIR", str(telemetry_dir))


def _read_telemetry(telemetry_dir: Path) -> list[dict[str, Any]]:
    files = sorted(telemetry_dir.glob("*.jsonl"))
    records: list[dict[str, Any]] = []
    for path in files:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                assert isinstance(rec, dict)
                records.append(rec)
    return records


# ---------------------------------------------------------------------------
# Happy paths — each candidate field
# ---------------------------------------------------------------------------


class TestPayloadShapes:
    @pytest.mark.parametrize("key", ["instructions", "loaded_files", "files", "paths"])
    def test_string_list_under_each_candidate_key(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch, key: str
    ) -> None:
        _patch(
            monkeypatch,
            tmp_dir,
            {key: ["CLAUDE.md", ".claude/rules/session-lifecycle.md"]},
        )

        assert instructions_loaded.main() == 0

        records = _read_telemetry(tmp_dir)
        assert len(records) == 1
        rec = records[0]
        assert rec["category"] == "instructions-loaded"
        assert rec["data"]["count"] == 2
        assert rec["data"]["files"] == [
            "CLAUDE.md",
            ".claude/rules/session-lifecycle.md",
        ]

    def test_dict_items_with_path_key(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch(
            monkeypatch,
            tmp_dir,
            {
                "instructions": [
                    {"path": "CLAUDE.md", "size": 1024},
                    {"path": ".claude/rules/foo.md"},
                ]
            },
        )

        instructions_loaded.main()
        rec = _read_telemetry(tmp_dir)[0]
        assert rec["data"]["files"] == ["CLAUDE.md", ".claude/rules/foo.md"]

    def test_first_non_empty_candidate_wins(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # ``instructions`` is empty; fall through to ``loaded_files``.
        _patch(
            monkeypatch,
            tmp_dir,
            {"instructions": [], "loaded_files": ["second.md"]},
        )

        instructions_loaded.main()
        rec = _read_telemetry(tmp_dir)[0]
        assert rec["data"]["files"] == ["second.md"]

    def test_mixed_string_and_dict_items(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch(
            monkeypatch,
            tmp_dir,
            {"instructions": ["a.md", {"path": "b.md"}, "c.md"]},
        )

        instructions_loaded.main()
        rec = _read_telemetry(tmp_dir)[0]
        assert rec["data"]["files"] == ["a.md", "b.md", "c.md"]


# ---------------------------------------------------------------------------
# Filtering — non-string / dict-without-path / whitespace
# ---------------------------------------------------------------------------


class TestFiltering:
    def test_non_string_items_dropped(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch(
            monkeypatch,
            tmp_dir,
            {"instructions": ["good.md", 42, None, ""]},
        )

        instructions_loaded.main()
        rec = _read_telemetry(tmp_dir)[0]
        assert rec["data"]["files"] == ["good.md"]
        assert rec["data"]["count"] == 1

    def test_whitespace_only_strings_dropped(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch(
            monkeypatch,
            tmp_dir,
            {"instructions": ["   ", "real.md", "\t\n"]},
        )

        instructions_loaded.main()
        rec = _read_telemetry(tmp_dir)[0]
        assert rec["data"]["files"] == ["real.md"]

    def test_dicts_without_path_key_dropped(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch(
            monkeypatch,
            tmp_dir,
            {"instructions": [{"name": "no-path"}, {"path": "yes.md"}]},
        )

        instructions_loaded.main()
        rec = _read_telemetry(tmp_dir)[0]
        assert rec["data"]["files"] == ["yes.md"]

    def test_dicts_with_non_string_path_dropped(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch(
            monkeypatch,
            tmp_dir,
            {"instructions": [{"path": 42}, {"path": "good.md"}]},
        )

        instructions_loaded.main()
        rec = _read_telemetry(tmp_dir)[0]
        assert rec["data"]["files"] == ["good.md"]


# ---------------------------------------------------------------------------
# No-data emit-anyway — partial audit beats no audit
# ---------------------------------------------------------------------------


class TestNoData:
    def test_empty_payload_emits_zero_count(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch(monkeypatch, tmp_dir, {})

        assert instructions_loaded.main() == 0
        rec = _read_telemetry(tmp_dir)[0]
        assert rec["data"]["files"] == []
        assert rec["data"]["count"] == 0

    def test_unrecognised_field_emits_zero_count(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch(monkeypatch, tmp_dir, {"some_other_field": ["ignored.md"]})

        instructions_loaded.main()
        rec = _read_telemetry(tmp_dir)[0]
        assert rec["data"]["files"] == []

    def test_non_list_value_emits_zero_count(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch(monkeypatch, tmp_dir, {"instructions": "not-a-list.md"})

        instructions_loaded.main()
        rec = _read_telemetry(tmp_dir)[0]
        assert rec["data"]["files"] == []

    def test_empty_stdin_emits_zero_count(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch(monkeypatch, tmp_dir, payload=None)

        assert instructions_loaded.main() == 0
        rec = _read_telemetry(tmp_dir)[0]
        assert rec["data"]["files"] == []
