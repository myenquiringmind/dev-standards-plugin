"""Tests for hooks/_session_state_common.py."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from hooks._session_state_common import (
    archive_state_to_injected,
    extract_from_transcript,
    get_git_state,
    get_memory_dir,
    parse_todos_from_markdown,
    write_session_state,
)

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# get_memory_dir
# ---------------------------------------------------------------------------


class TestGetMemoryDir:
    def test_windows_path_slugging(self) -> None:
        result = get_memory_dir(r"C:\Users\jmarks01\Projects\dsp")
        # Each of ``:`` and ``\`` becomes ``-`` independently, so
        # ``C:\`` → ``C--`` (this matches the real on-disk layout
        # under ~/.claude/projects/).
        assert result.name == "memory"
        assert result.parent.name == "C--Users-jmarks01-Projects-dsp"

    def test_posix_path_slugging(self) -> None:
        result = get_memory_dir("/home/jm/projects/dsp")
        assert result.name == "memory"
        # Leading slash becomes "-", which is stripped.
        assert result.parent.name == "home-jm-projects-dsp"

    def test_under_home(self) -> None:
        result = get_memory_dir("/whatever")
        assert result.is_absolute()
        assert ".claude" in result.parts
        assert "projects" in result.parts

    def test_accepts_path_object(self, tmp_dir: Path) -> None:
        result = get_memory_dir(tmp_dir)
        assert result.name == "memory"


# ---------------------------------------------------------------------------
# extract_from_transcript
# ---------------------------------------------------------------------------


def _write_transcript(path: Path, entries: list[dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


class TestExtractFromTranscript:
    def test_extracts_modified_files(self, tmp_dir: Path) -> None:
        transcript = tmp_dir / "t.jsonl"
        _write_transcript(
            transcript,
            [
                {
                    "type": "tool_use",
                    "tool_name": "Edit",
                    "tool_input": {"file_path": "/a.py"},
                },
                {
                    "type": "tool_use",
                    "tool_name": "Write",
                    "tool_input": {"file_path": "/b.py"},
                },
                {
                    "type": "tool_use",
                    "tool_name": "Bash",
                    "tool_input": {"command": "ls"},
                },
            ],
        )
        result = extract_from_transcript(transcript)
        assert result["modified_files"] == ["/a.py", "/b.py"]

    def test_extracts_last_user_prompt_string(self, tmp_dir: Path) -> None:
        transcript = tmp_dir / "t.jsonl"
        _write_transcript(
            transcript,
            [
                {"type": "human", "content": "first prompt"},
                {"type": "human", "content": "second prompt"},
            ],
        )
        result = extract_from_transcript(transcript)
        assert result["last_user_prompt"] == "second prompt"

    def test_extracts_last_user_prompt_blocks(self, tmp_dir: Path) -> None:
        transcript = tmp_dir / "t.jsonl"
        _write_transcript(
            transcript,
            [
                {
                    "type": "human",
                    "content": [{"type": "text", "text": "hello from blocks"}],
                },
            ],
        )
        result = extract_from_transcript(transcript)
        assert result["last_user_prompt"] == "hello from blocks"

    def test_truncates_user_prompt_to_500(self, tmp_dir: Path) -> None:
        transcript = tmp_dir / "t.jsonl"
        long_text = "a" * 1000
        _write_transcript(transcript, [{"type": "human", "content": long_text}])
        result = extract_from_transcript(transcript)
        assert len(result["last_user_prompt"]) == 500

    def test_captures_last_todo_write(self, tmp_dir: Path) -> None:
        transcript = tmp_dir / "t.jsonl"
        _write_transcript(
            transcript,
            [
                {
                    "type": "tool_use",
                    "tool_name": "TodoWrite",
                    "tool_input": {
                        "todos": [{"content": "one", "status": "pending"}],
                    },
                },
                {
                    "type": "tool_use",
                    "tool_name": "TodoWrite",
                    "tool_input": {
                        "todos": [
                            {"content": "two", "status": "in_progress"},
                            {"content": "three", "status": "completed"},
                        ],
                    },
                },
            ],
        )
        result = extract_from_transcript(transcript)
        assert len(result["todos"]) == 2
        assert result["todos"][0]["content"] == "two"

    def test_caps_errors_at_3(self, tmp_dir: Path) -> None:
        transcript = tmp_dir / "t.jsonl"
        entries = [
            {"type": "tool_result", "is_error": True, "content": f"err {i}"} for i in range(10)
        ]
        _write_transcript(transcript, entries)
        result = extract_from_transcript(transcript)
        assert len(result["errors"]) == 3
        # Most recent three.
        assert "err 9" in result["errors"][-1]

    def test_caps_reasoning_at_2(self, tmp_dir: Path) -> None:
        transcript = tmp_dir / "t.jsonl"
        entries = [{"type": "assistant", "content": f"thought {i}"} for i in range(10)]
        _write_transcript(transcript, entries)
        result = extract_from_transcript(transcript)
        assert len(result["recent_reasoning"]) == 2
        assert "thought 9" in result["recent_reasoning"][-1]

    def test_skips_malformed_lines(self, tmp_dir: Path) -> None:
        transcript = tmp_dir / "t.jsonl"
        with open(transcript, "w", encoding="utf-8") as f:
            f.write('{"type": "human", "content": "good"}\n')
            f.write("{not json\n")
            f.write("\n")
            f.write('{"type": "human", "content": "also good"}\n')
        result = extract_from_transcript(transcript)
        assert result["last_user_prompt"] == "also good"

    def test_missing_file_returns_empty(self, tmp_dir: Path) -> None:
        result = extract_from_transcript(tmp_dir / "nope.jsonl")
        assert result["modified_files"] == []
        assert result["last_user_prompt"] == ""
        assert result["todos"] == []


# ---------------------------------------------------------------------------
# get_git_state
# ---------------------------------------------------------------------------


class TestGetGitState:
    def test_reports_branch_in_clean_repo(self, tmp_git_repo: Path) -> None:
        result = get_git_state(tmp_git_repo)
        assert "### Current Branch" in result

    def test_reports_status_when_dirty(self, tmp_git_repo: Path) -> None:
        (tmp_git_repo / "new.txt").write_text("hi", encoding="utf-8")
        result = get_git_state(tmp_git_repo)
        assert "### Git Status" in result
        assert "new.txt" in result

    def test_non_repo_returns_empty(self, tmp_dir: Path) -> None:
        result = get_git_state(tmp_dir)
        assert result == ""


# ---------------------------------------------------------------------------
# write_session_state
# ---------------------------------------------------------------------------


class TestWriteSessionState:
    def test_writes_file_and_header(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Redirect HOME so the memory dir lives inside the tmp area.
        monkeypatch.setenv("HOME", str(tmp_git_repo))
        monkeypatch.setenv("USERPROFILE", str(tmp_git_repo))
        data = {
            "last_user_prompt": "hi",
            "todos": [],
            "modified_files": [],
            "errors": [],
            "recent_reasoning": [],
        }
        path = write_session_state(data, tmp_git_repo)
        content = path.read_text(encoding="utf-8")
        assert path.name == "session-state.md"
        assert "# Session State Snapshot" in content
        assert "## Active Request" in content
        assert "hi" in content

    def test_header_note_included(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("HOME", str(tmp_git_repo))
        monkeypatch.setenv("USERPROFILE", str(tmp_git_repo))
        data = {
            "last_user_prompt": "",
            "todos": [],
            "modified_files": [],
            "errors": [],
            "recent_reasoning": [],
        }
        path = write_session_state(data, tmp_git_repo, header_note="Pre-compaction snapshot")
        assert "Pre-compaction snapshot" in path.read_text(encoding="utf-8")

    def test_sections_rendered_for_all_fields(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("HOME", str(tmp_git_repo))
        monkeypatch.setenv("USERPROFILE", str(tmp_git_repo))
        data = {
            "last_user_prompt": "do the thing",
            "todos": [
                {"content": "pend task", "status": "pending"},
                {"content": "wip task", "status": "in_progress"},
                {"content": "done task", "status": "completed"},
            ],
            "modified_files": ["/a.py", "/b.py"],
            "errors": ["oops"],
            "recent_reasoning": ["I was thinking..."],
        }
        path = write_session_state(data, tmp_git_repo)
        content = path.read_text(encoding="utf-8")
        assert "## Active Request" in content
        assert "## Task Progress" in content
        assert "- [ ] pend task" in content
        assert "- [~] wip task" in content
        assert "- [x] done task" in content
        assert "## Files Modified" in content
        assert "`/a.py`" in content
        assert "## Recent Errors" in content
        assert "- oops" in content
        assert "## Recent Context" in content
        assert "> I was thinking..." in content

    def test_round_trip_todos(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("HOME", str(tmp_git_repo))
        monkeypatch.setenv("USERPROFILE", str(tmp_git_repo))
        data = {
            "last_user_prompt": "",
            "todos": [
                {"content": "alpha", "status": "pending"},
                {"content": "beta", "status": "in_progress"},
                {"content": "gamma", "status": "completed"},
            ],
            "modified_files": [],
            "errors": [],
            "recent_reasoning": [],
        }
        path = write_session_state(data, tmp_git_repo)
        recovered = parse_todos_from_markdown(path.read_text(encoding="utf-8"))
        assert recovered == data["todos"]


# ---------------------------------------------------------------------------
# parse_todos_from_markdown
# ---------------------------------------------------------------------------


class TestParseTodosFromMarkdown:
    def test_recognises_three_markers(self) -> None:
        md = "# Header\n## Task Progress\n- [ ] todo 1\n- [~] todo 2\n- [x] todo 3\n"
        result = parse_todos_from_markdown(md)
        assert result == [
            {"content": "todo 1", "status": "pending"},
            {"content": "todo 2", "status": "in_progress"},
            {"content": "todo 3", "status": "completed"},
        ]

    def test_uppercase_x_marker(self) -> None:
        md = "## Task Progress\n- [X] done\n"
        assert parse_todos_from_markdown(md) == [
            {"content": "done", "status": "completed"},
        ]

    def test_stops_at_next_section(self) -> None:
        md = "## Task Progress\n- [ ] first\n## Files Modified\n- [ ] not a todo\n"
        result = parse_todos_from_markdown(md)
        assert result == [{"content": "first", "status": "pending"}]

    def test_no_section_returns_empty(self) -> None:
        md = "## Files Modified\n- [ ] x\n"
        assert parse_todos_from_markdown(md) == []

    def test_empty_string(self) -> None:
        assert parse_todos_from_markdown("") == []


# ---------------------------------------------------------------------------
# archive_state_to_injected
# ---------------------------------------------------------------------------


class TestArchiveStateToInjected:
    def test_renames_when_present(self, tmp_dir: Path) -> None:
        source = tmp_dir / "session-state.md"
        source.write_text("payload", encoding="utf-8")
        result = archive_state_to_injected(tmp_dir)
        assert result is not None
        assert result.name == "session-state.md.injected"
        assert not source.exists()
        assert result.read_text(encoding="utf-8") == "payload"

    def test_noop_when_missing(self, tmp_dir: Path) -> None:
        assert archive_state_to_injected(tmp_dir) is None

    def test_overwrites_stale_injected(self, tmp_dir: Path) -> None:
        stale = tmp_dir / "session-state.md.injected"
        stale.write_text("old", encoding="utf-8")
        source = tmp_dir / "session-state.md"
        source.write_text("new", encoding="utf-8")
        result = archive_state_to_injected(tmp_dir)
        assert result is not None
        assert result.read_text(encoding="utf-8") == "new"


# ---------------------------------------------------------------------------
# End-to-end round trip
# ---------------------------------------------------------------------------


class TestRoundTrip:
    def test_write_then_parse_todos(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("HOME", str(tmp_git_repo))
        monkeypatch.setenv("USERPROFILE", str(tmp_git_repo))

        # Create a small transcript that exercises every branch.
        transcript = tmp_git_repo / "t.jsonl"
        _write_transcript(
            transcript,
            [
                {"type": "human", "content": "do X"},
                {
                    "type": "tool_use",
                    "tool_name": "TodoWrite",
                    "tool_input": {
                        "todos": [
                            {"content": "first", "status": "in_progress"},
                            {"content": "second", "status": "pending"},
                        ],
                    },
                },
                {
                    "type": "tool_use",
                    "tool_name": "Edit",
                    "tool_input": {"file_path": str(tmp_git_repo / "x.py")},
                },
                {"type": "assistant", "content": "reasoning step"},
            ],
        )

        data = extract_from_transcript(transcript)
        path = write_session_state(data, tmp_git_repo)

        content = path.read_text(encoding="utf-8")
        assert "do X" in content
        assert "reasoning step" in content
        recovered = parse_todos_from_markdown(content)
        assert recovered == data["todos"]

        # Archive and verify.
        injected = archive_state_to_injected(path.parent)
        assert injected is not None
        assert injected.exists()
        assert not path.exists()


# ---------------------------------------------------------------------------
# get_git_state timeout surface (light coverage — don't fake timeouts)
# ---------------------------------------------------------------------------


class TestGitStateResilience:
    def test_git_not_installed(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def boom(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
            msg = "git not found"
            raise FileNotFoundError(msg)

        monkeypatch.setattr(subprocess, "run", boom)
        # Should not raise.
        assert get_git_state(tmp_dir) == ""
