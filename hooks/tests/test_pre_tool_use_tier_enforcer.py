"""Tests for hooks/pre_tool_use_tier_enforcer.py."""

from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from hooks import pre_tool_use_tier_enforcer as enforcer


def _write_registry(root: Path, nodes: list[dict[str, Any]]) -> None:
    (root / "config").mkdir(parents=True, exist_ok=True)
    registry = {
        "version": "1.0.0",
        "generated_at": "2026-04-23T00:00:00Z",
        "nodes": nodes,
        "edges": [],
    }
    (root / "config" / "graph-registry.json").write_text(json.dumps(registry), encoding="utf-8")


def _agent_node(agent_id: str, tier: str) -> dict[str, Any]:
    return {
        "id": agent_id,
        "type": "Agent",
        "category": "meta",
        "metadata": {
            "agent_type": "blocking",
            "model": "opus",
            "tools": ["Read", "Bash"],
            "memory": "none",
            "maxTurns": 10,
            "tier": tier,
        },
    }


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    root: Path,
    *,
    payload: dict[str, Any],
) -> None:
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(payload)))
    # _graph.load_registry reads from get_project_dir() -> config/graph-registry.json
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(root))


class TestMutatingToolsFromReadTier:
    @pytest.mark.parametrize("tool", ["Edit", "Write", "MultiEdit", "NotebookEdit"])
    def test_read_tier_blocks(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        tool: str,
    ) -> None:
        _write_registry(tmp_dir, [_agent_node("scanner", "read")])
        _patch(
            monkeypatch,
            tmp_dir,
            payload={
                "tool_name": tool,
                "agent_type": "scanner",
                "tool_input": {"file_path": "/tmp/x"},
            },
        )

        rc = enforcer.main()

        err = capsys.readouterr().err
        assert rc == 2
        assert "refusing" in err
        assert tool in err
        assert "scanner" in err
        assert "read" in err

    def test_reason_tier_blocks(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write_registry(tmp_dir, [_agent_node("planner", "reason")])
        _patch(
            monkeypatch,
            tmp_dir,
            payload={
                "tool_name": "Edit",
                "agent_type": "planner",
                "tool_input": {"file_path": "/tmp/x"},
            },
        )

        rc = enforcer.main()
        assert rc == 2
        assert "reason" in capsys.readouterr().err


class TestMutatingToolsFromWriteTier:
    @pytest.mark.parametrize("tier", ["write", "read-reason-write"])
    def test_write_tier_passes(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch, tier: str
    ) -> None:
        _write_registry(tmp_dir, [_agent_node("scaffolder", tier)])
        _patch(
            monkeypatch,
            tmp_dir,
            payload={
                "tool_name": "Write",
                "agent_type": "scaffolder",
                "tool_input": {"file_path": "/tmp/x"},
            },
        )

        assert enforcer.main() == 0


class TestNonMutatingTools:
    @pytest.mark.parametrize("tool", ["Read", "Glob", "Grep", "Bash", "Task"])
    def test_read_only_tools_always_pass(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch, tool: str
    ) -> None:
        _write_registry(tmp_dir, [_agent_node("scanner", "read")])
        _patch(
            monkeypatch,
            tmp_dir,
            payload={"tool_name": tool, "agent_type": "scanner"},
        )
        assert enforcer.main() == 0


class TestMainThreadCalls:
    def test_no_agent_type_passes(self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Main-thread Edit call — agent_type absent. Must not block.
        _write_registry(tmp_dir, [_agent_node("scanner", "read")])
        _patch(
            monkeypatch,
            tmp_dir,
            payload={"tool_name": "Edit", "tool_input": {"file_path": "/tmp/x"}},
        )
        assert enforcer.main() == 0

    def test_empty_agent_type_passes(self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_registry(tmp_dir, [_agent_node("scanner", "read")])
        _patch(
            monkeypatch,
            tmp_dir,
            payload={"tool_name": "Edit", "agent_type": "", "tool_input": {}},
        )
        assert enforcer.main() == 0


class TestUnknownAgent:
    def test_unknown_agent_passes(self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Registry doesn't contain the caller — fail-open.
        _write_registry(tmp_dir, [_agent_node("known", "read")])
        _patch(
            monkeypatch,
            tmp_dir,
            payload={
                "tool_name": "Edit",
                "agent_type": "unknown-agent",
                "tool_input": {"file_path": "/tmp/x"},
            },
        )
        assert enforcer.main() == 0


class TestMissingRegistry:
    def test_missing_registry_fails_open(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # No config/graph-registry.json at all.
        _patch(
            monkeypatch,
            tmp_dir,
            payload={
                "tool_name": "Edit",
                "agent_type": "scanner",
                "tool_input": {"file_path": "/tmp/x"},
            },
        )
        assert enforcer.main() == 0


class TestTierMissing:
    def test_node_without_tier_passes(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Registry built before the tier-propagation change — metadata has no tier.
        node: dict[str, Any] = {
            "id": "legacy",
            "type": "Agent",
            "category": "meta",
            "metadata": {
                "agent_type": "blocking",
                "model": "opus",
                "tools": ["Read"],
                "memory": "none",
                "maxTurns": 10,
                # tier deliberately absent
            },
        }
        _write_registry(tmp_dir, [node])
        _patch(
            monkeypatch,
            tmp_dir,
            payload={
                "tool_name": "Edit",
                "agent_type": "legacy",
                "tool_input": {"file_path": "/tmp/x"},
            },
        )
        # Without a tier, we cannot enforce — fail-open.
        assert enforcer.main() == 0


class TestEmptyInput:
    def test_empty_stdin_exits_zero(self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_dir))
        monkeypatch.setattr(sys, "stdin", StringIO(""))
        assert enforcer.main() == 0
