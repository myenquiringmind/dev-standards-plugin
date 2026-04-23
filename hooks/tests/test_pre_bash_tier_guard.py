"""Tests for hooks/pre_bash_tier_guard.py."""

from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from hooks import pre_bash_tier_guard as guard


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
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(root))


def _bash_payload(agent_type: str, command: str) -> dict[str, Any]:
    return {
        "tool_name": "Bash",
        "agent_type": agent_type,
        "tool_input": {"command": command},
    }


# ---------------------------------------------------------------------------
# Block path: read/reason tier with non-allowlisted commands
# ---------------------------------------------------------------------------


class TestBlocksMutatingCommands:
    @pytest.mark.parametrize(
        ("command", "needle"),
        [
            ("rm -rf /tmp/x", "rm"),
            ("mv a b", "mv"),
            ("cp a b", "cp"),
            ("touch foo", "touch"),
            ("mkdir foo", "mkdir"),
            ("curl https://example.com", "curl"),
            ("wget https://example.com", "wget"),
            ("npm install", "npm"),
            ("uv add requests", "uv"),
            ("python -c 'print(1)'", "python"),
        ],
    )
    def test_read_tier_blocks_mutator(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        command: str,
        needle: str,
    ) -> None:
        _write_registry(tmp_dir, [_agent_node("scanner", "read")])
        _patch(monkeypatch, tmp_dir, payload=_bash_payload("scanner", command))

        rc = guard.main()

        err = capsys.readouterr().err
        assert rc == 2
        assert "refusing" in err
        assert "scanner" in err
        assert "read" in err
        assert needle in err

    def test_reason_tier_blocks(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write_registry(tmp_dir, [_agent_node("planner", "reason")])
        _patch(monkeypatch, tmp_dir, payload=_bash_payload("planner", "rm -rf foo"))

        assert guard.main() == 2
        assert "reason" in capsys.readouterr().err


class TestBlocksMutatingGitVerbs:
    @pytest.mark.parametrize(
        ("command", "needle"),
        [
            ("git push origin master", "git push"),
            ("git commit -m 'x'", "git commit"),
            ("git checkout -b feat/x", "git checkout"),
            ("git reset --hard HEAD", "git reset"),
            ("git rebase main", "git rebase"),
            ("git merge feat/x", "git merge"),
            ("git add .", "git add"),
            ("git rm foo", "git rm"),
            ("git pull", "git pull"),
            ("git fetch", "git fetch"),
        ],
    )
    def test_git_write_verb_blocks(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        command: str,
        needle: str,
    ) -> None:
        _write_registry(tmp_dir, [_agent_node("scanner", "read")])
        _patch(monkeypatch, tmp_dir, payload=_bash_payload("scanner", command))

        assert guard.main() == 2
        assert needle in capsys.readouterr().err


class TestBlocksCompoundCommands:
    def test_allowed_then_mutator_blocks(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # The first segment is fine; the second is not.
        _write_registry(tmp_dir, [_agent_node("scanner", "read")])
        _patch(
            monkeypatch,
            tmp_dir,
            payload=_bash_payload("scanner", "git status && rm -rf /tmp/x"),
        )

        assert guard.main() == 2
        assert "rm" in capsys.readouterr().err

    @pytest.mark.parametrize("operator", ["&&", "||", ";", "|", "&"])
    def test_each_operator_separates_segments(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch, operator: str
    ) -> None:
        _write_registry(tmp_dir, [_agent_node("scanner", "read")])
        _patch(
            monkeypatch,
            tmp_dir,
            payload=_bash_payload("scanner", f"ls {operator} rm foo"),
        )
        assert guard.main() == 2

    def test_unbalanced_quotes_blocks(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # shlex cannot parse — block defensively.
        _write_registry(tmp_dir, [_agent_node("scanner", "read")])
        _patch(
            monkeypatch,
            tmp_dir,
            payload=_bash_payload("scanner", "echo 'unterminated"),
        )
        assert guard.main() == 2
        assert "refusing" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Pass path: allowlisted commands
# ---------------------------------------------------------------------------


class TestPassesAllowlistedCommands:
    @pytest.mark.parametrize(
        "command",
        [
            "ls -la",
            "pwd",
            "cat README.md",
            "head -n 20 file.txt",
            "tail -f log.txt",
            "wc -l *.py",
            "grep -r 'foo' .",
            "rg --type py 'import'",
            "find . -name '*.py'",
            "jq '.nodes[]' config/graph-registry.json",
            "echo hello",
            "which python",
            "env",
        ],
    )
    def test_read_tool_passes(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch, command: str
    ) -> None:
        _write_registry(tmp_dir, [_agent_node("scanner", "read")])
        _patch(monkeypatch, tmp_dir, payload=_bash_payload("scanner", command))
        assert guard.main() == 0

    @pytest.mark.parametrize(
        "command",
        [
            "git status",
            "git status -s --porcelain",
            "git log --oneline -10",
            "git diff master...HEAD",
            "git show HEAD",
            "git branch -a",
            "git rev-parse HEAD",
            "git config --list",
            "git",  # bare git prints help
        ],
    )
    def test_git_read_verb_passes(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch, command: str
    ) -> None:
        _write_registry(tmp_dir, [_agent_node("scanner", "read")])
        _patch(monkeypatch, tmp_dir, payload=_bash_payload("scanner", command))
        assert guard.main() == 0

    def test_compound_all_allowlisted_passes(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_registry(tmp_dir, [_agent_node("scanner", "read")])
        _patch(
            monkeypatch,
            tmp_dir,
            payload=_bash_payload("scanner", "git status && git log --oneline | head -5"),
        )
        assert guard.main() == 0

    def test_path_qualified_program_passes(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # /usr/bin/git status is git status.
        _write_registry(tmp_dir, [_agent_node("scanner", "read")])
        _patch(monkeypatch, tmp_dir, payload=_bash_payload("scanner", "/usr/bin/git status"))
        assert guard.main() == 0


# ---------------------------------------------------------------------------
# Fail-open paths
# ---------------------------------------------------------------------------


class TestWriteTierUntouched:
    @pytest.mark.parametrize("tier", ["write", "read-reason-write"])
    def test_write_tier_runs_anything(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch, tier: str
    ) -> None:
        _write_registry(tmp_dir, [_agent_node("scaffolder", tier)])
        _patch(
            monkeypatch,
            tmp_dir,
            payload=_bash_payload("scaffolder", "rm -rf foo && git push --force"),
        )
        assert guard.main() == 0


class TestNonBashTools:
    @pytest.mark.parametrize("tool", ["Edit", "Write", "Read", "Glob", "Grep"])
    def test_non_bash_tools_pass(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch, tool: str
    ) -> None:
        # Defensive: hook should be matched only on Bash, but if invoked
        # on another tool it must not block.
        _write_registry(tmp_dir, [_agent_node("scanner", "read")])
        _patch(
            monkeypatch,
            tmp_dir,
            payload={"tool_name": tool, "agent_type": "scanner", "tool_input": {}},
        )
        assert guard.main() == 0


class TestMainThreadCalls:
    def test_no_agent_type_passes(self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_registry(tmp_dir, [_agent_node("scanner", "read")])
        _patch(
            monkeypatch,
            tmp_dir,
            payload={"tool_name": "Bash", "tool_input": {"command": "rm -rf foo"}},
        )
        assert guard.main() == 0

    def test_empty_agent_type_passes(self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_registry(tmp_dir, [_agent_node("scanner", "read")])
        _patch(
            monkeypatch,
            tmp_dir,
            payload={
                "tool_name": "Bash",
                "agent_type": "",
                "tool_input": {"command": "rm -rf foo"},
            },
        )
        assert guard.main() == 0


class TestUnknownAgent:
    def test_unknown_agent_passes(self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_registry(tmp_dir, [_agent_node("known", "read")])
        _patch(
            monkeypatch,
            tmp_dir,
            payload=_bash_payload("unknown-agent", "rm -rf foo"),
        )
        assert guard.main() == 0


class TestMissingRegistry:
    def test_missing_registry_fails_open(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # No config/graph-registry.json at all.
        _patch(
            monkeypatch,
            tmp_dir,
            payload=_bash_payload("scanner", "rm -rf foo"),
        )
        assert guard.main() == 0


class TestTierMissing:
    def test_node_without_tier_passes(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        node: dict[str, Any] = {
            "id": "legacy",
            "type": "Agent",
            "category": "meta",
            "metadata": {
                "agent_type": "blocking",
                "model": "opus",
                "tools": ["Read", "Bash"],
                "memory": "none",
                "maxTurns": 10,
                # tier deliberately absent
            },
        }
        _write_registry(tmp_dir, [node])
        _patch(monkeypatch, tmp_dir, payload=_bash_payload("legacy", "rm -rf foo"))
        assert guard.main() == 0


class TestEmptyOrMissingCommand:
    def test_empty_command_passes(self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_registry(tmp_dir, [_agent_node("scanner", "read")])
        _patch(
            monkeypatch,
            tmp_dir,
            payload={
                "tool_name": "Bash",
                "agent_type": "scanner",
                "tool_input": {"command": "   "},
            },
        )
        assert guard.main() == 0

    def test_missing_tool_input_passes(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_registry(tmp_dir, [_agent_node("scanner", "read")])
        _patch(
            monkeypatch,
            tmp_dir,
            payload={"tool_name": "Bash", "agent_type": "scanner"},
        )
        assert guard.main() == 0


class TestEmptyInput:
    def test_empty_stdin_exits_zero(self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_dir))
        monkeypatch.setattr(sys, "stdin", StringIO(""))
        assert guard.main() == 0
