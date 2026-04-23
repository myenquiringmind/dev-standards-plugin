"""Tests for hooks/_incident.py."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from hooks import _incident

_ULID_PATTERN = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")


@pytest.fixture
def incidents_root(tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_dir / "incidents"
    monkeypatch.setenv("CLAUDE_INCIDENTS_DIR", str(root))
    return root


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


class TestUlidGeneration:
    def test_26_char_crockford_base32(self) -> None:
        ulid = _incident._generate_ulid()
        assert len(ulid) == 26
        assert _ULID_PATTERN.match(ulid), f"ULID malformed: {ulid!r}"

    def test_many_ulids_are_unique(self) -> None:
        ulids = {_incident._generate_ulid() for _ in range(1000)}
        assert len(ulids) == 1000  # probability of collision in 80-bit random < 1e-21

    def test_ulids_sort_lexicographically_by_time(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Deterministic clock: feed two timestamps 1s apart. The timestamp
        # dominates the leading 10 characters, so even if the random tail
        # of the earlier ULID is all-Z, the later one still sorts after.
        fake_times = iter([1_700_000_000.000, 1_700_000_001.000])
        monkeypatch.setattr("time.time", lambda: next(fake_times))

        first = _incident._generate_ulid()
        second = _incident._generate_ulid()
        assert first < second, f"{first!r} should sort before {second!r}"
        # Verify the leading 10 chars (timestamp) differ in the expected direction.
        assert first[:10] < second[:10]


class TestWriteIncident:
    def test_basic_write(self, incidents_root: Path) -> None:
        ulid = _incident.write_incident("stop-failure", "commit gate rejected")

        assert _ULID_PATTERN.match(ulid)
        # File path: incidents/<YYYY-MM>/INC-<ulid>.jsonl
        today = datetime.now(UTC).strftime("%Y-%m")
        path = incidents_root / today / f"INC-{ulid}.jsonl"
        assert path.is_file()

        records = _read_jsonl(path)
        assert len(records) == 1
        rec = records[0]
        assert rec["ulid"] == ulid
        assert rec["category"] == "stop-failure"
        assert rec["severity"] == "error"
        assert rec["detail"] == "commit gate rejected"
        assert rec["extra"] == {}
        assert rec["timestamp"].endswith("Z")

    def test_extra_fields_roundtrip(self, incidents_root: Path) -> None:
        ulid = _incident.write_incident(
            "stop-failure",
            "test",
            branch="feat/example",
            attempt=3,
        )
        today = datetime.now(UTC).strftime("%Y-%m")
        path = incidents_root / today / f"INC-{ulid}.jsonl"
        records = _read_jsonl(path)
        assert records[0]["extra"] == {"branch": "feat/example", "attempt": 3}

    @pytest.mark.parametrize("severity", ["error", "warn", "info"])
    def test_valid_severity(self, incidents_root: Path, severity: str) -> None:
        ulid = _incident.write_incident("x", "detail", severity=severity)
        assert _ULID_PATTERN.match(ulid)

    @pytest.mark.parametrize("severity", ["critical", "debug", "", "ERROR"])
    def test_invalid_severity_rejected(
        self, incidents_root: Path, severity: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        ulid = _incident.write_incident("x", "detail", severity=severity)
        assert ulid == ""
        assert "refusing invalid severity" in capsys.readouterr().err

    @pytest.mark.parametrize("bad", ["Bad-Cat", "bad_cat", "", "../escape", "-leading"])
    def test_invalid_category_rejected(
        self, incidents_root: Path, bad: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        ulid = _incident.write_incident(bad, "detail")
        assert ulid == ""
        assert "refusing invalid category" in capsys.readouterr().err

    def test_empty_detail_rejected(
        self, incidents_root: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        ulid = _incident.write_incident("x", "   \t\n")
        assert ulid == ""
        assert "refusing empty detail" in capsys.readouterr().err

    def test_non_serialisable_extra_rejected(
        self, incidents_root: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        class NotJson:
            pass

        ulid = _incident.write_incident("x", "detail", bad=NotJson())
        assert ulid == ""
        assert "not JSON-serialisable" in capsys.readouterr().err


class TestAppendToIncident:
    def test_append_to_existing_incident(self, incidents_root: Path) -> None:
        ulid = _incident.write_incident("stop-failure", "initial failure")
        ok = _incident.append_to_incident(ulid, "user notified", severity="info")
        assert ok is True

        today = datetime.now(UTC).strftime("%Y-%m")
        path = incidents_root / today / f"INC-{ulid}.jsonl"
        records = _read_jsonl(path)
        assert len(records) == 2
        assert records[0]["detail"] == "initial failure"
        assert records[0]["severity"] == "error"
        assert records[1]["detail"] == "user notified"
        assert records[1]["severity"] == "info"

    def test_multiple_appends_preserve_order(self, incidents_root: Path) -> None:
        ulid = _incident.write_incident("x", "start")
        for i in range(5):
            _incident.append_to_incident(ulid, f"step {i}")

        today = datetime.now(UTC).strftime("%Y-%m")
        path = incidents_root / today / f"INC-{ulid}.jsonl"
        records = _read_jsonl(path)
        assert [r["detail"] for r in records] == [
            "start",
            "step 0",
            "step 1",
            "step 2",
            "step 3",
            "step 4",
        ]

    def test_append_to_unknown_ulid_fails(
        self, incidents_root: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Valid ULID format but no corresponding file.
        fake = "0" * 26
        ok = _incident.append_to_incident(fake, "note")
        assert ok is False
        assert "no incident file" in capsys.readouterr().err

    def test_append_to_malformed_ulid_fails(
        self, incidents_root: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        ok = _incident.append_to_incident("not-a-ulid", "note")
        assert ok is False
        assert "refusing invalid ulid" in capsys.readouterr().err

    def test_append_empty_detail_rejected(
        self, incidents_root: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        ulid = _incident.write_incident("x", "start")
        ok = _incident.append_to_incident(ulid, "")
        assert ok is False
        assert "refusing empty detail" in capsys.readouterr().err

    def test_append_invalid_severity_rejected(
        self, incidents_root: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        ulid = _incident.write_incident("x", "start")
        ok = _incident.append_to_incident(ulid, "note", severity="critical")
        assert ok is False
        assert "refusing invalid severity" in capsys.readouterr().err


class TestFinderAcrossMonths:
    def test_find_incident_across_month_subdirs(
        self, incidents_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Simulate a prior-month incident by manually creating the file.
        ulid = "01HQJR7K0P7E9X0XZHGMS8A5Q8"
        prior = incidents_root / "2026-01" / f"INC-{ulid}.jsonl"
        prior.parent.mkdir(parents=True)
        prior.write_text(json.dumps({"ulid": ulid, "detail": "old"}) + "\n", encoding="utf-8")

        # Appending should find it even though the current month differs.
        ok = _incident.append_to_incident(ulid, "still going")
        assert ok is True
        records = _read_jsonl(prior)
        assert len(records) == 2
