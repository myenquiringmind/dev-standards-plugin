"""Round-trip tests: actual records from _incident/_telemetry validate
against schemas/contracts/incident.schema.json and telemetry-record.schema.json.

This is the single load-bearing test for the Phase 4 contract schemas.
The schemas pin the shape that hooks._incident.write_incident() /
append_to_incident() and hooks._telemetry.emit() actually produce,
so the round-trip is the test — generating a record then validating
it catches both schema drift and emitter drift.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

from hooks import _incident, _telemetry

_REPO_ROOT = Path(__file__).resolve().parents[2]
_INCIDENT_SCHEMA_PATH = _REPO_ROOT / "schemas" / "contracts" / "incident.schema.json"
_TELEMETRY_SCHEMA_PATH = _REPO_ROOT / "schemas" / "contracts" / "telemetry-record.schema.json"


def _load_schema(path: Path) -> dict[str, object]:
    parsed: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
    return parsed


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line:
            out.append(json.loads(line))
    return out


@pytest.fixture
def incident_root(tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_dir / "incidents"
    monkeypatch.setenv("CLAUDE_INCIDENTS_DIR", str(root))
    return root


@pytest.fixture
def telemetry_root(tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_dir / "telemetry"
    monkeypatch.setenv("CLAUDE_TELEMETRY_DIR", str(root))
    return root


class TestSchemasSelfValidate:
    def test_incident_schema_meta_validates(self) -> None:
        schema = _load_schema(_INCIDENT_SCHEMA_PATH)
        Draft202012Validator.check_schema(schema)

    def test_telemetry_schema_meta_validates(self) -> None:
        schema = _load_schema(_TELEMETRY_SCHEMA_PATH)
        Draft202012Validator.check_schema(schema)


class TestIncidentRoundTrip:
    """Records produced by _incident must validate against incident.schema.json."""

    def test_initial_record_validates(self, incident_root: Path) -> None:
        ulid = _incident.write_incident(
            "stop-failure",
            "Stop handshake failed mid-tool-call",
            severity="error",
            tool_name="Edit",
            exit_code=2,
        )
        assert ulid

        files = list(incident_root.rglob("INC-*.jsonl"))
        assert len(files) == 1
        records = _read_jsonl(files[0])
        assert len(records) == 1

        schema = _load_schema(_INCIDENT_SCHEMA_PATH)
        errors = list(Draft202012Validator(schema).iter_errors(records[0]))
        assert not errors, f"initial record rejected: {[e.message for e in errors]}"

    def test_initial_record_carries_category(self, incident_root: Path) -> None:
        _incident.write_incident("permission-denied", "Tool call rejected")
        files = list(incident_root.rglob("INC-*.jsonl"))
        records = _read_jsonl(files[0])
        assert records[0]["category"] == "permission-denied"

    def test_followup_record_validates_without_category(self, incident_root: Path) -> None:
        ulid = _incident.write_incident("stop-failure", "Initial failure")
        assert ulid

        ok = _incident.append_to_incident(
            ulid, "Resolved by retry", severity="info", retry_count=1
        )
        assert ok

        files = list(incident_root.rglob("INC-*.jsonl"))
        records = _read_jsonl(files[0])
        assert len(records) == 2

        schema = _load_schema(_INCIDENT_SCHEMA_PATH)
        for i, record in enumerate(records):
            errors = list(Draft202012Validator(schema).iter_errors(record))
            assert not errors, f"record {i} rejected: {[e.message for e in errors]}"

        # Initial has category; follow-up does not.
        assert "category" in records[0]
        assert "category" not in records[1]

    def test_all_severity_values_validate(self, incident_root: Path) -> None:
        for severity in ("error", "warn", "info"):
            _incident.write_incident("stop-failure", f"detail-{severity}", severity=severity)

        files = list(incident_root.rglob("INC-*.jsonl"))
        assert len(files) == 3

        schema = _load_schema(_INCIDENT_SCHEMA_PATH)
        for path in files:
            for record in _read_jsonl(path):
                errors = list(Draft202012Validator(schema).iter_errors(record))
                assert not errors, f"record rejected for severity in {path}: {errors}"


class TestTelemetryRoundTrip:
    """Records produced by _telemetry must validate against
    telemetry-record.schema.json."""

    def test_emit_record_validates(self, telemetry_root: Path) -> None:
        _telemetry.emit("hook-failure", {"tool": "Edit", "exit": 2})

        files = list(telemetry_root.glob("*.jsonl"))
        assert len(files) == 1
        records = _read_jsonl(files[0])
        assert len(records) == 1

        schema = _load_schema(_TELEMETRY_SCHEMA_PATH)
        errors = list(Draft202012Validator(schema).iter_errors(records[0]))
        assert not errors, f"emit record rejected: {[e.message for e in errors]}"

    def test_emit_many_records_all_validate(self, telemetry_root: Path) -> None:
        _telemetry.emit_many(
            "stamp-write",
            [
                {"gate": "code", "steps": ["ruff-check", "pytest"]},
                {"gate": "agent", "steps": ["agent-arch-doc-reviewer"]},
                {"gate": "frontend", "steps": ["eslint", "tsc-strict", "vitest"]},
            ],
        )

        files = list(telemetry_root.glob("*.jsonl"))
        records = _read_jsonl(files[0])
        assert len(records) == 3

        schema = _load_schema(_TELEMETRY_SCHEMA_PATH)
        for record in records:
            errors = list(Draft202012Validator(schema).iter_errors(record))
            assert not errors, f"emit_many record rejected: {[e.message for e in errors]}"

    def test_data_can_be_arbitrary_object(self, telemetry_root: Path) -> None:
        _telemetry.emit(
            "subagent-start",
            {
                "agent": "py-solid-dry-reviewer",
                "max_turns": 20,
                "nested": {"effort": "high", "model": "opus"},
                "list_field": [1, 2, 3],
            },
        )
        files = list(telemetry_root.glob("*.jsonl"))
        records = _read_jsonl(files[0])

        schema = _load_schema(_TELEMETRY_SCHEMA_PATH)
        errors = list(Draft202012Validator(schema).iter_errors(records[0]))
        assert not errors


class TestNegativeExamples:
    """Schemas reject malformed records."""

    def test_incident_rejects_invalid_ulid(self) -> None:
        schema = _load_schema(_INCIDENT_SCHEMA_PATH)
        bad = {
            "ulid": "TOO-SHORT",
            "timestamp": "2026-05-04T22:20:10Z",
            "category": "stop-failure",
            "severity": "error",
            "detail": "x",
            "extra": {},
        }
        errors = list(Draft202012Validator(schema).iter_errors(bad))
        assert errors

    def test_incident_rejects_invalid_severity(self) -> None:
        schema = _load_schema(_INCIDENT_SCHEMA_PATH)
        bad = {
            "ulid": "01HKQRSTVWXYZ0123456789ABC",
            "timestamp": "2026-05-04T22:20:10Z",
            "severity": "critical",
            "detail": "x",
            "extra": {},
        }
        errors = list(Draft202012Validator(schema).iter_errors(bad))
        assert errors

    def test_incident_rejects_empty_detail(self) -> None:
        schema = _load_schema(_INCIDENT_SCHEMA_PATH)
        bad = {
            "ulid": "01HKQRSTVWXYZ0123456789ABC",
            "timestamp": "2026-05-04T22:20:10Z",
            "severity": "error",
            "detail": "",
            "extra": {},
        }
        errors = list(Draft202012Validator(schema).iter_errors(bad))
        assert errors

    def test_telemetry_rejects_missing_data(self) -> None:
        schema = _load_schema(_TELEMETRY_SCHEMA_PATH)
        bad = {
            "timestamp": "2026-05-04T22:20:10Z",
            "category": "hook-failure",
        }
        errors = list(Draft202012Validator(schema).iter_errors(bad))
        assert errors

    def test_telemetry_rejects_uppercase_category(self) -> None:
        schema = _load_schema(_TELEMETRY_SCHEMA_PATH)
        bad = {
            "timestamp": "2026-05-04T22:20:10Z",
            "category": "Hook-Failure",
            "data": {},
        }
        errors = list(Draft202012Validator(schema).iter_errors(bad))
        assert errors

    def test_telemetry_rejects_malformed_timestamp(self) -> None:
        schema = _load_schema(_TELEMETRY_SCHEMA_PATH)
        bad = {
            "timestamp": "yesterday",
            "category": "hook-failure",
            "data": {},
        }
        errors = list(Draft202012Validator(schema).iter_errors(bad))
        assert errors
