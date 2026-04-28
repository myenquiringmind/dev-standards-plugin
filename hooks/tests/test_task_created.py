"""Tests for hooks/task_created.py."""

from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from hooks import task_created

_STATE_FILENAME = "session-state.md"


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    memory_dir: Path,
    payload: dict[str, Any],
) -> None:
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(payload)))
    monkeypatch.setattr(task_created, "get_project_dir", lambda: memory_dir)
    monkeypatch.setattr(task_created, "get_memory_dir", lambda _d: memory_dir)


def _seed_state(memory_dir: Path, content: str) -> Path:
    p = memory_dir / _STATE_FILENAME
    p.write_text(content, encoding="utf-8")
    return p


def _read_state(memory_dir: Path) -> str:
    return (memory_dir / _STATE_FILENAME).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Subject extraction
# ---------------------------------------------------------------------------


class TestSubjectExtraction:
    @pytest.mark.parametrize(
        "payload",
        [
            {"task": {"subject": "Build widget"}},
            {"task": {"content": "Build widget"}},
            {"subject": "Build widget"},
            {"content": "Build widget"},
        ],
    )
    def test_subject_from_each_recognised_field(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        payload: dict[str, Any],
    ) -> None:
        _seed_state(tmp_dir, "## Task Progress\n")
        _patch(monkeypatch, tmp_dir, payload)

        assert task_created.main() == 0
        assert "- [ ] Build widget" in _read_state(tmp_dir)

    def test_task_subject_priority_over_other_fields(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _seed_state(tmp_dir, "## Task Progress\n")
        _patch(
            monkeypatch,
            tmp_dir,
            {
                "task": {"subject": "from-task-subject", "content": "from-task-content"},
                "subject": "from-top",
            },
        )

        task_created.main()
        text = _read_state(tmp_dir)
        assert "from-task-subject" in text
        assert "from-task-content" not in text
        assert "from-top" not in text

    def test_empty_subject_is_no_op(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _seed_state(tmp_dir, "## Task Progress\n")
        _patch(monkeypatch, tmp_dir, {"task": {"subject": "   "}})

        task_created.main()
        # Section unchanged.
        assert _read_state(tmp_dir) == "## Task Progress\n"

    def test_no_subject_field_is_no_op(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _seed_state(tmp_dir, "## Task Progress\n")
        _patch(monkeypatch, tmp_dir, {"task": {"description": "no subject here"}})

        task_created.main()
        assert _read_state(tmp_dir) == "## Task Progress\n"


# ---------------------------------------------------------------------------
# State-file mechanics: section creation, append, idempotency
# ---------------------------------------------------------------------------


class TestStateFileUpdates:
    def test_appends_when_section_exists(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _seed_state(
            tmp_dir,
            "# Header\n\n## Task Progress\n- [ ] existing task\n\n## Files Modified\n- `a.py`\n",
        )
        _patch(monkeypatch, tmp_dir, {"task": {"subject": "new task"}})

        task_created.main()
        text = _read_state(tmp_dir)

        # Both lines present, in order.
        existing_idx = text.index("- [ ] existing task")
        new_idx = text.index("- [ ] new task")
        files_idx = text.index("## Files Modified")
        assert existing_idx < new_idx < files_idx
        # Other section preserved.
        assert "- `a.py`" in text

    def test_creates_section_when_missing(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _seed_state(tmp_dir, "# Snapshot\n\n## Files Modified\n- `a.py`\n")
        _patch(monkeypatch, tmp_dir, {"task": {"subject": "first task"}})

        task_created.main()
        text = _read_state(tmp_dir)
        assert "## Task Progress" in text
        assert "- [ ] first task" in text
        # Existing section retained.
        assert "## Files Modified" in text
        assert "- `a.py`" in text

    def test_idempotent_on_duplicate(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        seed = "## Task Progress\n- [ ] same task\n"
        _seed_state(tmp_dir, seed)
        _patch(monkeypatch, tmp_dir, {"task": {"subject": "same task"}})

        task_created.main()
        # Unchanged — single occurrence retained.
        assert _read_state(tmp_dir).count("- [ ] same task") == 1

    def test_appends_new_line_when_section_has_only_heading(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _seed_state(tmp_dir, "## Task Progress\n")
        _patch(monkeypatch, tmp_dir, {"task": {"subject": "only task"}})

        task_created.main()
        assert "- [ ] only task" in _read_state(tmp_dir)

    def test_section_at_eof_with_no_trailing_newline(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _seed_state(tmp_dir, "## Task Progress\n- [ ] one")
        _patch(monkeypatch, tmp_dir, {"task": {"subject": "two"}})

        task_created.main()
        text = _read_state(tmp_dir)
        assert "- [ ] one" in text
        assert "- [ ] two" in text


# ---------------------------------------------------------------------------
# Fail-open: missing inputs / state file / payload
# ---------------------------------------------------------------------------


class TestFailOpen:
    def test_missing_state_file_is_no_op(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _patch(monkeypatch, tmp_dir, {"task": {"subject": "ignored"}})

        assert task_created.main() == 0
        assert not (tmp_dir / _STATE_FILENAME).exists()

    def test_empty_stdin_is_no_op(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _seed_state(tmp_dir, "## Task Progress\n")
        monkeypatch.setattr(sys, "stdin", StringIO(""))
        monkeypatch.setattr(task_created, "get_project_dir", lambda: tmp_dir)
        monkeypatch.setattr(task_created, "get_memory_dir", lambda _d: tmp_dir)

        assert task_created.main() == 0
        # Section unchanged.
        assert _read_state(tmp_dir) == "## Task Progress\n"

    def test_non_string_subject_ignored(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _seed_state(tmp_dir, "## Task Progress\n")
        _patch(monkeypatch, tmp_dir, {"task": {"subject": 42}})

        assert task_created.main() == 0
        assert _read_state(tmp_dir) == "## Task Progress\n"
