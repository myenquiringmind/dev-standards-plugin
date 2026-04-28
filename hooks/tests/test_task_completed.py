"""Tests for hooks/task_completed.py."""

from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from hooks import task_completed

_STATE_FILENAME = "session-state.md"


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    memory_dir: Path,
    payload: dict[str, Any],
) -> None:
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(payload)))
    monkeypatch.setattr(task_completed, "get_project_dir", lambda: memory_dir)
    monkeypatch.setattr(task_completed, "get_memory_dir", lambda _d: memory_dir)


def _seed_state(memory_dir: Path, content: str) -> Path:
    p = memory_dir / _STATE_FILENAME
    p.write_text(content, encoding="utf-8")
    return p


def _read_state(memory_dir: Path) -> str:
    return (memory_dir / _STATE_FILENAME).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Happy path: pending → completed
# ---------------------------------------------------------------------------


class TestFlipsPending:
    def test_flips_pending_line_to_completed(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _seed_state(
            tmp_dir,
            "## Task Progress\n- [ ] do the thing\n- [ ] another\n",
        )
        _patch(monkeypatch, tmp_dir, {"task": {"subject": "do the thing"}})

        assert task_completed.main() == 0
        text = _read_state(tmp_dir)
        assert "- [x] do the thing" in text
        assert "- [ ] another" in text  # Other tasks untouched.

    def test_subject_extraction_priority(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _seed_state(tmp_dir, "## Task Progress\n- [ ] from-task-subject\n")
        _patch(
            monkeypatch,
            tmp_dir,
            {
                "task": {"subject": "from-task-subject", "content": "from-task-content"},
                "subject": "from-top",
            },
        )

        task_completed.main()
        text = _read_state(tmp_dir)
        assert "- [x] from-task-subject" in text

    @pytest.mark.parametrize(
        "payload",
        [
            {"task": {"subject": "x"}},
            {"task": {"content": "x"}},
            {"subject": "x"},
            {"content": "x"},
        ],
    )
    def test_subject_from_each_recognised_field(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        payload: dict[str, Any],
    ) -> None:
        _seed_state(tmp_dir, "## Task Progress\n- [ ] x\n")
        _patch(monkeypatch, tmp_dir, payload)

        task_completed.main()
        assert "- [x] x" in _read_state(tmp_dir)

    def test_first_match_wins_on_duplicate_subjects(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _seed_state(
            tmp_dir,
            "## Task Progress\n- [ ] same\n- [ ] same\n",
        )
        _patch(monkeypatch, tmp_dir, {"task": {"subject": "same"}})

        task_completed.main()
        text = _read_state(tmp_dir)
        # First flipped, second still pending.
        assert text.count("- [x] same") == 1
        assert text.count("- [ ] same") == 1

    def test_other_sections_unchanged(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _seed_state(
            tmp_dir,
            "# Snapshot\n\n## Task Progress\n- [ ] flip me\n\n## Files Modified\n- `a.py`\n",
        )
        _patch(monkeypatch, tmp_dir, {"task": {"subject": "flip me"}})

        task_completed.main()
        text = _read_state(tmp_dir)
        assert "- [x] flip me" in text
        assert "## Files Modified" in text
        assert "- `a.py`" in text


# ---------------------------------------------------------------------------
# No-op cases: idempotent / not-found / no section
# ---------------------------------------------------------------------------


class TestNoOpCases:
    def test_already_completed_is_idempotent(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        seed = "## Task Progress\n- [x] already done\n"
        _seed_state(tmp_dir, seed)
        _patch(monkeypatch, tmp_dir, {"task": {"subject": "already done"}})

        task_completed.main()
        # File unchanged.
        assert _read_state(tmp_dir) == seed

    def test_subject_not_in_section_does_not_create_line(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        seed = "## Task Progress\n- [ ] something else\n"
        _seed_state(tmp_dir, seed)
        _patch(monkeypatch, tmp_dir, {"task": {"subject": "untracked task"}})

        task_completed.main()
        text = _read_state(tmp_dir)
        # No new line invented.
        assert "untracked task" not in text
        # Existing pending line untouched.
        assert "- [ ] something else" in text

    def test_section_absent_is_no_op(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        seed = "# Snapshot\n\n## Files Modified\n- `a.py`\n"
        _seed_state(tmp_dir, seed)
        _patch(monkeypatch, tmp_dir, {"task": {"subject": "anything"}})

        task_completed.main()
        # File unchanged.
        assert _read_state(tmp_dir) == seed


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

        assert task_completed.main() == 0
        assert not (tmp_dir / _STATE_FILENAME).exists()

    def test_empty_subject_is_no_op(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        seed = "## Task Progress\n- [ ] keep me\n"
        _seed_state(tmp_dir, seed)
        _patch(monkeypatch, tmp_dir, {"task": {"subject": "   "}})

        assert task_completed.main() == 0
        assert _read_state(tmp_dir) == seed

    def test_no_subject_field_is_no_op(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        seed = "## Task Progress\n- [ ] keep me\n"
        _seed_state(tmp_dir, seed)
        _patch(monkeypatch, tmp_dir, {"task": {"description": "no subject"}})

        assert task_completed.main() == 0
        assert _read_state(tmp_dir) == seed

    def test_non_string_subject_ignored(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        seed = "## Task Progress\n- [ ] keep me\n"
        _seed_state(tmp_dir, seed)
        _patch(monkeypatch, tmp_dir, {"task": {"subject": 99}})

        assert task_completed.main() == 0
        assert _read_state(tmp_dir) == seed

    def test_empty_stdin_is_no_op(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        seed = "## Task Progress\n- [ ] keep me\n"
        _seed_state(tmp_dir, seed)
        monkeypatch.setattr(sys, "stdin", StringIO(""))
        monkeypatch.setattr(task_completed, "get_project_dir", lambda: tmp_dir)
        monkeypatch.setattr(task_completed, "get_memory_dir", lambda _d: tmp_dir)

        assert task_completed.main() == 0
        assert _read_state(tmp_dir) == seed
