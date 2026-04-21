"""Tests for hooks/pre_commit_secret_scan.py."""

from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path

import pytest

from hooks import pre_commit_secret_scan


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    *,
    command: str,
    project_dir: Path,
    diff: str | None,
    tool_name: str = "Bash",
) -> None:
    payload = {"tool_name": tool_name, "tool_input": {"command": command}}
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(payload)))
    monkeypatch.setattr(pre_commit_secret_scan, "get_project_dir", lambda: project_dir)
    monkeypatch.setattr(pre_commit_secret_scan, "_staged_diff", lambda _d: diff)


def _clean_diff(added_line: str) -> str:
    """Build a minimal git diff containing one added line."""
    return (
        "diff --git a/example.py b/example.py\n"
        "--- a/example.py\n"
        "+++ b/example.py\n"
        "@@ -0,0 +1 @@\n"
        f"+{added_line}\n"
    )


class TestBlockedPatterns:
    def test_aws_key_in_added_line_blocks(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        diff = _clean_diff("AWS_KEY = 'AKIAIOSFODNN7EXAMPLE'")
        _patch(monkeypatch, command="git commit -m 'feat: thing'", project_dir=tmp_dir, diff=diff)

        rc = pre_commit_secret_scan.main()

        err = capsys.readouterr().err
        assert rc == 2
        assert "AWS access key ID" in err
        assert "git reset HEAD" in err

    def test_github_token_blocks(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        diff = _clean_diff("TOKEN = 'ghp_abcdefghijklmnopqrstuvwxyz0123456789'")
        _patch(monkeypatch, command="git commit", project_dir=tmp_dir, diff=diff)

        assert pre_commit_secret_scan.main() == 2

    def test_openai_key_blocks(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        fake_key = "sk-" + "a" * 48
        diff = _clean_diff(f"OPENAI = '{fake_key}'")
        _patch(monkeypatch, command="git commit", project_dir=tmp_dir, diff=diff)

        assert pre_commit_secret_scan.main() == 2

    def test_anthropic_key_blocks(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        fake_key = "sk-ant-" + "a" * 40
        diff = _clean_diff(f"ANTHROPIC = '{fake_key}'")
        _patch(monkeypatch, command="git commit", project_dir=tmp_dir, diff=diff)

        assert pre_commit_secret_scan.main() == 2

    def test_pem_private_key_blocks(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        diff = _clean_diff("-----BEGIN RSA PRIVATE KEY-----")
        _patch(monkeypatch, command="git commit", project_dir=tmp_dir, diff=diff)

        assert pre_commit_secret_scan.main() == 2


class TestContextLinesIgnored:
    def test_secret_in_context_line_is_ignored(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Context line (no +/- prefix) contains a secret — must not trigger.
        diff = (
            "diff --git a/example.py b/example.py\n"
            "--- a/example.py\n"
            "+++ b/example.py\n"
            "@@ -1,3 +1,3 @@\n"
            " AWS_KEY = 'AKIAIOSFODNN7EXAMPLE'\n"  # context line
            "-old = 1\n"
            "+new = 2\n"
        )
        _patch(monkeypatch, command="git commit", project_dir=tmp_dir, diff=diff)

        assert pre_commit_secret_scan.main() == 0

    def test_secret_in_removed_line_is_ignored(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        diff = (
            "diff --git a/example.py b/example.py\n"
            "--- a/example.py\n"
            "+++ b/example.py\n"
            "@@ -1,1 +1,1 @@\n"
            "-AWS_KEY = 'AKIAIOSFODNN7EXAMPLE'\n"
            "+AWS_KEY = os.environ['AWS']\n"
        )
        _patch(monkeypatch, command="git commit", project_dir=tmp_dir, diff=diff)

        assert pre_commit_secret_scan.main() == 0

    def test_file_header_plus_plus_plus_ignored(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # "+++ b/path" is a file header, not an added line; even if a path
        # string looks scary, it must not be scanned as content.
        diff = (
            "diff --git a/AKIAIOSFODNN7EXAMPLE b/AKIAIOSFODNN7EXAMPLE\n"
            "--- a/AKIAIOSFODNN7EXAMPLE\n"
            "+++ b/AKIAIOSFODNN7EXAMPLE\n"
            "@@ -0,0 +1 @@\n"
            "+hello\n"
        )
        _patch(monkeypatch, command="git commit", project_dir=tmp_dir, diff=diff)

        # The file header lines start with `+++` / `---`; those are filtered.
        # The only added line is `+hello`, which is clean.
        assert pre_commit_secret_scan.main() == 0


class TestBypasses:
    def test_wip_marker_bypasses(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        diff = _clean_diff("AKIAIOSFODNN7EXAMPLE")
        _patch(
            monkeypatch,
            command="git commit -m '[WIP] in progress'",
            project_dir=tmp_dir,
            diff=diff,
        )

        assert pre_commit_secret_scan.main() == 0

    def test_merge_head_bypasses(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        git_dir = tmp_dir / ".git"
        git_dir.mkdir()
        (git_dir / "MERGE_HEAD").write_text("abc123\n", encoding="utf-8")

        diff = _clean_diff("AKIAIOSFODNN7EXAMPLE")
        _patch(monkeypatch, command="git commit", project_dir=tmp_dir, diff=diff)

        assert pre_commit_secret_scan.main() == 0


class TestNonCommitBash:
    def test_non_commit_bash_is_noop(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Even if the "command" contains a secret, a non-commit Bash call
        # should never call _staged_diff.
        called: dict[str, bool] = {"staged": False}

        def fake_diff(_d: Path) -> str | None:
            called["staged"] = True
            return None

        monkeypatch.setattr(pre_commit_secret_scan, "_staged_diff", fake_diff)
        monkeypatch.setattr(pre_commit_secret_scan, "get_project_dir", lambda: tmp_dir)
        payload = {"tool_name": "Bash", "tool_input": {"command": "ls -la"}}
        monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(payload)))

        assert pre_commit_secret_scan.main() == 0
        assert called["staged"] is False

    def test_non_bash_tool_is_noop(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        payload = {"tool_name": "Edit", "tool_input": {}}
        monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(payload)))
        monkeypatch.setattr(pre_commit_secret_scan, "get_project_dir", lambda: tmp_dir)

        assert pre_commit_secret_scan.main() == 0

    def test_commit_tree_not_triggered(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        diff = _clean_diff("AKIAIOSFODNN7EXAMPLE")
        _patch(
            monkeypatch,
            command="git commit-tree abc123",
            project_dir=tmp_dir,
            diff=diff,
        )

        # commit-tree is not a commit — should not block.
        assert pre_commit_secret_scan.main() == 0

    def test_git_c_option_still_triggered(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        diff = _clean_diff("AKIAIOSFODNN7EXAMPLE")
        _patch(
            monkeypatch,
            command="git -c user.email=test@x.com commit -m 'x'",
            project_dir=tmp_dir,
            diff=diff,
        )

        assert pre_commit_secret_scan.main() == 2


class TestCleanCases:
    def test_clean_diff_allows(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        diff = _clean_diff("x = 1")
        _patch(monkeypatch, command="git commit", project_dir=tmp_dir, diff=diff)

        assert pre_commit_secret_scan.main() == 0

    def test_empty_diff_allows(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _patch(monkeypatch, command="git commit", project_dir=tmp_dir, diff="")

        assert pre_commit_secret_scan.main() == 0

    def test_diff_unavailable_allows(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # git subprocess failed → None. Don't block the commit on our own
        # inability to read it; pre_commit_cli_gate is the real gate.
        _patch(monkeypatch, command="git commit", project_dir=tmp_dir, diff=None)

        assert pre_commit_secret_scan.main() == 0

    def test_only_removed_lines_allows(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        diff = (
            "diff --git a/example.py b/example.py\n"
            "--- a/example.py\n"
            "+++ b/example.py\n"
            "@@ -1,1 +0,0 @@\n"
            "-x = 1\n"
        )
        _patch(monkeypatch, command="git commit", project_dir=tmp_dir, diff=diff)

        assert pre_commit_secret_scan.main() == 0


class TestEmptyStdin:
    def test_empty_stdin_allows(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(sys, "stdin", StringIO(""))
        monkeypatch.setattr(pre_commit_secret_scan, "get_project_dir", lambda: tmp_dir)

        assert pre_commit_secret_scan.main() == 0
