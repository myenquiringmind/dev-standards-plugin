"""Tests for hooks/pre_commit_cli_gate.py."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from io import StringIO
from pathlib import Path

import pytest

from hooks import pre_commit_cli_gate
from hooks._hook_shared import (
    AGENT_VALIDATION_STEPS,
    PY_VALIDATION_STEPS,
    STAMP_TTL,
)

SCHEMA_SOURCE = Path(__file__).resolve().parent.parent.parent / "schemas" / "stamp.schema.json"


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    *,
    command: str,
    project_dir: Path,
    branch: str,
    staged: list[str],
    tool_name: str = "Bash",
) -> None:
    payload = {"tool_name": tool_name, "tool_input": {"command": command}}
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(payload)))
    monkeypatch.setattr(pre_commit_cli_gate, "get_project_dir", lambda: project_dir)
    monkeypatch.setattr(pre_commit_cli_gate, "get_current_branch", lambda _d=None: branch)
    monkeypatch.setattr(pre_commit_cli_gate, "_staged_files", lambda _d: list(staged))


def _write_schema(project_dir: Path) -> None:
    schemas = project_dir / "schemas"
    schemas.mkdir(parents=True, exist_ok=True)
    (schemas / "stamp.schema.json").write_text(
        SCHEMA_SOURCE.read_text(encoding="utf-8"),
        encoding="utf-8",
    )


def _write_stamp(
    project_dir: Path,
    *,
    gate: str,
    branch: str,
    steps: list[str] | None = None,
    age_seconds: int = 0,
    extra: dict[str, object] | None = None,
) -> Path:
    filename = pre_commit_cli_gate._STAMP_FILENAMES[gate]
    default_steps = {
        "code": list(PY_VALIDATION_STEPS),
        "frontend": ["eslint"],
        "agent": list(AGENT_VALIDATION_STEPS),
        "db": ["db-schema-reviewer"],
        "api": ["api-contract-reviewer"],
    }[gate]
    now = datetime.now(UTC) - timedelta(seconds=age_seconds)
    stamp: dict[str, object] = {
        "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "branch": branch,
        "steps": steps if steps is not None else default_steps,
        "ttl_seconds": STAMP_TTL,
        "version": "1.0.0",
        "gate": gate,
    }
    if extra:
        stamp.update(extra)
    path = project_dir / filename
    path.write_text(json.dumps(stamp, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


class TestNonCommitBash:
    def test_non_bash_tool_ignored(self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch(
            monkeypatch,
            command="git commit -m 'foo'",
            project_dir=tmp_dir,
            branch="feat/x",
            staged=["foo.py"],
            tool_name="Edit",
        )
        assert pre_commit_cli_gate.main() == 0

    @pytest.mark.parametrize(
        "command",
        [
            "echo hello",
            "git status",
            "git commit-tree -m foo",
            "grep commit README.md",
            "git log",
            "ls -la",
        ],
    )
    def test_non_commit_command_ignored(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        command: str,
    ) -> None:
        _patch(
            monkeypatch,
            command=command,
            project_dir=tmp_dir,
            branch="feat/x",
            staged=["foo.py"],
        )
        assert pre_commit_cli_gate.main() == 0


class TestHappyPath:
    def test_valid_code_stamp_allows_commit(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_schema(tmp_dir)
        _write_stamp(tmp_dir, gate="code", branch="feat/x")
        _patch(
            monkeypatch,
            command="git commit -m 'real work'",
            project_dir=tmp_dir,
            branch="feat/x",
            staged=["hooks/foo.py"],
        )
        assert pre_commit_cli_gate.main() == 0

    def test_valid_multi_gate(self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_schema(tmp_dir)
        _write_stamp(tmp_dir, gate="code", branch="feat/x")
        _write_stamp(tmp_dir, gate="agent", branch="feat/x")
        _patch(
            monkeypatch,
            command="git commit -m 'real work'",
            project_dir=tmp_dir,
            branch="feat/x",
            staged=["hooks/foo.py", "agents/meta/new-agent.md"],
        )
        assert pre_commit_cli_gate.main() == 0

    def test_no_staged_files_allows_commit(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch(
            monkeypatch,
            command="git commit -m 'empty'",
            project_dir=tmp_dir,
            branch="feat/x",
            staged=[],
        )
        assert pre_commit_cli_gate.main() == 0

    def test_docs_only_staged_allows_commit(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch(
            monkeypatch,
            command="git commit -m 'docs'",
            project_dir=tmp_dir,
            branch="feat/x",
            staged=["docs/foo.md", "README.md"],
        )
        assert pre_commit_cli_gate.main() == 0


class TestMissingStamp:
    def test_commit_without_stamp_blocks(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _write_schema(tmp_dir)
        _patch(
            monkeypatch,
            command="git commit -m 'work'",
            project_dir=tmp_dir,
            branch="feat/x",
            staged=["hooks/foo.py"],
        )
        rc = pre_commit_cli_gate.main()
        err = capsys.readouterr().err
        assert rc == 2
        assert "no stamp" in err
        assert "code" in err

    def test_commit_with_partial_multi_gate_stamp_blocks(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _write_schema(tmp_dir)
        _write_stamp(tmp_dir, gate="code", branch="feat/x")
        # Agent staged but no agent stamp.
        _patch(
            monkeypatch,
            command="git commit -m 'work'",
            project_dir=tmp_dir,
            branch="feat/x",
            staged=["hooks/foo.py", "agents/meta/a.md"],
        )
        rc = pre_commit_cli_gate.main()
        err = capsys.readouterr().err
        assert rc == 2
        assert "agent" in err


class TestStaleStamp:
    def test_stamp_older_than_ttl_blocks(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _write_schema(tmp_dir)
        _write_stamp(tmp_dir, gate="code", branch="feat/x", age_seconds=STAMP_TTL + 60)
        _patch(
            monkeypatch,
            command="git commit -m 'work'",
            project_dir=tmp_dir,
            branch="feat/x",
            staged=["hooks/foo.py"],
        )
        rc = pre_commit_cli_gate.main()
        err = capsys.readouterr().err
        assert rc == 2
        assert "stale" in err


class TestWipBypass:
    @pytest.mark.parametrize(
        "command",
        [
            "git commit -m '[WIP] partial'",
            'git commit -m "[WIP] partial"',
            "git commit --message='[WIP] checkpoint'",
        ],
    )
    def test_wip_marker_bypasses_gate(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        command: str,
    ) -> None:
        # Deliberately no stamp written — bypass should still allow.
        _patch(
            monkeypatch,
            command=command,
            project_dir=tmp_dir,
            branch="feat/x",
            staged=["hooks/foo.py"],
        )
        assert pre_commit_cli_gate.main() == 0


class TestMergeHeadBypass:
    def test_merge_head_bypasses_gate(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        git_dir = tmp_dir / ".git"
        git_dir.mkdir()
        (git_dir / "MERGE_HEAD").write_text("abcdef\n", encoding="utf-8")
        _patch(
            monkeypatch,
            command="git commit -m 'resolve merge'",
            project_dir=tmp_dir,
            branch="feat/x",
            staged=["hooks/foo.py"],
        )
        assert pre_commit_cli_gate.main() == 0


class TestBranchMismatch:
    def test_stamp_for_wrong_branch_blocks(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _write_schema(tmp_dir)
        _write_stamp(tmp_dir, gate="code", branch="feat/old")
        _patch(
            monkeypatch,
            command="git commit -m 'work'",
            project_dir=tmp_dir,
            branch="feat/new",
            staged=["hooks/foo.py"],
        )
        rc = pre_commit_cli_gate.main()
        err = capsys.readouterr().err
        assert rc == 2
        assert "feat/old" in err
        assert "feat/new" in err


class TestCanonicalSteps:
    def test_missing_canonical_step_blocks(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _write_schema(tmp_dir)
        # Missing several canonical steps.
        _write_stamp(
            tmp_dir,
            gate="code",
            branch="feat/x",
            steps=["ruff-check", "pytest"],
        )
        _patch(
            monkeypatch,
            command="git commit -m 'work'",
            project_dir=tmp_dir,
            branch="feat/x",
            staged=["hooks/foo.py"],
        )
        rc = pre_commit_cli_gate.main()
        err = capsys.readouterr().err
        assert rc == 2
        assert "canonical steps" in err


class TestCorruptStamp:
    def test_invalid_json_blocks(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _write_schema(tmp_dir)
        (tmp_dir / ".validation_stamp").write_text("{not json", encoding="utf-8")
        _patch(
            monkeypatch,
            command="git commit -m 'work'",
            project_dir=tmp_dir,
            branch="feat/x",
            staged=["hooks/foo.py"],
        )
        rc = pre_commit_cli_gate.main()
        err = capsys.readouterr().err
        assert rc == 2
        assert "unreadable" in err

    def test_schema_violation_blocks(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _write_schema(tmp_dir)
        # ttl_seconds deviates from the const 900 — schema rejects.
        _write_stamp(
            tmp_dir,
            gate="code",
            branch="feat/x",
            extra={"ttl_seconds": 60},
        )
        _patch(
            monkeypatch,
            command="git commit -m 'work'",
            project_dir=tmp_dir,
            branch="feat/x",
            staged=["hooks/foo.py"],
        )
        rc = pre_commit_cli_gate.main()
        err = capsys.readouterr().err
        assert rc == 2
        assert "schema" in err


class TestMissingSchema:
    def test_missing_schema_blocks(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # No schema file written.
        _patch(
            monkeypatch,
            command="git commit -m 'work'",
            project_dir=tmp_dir,
            branch="feat/x",
            staged=["hooks/foo.py"],
        )
        rc = pre_commit_cli_gate.main()
        err = capsys.readouterr().err
        assert rc == 2
        assert "schema" in err


class TestBranchResolution:
    def test_empty_branch_blocks(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _write_schema(tmp_dir)
        _patch(
            monkeypatch,
            command="git commit -m 'work'",
            project_dir=tmp_dir,
            branch="",
            staged=["hooks/foo.py"],
        )
        rc = pre_commit_cli_gate.main()
        err = capsys.readouterr().err
        assert rc == 2
        assert "branch" in err


class TestGatePatternDetection:
    @pytest.mark.parametrize(
        "staged,expected",
        [
            (["foo.py"], {"code"}),
            (["src/app.ts"], {"frontend"}),
            (["src/app.tsx", "src/style.css"], {"frontend"}),
            (["agents/meta/foo.md"], {"agent"}),
            (["db/migrations/0001_init.sql"], {"db"}),
            (["api/openapi.yaml"], {"api"}),
            (["openapi.yaml"], {"api"}),
            (["hooks/foo.py", "agents/x/bar.md"], {"code", "agent"}),
            (["README.md", "docs/foo.md"], set()),
            (["hooks/foo.md"], set()),
        ],
    )
    def test_pattern_mapping(
        self,
        staged: list[str],
        expected: set[str],
    ) -> None:
        assert pre_commit_cli_gate._required_gates(staged) == expected


class TestCommitDetection:
    @pytest.mark.parametrize(
        "command,should_match",
        [
            ("git commit", True),
            ("git commit -m 'foo'", True),
            ("git commit -am 'foo'", True),
            ("git -c user.name=x commit -m 'foo'", True),
            ("git commit --amend", True),
            ("cd /tmp && git commit -m 'foo'", True),
            ("git commit-tree ...", False),
            ("git log", False),
            ("echo 'git commit'", True),
            ("git status", False),
        ],
    )
    def test_regex(self, command: str, should_match: bool) -> None:
        assert pre_commit_cli_gate._is_git_commit(command) is should_match
