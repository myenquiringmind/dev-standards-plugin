"""Tests for hooks/branch_protection.py."""

from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path

import pytest

from hooks import branch_protection


def _patch_io(
    monkeypatch: pytest.MonkeyPatch,
    stdin_payload: dict[str, object],
    branch: str,
    project_dir: Path,
) -> None:
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(stdin_payload)))
    monkeypatch.setattr(branch_protection, "get_project_dir", lambda: project_dir)
    monkeypatch.setattr(branch_protection, "get_current_branch", lambda _d: branch)


class TestProtectedBranches:
    @pytest.mark.parametrize(
        "branch", ["master", "main", "production", "develop", "staging", "release"]
    )
    @pytest.mark.parametrize("tool", ["Edit", "Write", "MultiEdit"])
    def test_blocks_on_any_protected_branch(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        branch: str,
        tool: str,
    ) -> None:
        _patch_io(monkeypatch, {"tool_name": tool}, branch, tmp_dir)

        rc = branch_protection.main()
        captured = capsys.readouterr()

        assert rc == 2
        assert f"refusing {tool}" in captured.err
        assert branch in captured.err
        assert "git checkout -b" in captured.err


class TestFeatureBranches:
    @pytest.mark.parametrize(
        "branch", ["feat/new-widget", "fix/bug-123", "docs/readme", "wip/experiment"]
    )
    def test_allows_edits_on_non_protected(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        branch: str,
    ) -> None:
        _patch_io(monkeypatch, {"tool_name": "Edit"}, branch, tmp_dir)
        assert branch_protection.main() == 0


class TestNonEditTool:
    def test_ignores_non_edit_tools_even_on_protected_branch(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _patch_io(monkeypatch, {"tool_name": "Read"}, "master", tmp_dir)
        assert branch_protection.main() == 0

    def test_missing_tool_name_is_ignored(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _patch_io(monkeypatch, {}, "master", tmp_dir)
        assert branch_protection.main() == 0


class TestEmptyBranch:
    def test_empty_branch_does_not_block(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _patch_io(monkeypatch, {"tool_name": "Edit"}, "", tmp_dir)
        assert branch_protection.main() == 0

    def test_detached_head_hash_does_not_block(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _patch_io(monkeypatch, {"tool_name": "Edit"}, "abc123def456", tmp_dir)
        assert branch_protection.main() == 0
