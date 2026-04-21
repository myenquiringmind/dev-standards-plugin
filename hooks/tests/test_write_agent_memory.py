"""Tests for hooks/write_agent_memory.py."""

from __future__ import annotations

import sys
from io import StringIO
from pathlib import Path

import pytest

from hooks import write_agent_memory


def _run(
    monkeypatch: pytest.MonkeyPatch,
    project_dir: Path,
    stdin_content: str,
    argv: list[str],
    *,
    plugin_data_env: str | None = None,
) -> int:
    monkeypatch.setattr(write_agent_memory, "get_project_dir", lambda: project_dir)
    monkeypatch.setattr(sys, "stdin", StringIO(stdin_content))
    if plugin_data_env is not None:
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", plugin_data_env)
    else:
        monkeypatch.delenv("CLAUDE_PLUGIN_DATA", raising=False)
        monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    return write_agent_memory.main(argv)


class TestHappyPath:
    def test_append_creates_file_with_heading(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        rc = _run(
            monkeypatch,
            tmp_dir,
            "learned X about Y",
            ["--agent", "py-solid-dry-reviewer", "--append"],
        )
        assert rc == 0
        memory = tmp_dir / ".claude" / "agent-memory" / "py-solid-dry-reviewer" / "MEMORY.md"
        assert memory.exists()
        content = memory.read_text(encoding="utf-8")
        assert "learned X about Y" in content
        assert "## " in content  # timestamp heading

    def test_append_to_existing_file(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        memory_dir = tmp_dir / ".claude" / "agent-memory" / "fe-doc-checker"
        memory_dir.mkdir(parents=True)
        (memory_dir / "MEMORY.md").write_text(
            "# fe-doc-checker memory\n\n## 2026-01-01 00:00:00 UTC\n\nold entry\n",
            encoding="utf-8",
        )

        rc = _run(
            monkeypatch,
            tmp_dir,
            "second insight",
            ["--agent", "fe-doc-checker"],
        )
        assert rc == 0
        content = (memory_dir / "MEMORY.md").read_text(encoding="utf-8")
        assert "old entry" in content
        assert "second insight" in content
        # Two heading markers
        assert content.count("## 20") >= 2

    def test_replace_overwrites_existing(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        memory_dir = tmp_dir / ".claude" / "agent-memory" / "meta-scaffolder"
        memory_dir.mkdir(parents=True)
        (memory_dir / "MEMORY.md").write_text("stale content\n", encoding="utf-8")

        rc = _run(
            monkeypatch,
            tmp_dir,
            "fresh content",
            ["--agent", "meta-scaffolder", "--replace"],
        )
        assert rc == 0
        content = (memory_dir / "MEMORY.md").read_text(encoding="utf-8")
        assert "stale content" not in content
        assert "fresh content" in content

    def test_respects_claude_plugin_data_env(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        plugin_data = tmp_dir / "plugin-data"
        plugin_data.mkdir()
        rc = _run(
            monkeypatch,
            tmp_dir / "unused-project",
            "x",
            ["--agent", "py-reviewer", "--append"],
            plugin_data_env=str(plugin_data),
        )
        assert rc == 0
        assert (plugin_data / "agent-memory" / "py-reviewer" / "MEMORY.md").exists()


class TestPathTraversalProtection:
    """Phase 1 exit gate assertion #8 — unsafe agent names must be rejected."""

    @pytest.mark.parametrize(
        "bad_name",
        [
            "../../etc/passwd",
            "..",
            "../escape",
            "foo/bar",
            "foo\\bar",
            ".hidden",
            "UPPER",
            "has space",
            "",
        ],
    )
    def test_rejects_unsafe_agent_name(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        bad_name: str,
    ) -> None:
        rc = _run(
            monkeypatch,
            tmp_dir,
            "content",
            ["--agent", bad_name, "--append"],
        )
        captured = capsys.readouterr()
        # argparse may swallow the empty string as missing arg (rc != 0);
        # non-empty bad names should print our refusal message with rc == 1.
        if bad_name == "":
            assert rc != 0
        else:
            assert rc == 1
            assert "unsafe agent name" in captured.err

    def test_valid_agent_name_accepted(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        rc = _run(monkeypatch, tmp_dir, "x", ["--agent", "py-solid-dry-reviewer", "--append"])
        assert rc == 0


class TestEmptyStdin:
    def test_empty_stdin_rejected(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        rc = _run(monkeypatch, tmp_dir, "", ["--agent", "py-reviewer", "--append"])
        captured = capsys.readouterr()
        assert rc == 1
        assert "empty content" in captured.err

    def test_whitespace_only_stdin_rejected(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        rc = _run(monkeypatch, tmp_dir, "   \n\t", ["--agent", "py-reviewer", "--append"])
        assert rc == 1


class TestMutuallyExclusiveFlags:
    def test_append_and_replace_together_rejected(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        rc = _run(
            monkeypatch,
            tmp_dir,
            "x",
            ["--agent", "py-reviewer", "--append", "--replace"],
        )
        captured = capsys.readouterr()
        assert rc == 1
        assert "mutually exclusive" in captured.err


class TestWriteFailure:
    def test_atomic_write_oserror(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        def boom(*_args: object, **_kwargs: object) -> Path:
            raise OSError("read-only fs")

        monkeypatch.setattr("hooks.write_agent_memory.atomic_write", boom)
        rc = _run(
            monkeypatch,
            tmp_dir,
            "x",
            ["--agent", "py-reviewer", "--append"],
        )
        captured = capsys.readouterr()
        assert rc == 1
        assert "could not write memory" in captured.err
