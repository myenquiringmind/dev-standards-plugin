"""Tests for hooks/subagent_start.py."""

from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from hooks import subagent_start


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    project_dir: Path,
    telemetry_dir: Path,
    payload: dict[str, Any] | None = None,
) -> None:
    body = json.dumps(payload) if payload is not None else ""
    monkeypatch.setattr(sys, "stdin", StringIO(body))
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project_dir))
    monkeypatch.setenv("CLAUDE_TELEMETRY_DIR", str(telemetry_dir))


def _seed_registry(project_dir: Path, nodes: list[dict[str, Any]]) -> None:
    config_dir = project_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "1.0.0",
        "generated_at": "2026-04-30T00:00:00Z",
        "nodes": nodes,
        "edges": [],
    }
    (config_dir / "graph-registry.json").write_text(json.dumps(payload), encoding="utf-8")


def _agent_node(
    agent_id: str,
    *,
    max_turns: int = 10,
    tier: str = "reason",
) -> dict[str, Any]:
    return {
        "id": agent_id,
        "type": "Agent",
        "category": "meta",
        "metadata": {
            "agent_type": "blocking",
            "model": "opus",
            "tools": ["Read", "Bash"],
            "memory": "none",
            "maxTurns": max_turns,
            "tier": tier,
        },
    }


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
# Happy path — telemetry includes registry-declared maxTurns
# ---------------------------------------------------------------------------


class TestRegistryLookup:
    def test_max_turns_pulled_from_registry(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path_factory: pytest.TempPathFactory,
    ) -> None:
        _seed_registry(tmp_dir, [_agent_node("planner", max_turns=20)])
        telemetry = tmp_path_factory.mktemp("telemetry")
        _patch(
            monkeypatch,
            tmp_dir,
            telemetry,
            {
                "agent_type": "planner",
                "session_id": "sess-1",
                "transcript_path": "/tmp/t.jsonl",
            },
        )

        assert subagent_start.main() == 0
        rec = _read_telemetry(telemetry)[0]
        assert rec["category"] == "subagent-start"
        data = rec["data"]
        assert data["agent"] == "planner"
        assert data["max_turns"] == 20
        assert data["session_id"] == "sess-1"
        assert data["transcript_path"] == "/tmp/t.jsonl"

    @pytest.mark.parametrize("key", ["agent_type", "agent_name", "subagent_type", "name"])
    def test_agent_recognised_under_each_key(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path_factory: pytest.TempPathFactory,
        key: str,
    ) -> None:
        _seed_registry(tmp_dir, [_agent_node("planner", max_turns=15)])
        telemetry = tmp_path_factory.mktemp("telemetry")
        _patch(monkeypatch, tmp_dir, telemetry, {key: "planner"})

        subagent_start.main()
        rec = _read_telemetry(telemetry)[0]
        assert rec["data"]["agent"] == "planner"
        assert rec["data"]["max_turns"] == 15


# ---------------------------------------------------------------------------
# Defensive lookup — missing / malformed registry, missing agent
# ---------------------------------------------------------------------------


class TestDefensiveLookup:
    def test_missing_registry_records_null_max_turns(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path_factory: pytest.TempPathFactory,
    ) -> None:
        # No registry file at all.
        telemetry = tmp_path_factory.mktemp("telemetry")
        _patch(monkeypatch, tmp_dir, telemetry, {"agent_type": "planner"})

        subagent_start.main()
        rec = _read_telemetry(telemetry)[0]
        assert rec["data"]["max_turns"] is None
        # Agent name is still recorded.
        assert rec["data"]["agent"] == "planner"

    def test_agent_not_in_registry_records_null(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path_factory: pytest.TempPathFactory,
    ) -> None:
        _seed_registry(tmp_dir, [_agent_node("other-agent")])
        telemetry = tmp_path_factory.mktemp("telemetry")
        _patch(monkeypatch, tmp_dir, telemetry, {"agent_type": "missing"})

        subagent_start.main()
        rec = _read_telemetry(telemetry)[0]
        assert rec["data"]["max_turns"] is None

    def test_metadata_missing_max_turns_records_null(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path_factory: pytest.TempPathFactory,
    ) -> None:
        # Node exists but metadata.maxTurns is absent.
        _seed_registry(
            tmp_dir,
            [
                {
                    "id": "minimal",
                    "type": "Agent",
                    "category": "meta",
                    "metadata": {
                        "agent_type": "blocking",
                        "model": "opus",
                        "tools": ["Read"],
                        "memory": "none",
                        "tier": "reason",
                    },
                }
            ],
        )
        telemetry = tmp_path_factory.mktemp("telemetry")
        _patch(monkeypatch, tmp_dir, telemetry, {"agent_type": "minimal"})

        subagent_start.main()
        rec = _read_telemetry(telemetry)[0]
        assert rec["data"]["max_turns"] is None

    def test_boolean_max_turns_rejected(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path_factory: pytest.TempPathFactory,
    ) -> None:
        # ``isinstance(True, int)`` is True — guard against that.
        node = _agent_node("planner")
        node["metadata"]["maxTurns"] = True
        _seed_registry(tmp_dir, [node])
        telemetry = tmp_path_factory.mktemp("telemetry")
        _patch(monkeypatch, tmp_dir, telemetry, {"agent_type": "planner"})

        subagent_start.main()
        rec = _read_telemetry(telemetry)[0]
        assert rec["data"]["max_turns"] is None


# ---------------------------------------------------------------------------
# Always emits — even with no usable payload
# ---------------------------------------------------------------------------


class TestAlwaysEmits:
    def test_empty_payload_still_emits(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path_factory: pytest.TempPathFactory,
    ) -> None:
        telemetry = tmp_path_factory.mktemp("telemetry")
        _patch(monkeypatch, tmp_dir, telemetry, {})

        assert subagent_start.main() == 0
        rec = _read_telemetry(telemetry)[0]
        assert rec["category"] == "subagent-start"
        assert rec["data"]["agent"] == ""
        assert rec["data"]["max_turns"] is None

    def test_empty_stdin_still_emits(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path_factory: pytest.TempPathFactory,
    ) -> None:
        telemetry = tmp_path_factory.mktemp("telemetry")
        monkeypatch.setattr(sys, "stdin", StringIO(""))
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_dir))
        monkeypatch.setenv("CLAUDE_TELEMETRY_DIR", str(telemetry))

        assert subagent_start.main() == 0
        rec = _read_telemetry(telemetry)[0]
        assert rec["category"] == "subagent-start"

    def test_session_and_transcript_default_to_empty_string(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path_factory: pytest.TempPathFactory,
    ) -> None:
        _seed_registry(tmp_dir, [_agent_node("planner")])
        telemetry = tmp_path_factory.mktemp("telemetry")
        _patch(monkeypatch, tmp_dir, telemetry, {"agent_type": "planner"})

        subagent_start.main()
        rec = _read_telemetry(telemetry)[0]
        assert rec["data"]["session_id"] == ""
        assert rec["data"]["transcript_path"] == ""
