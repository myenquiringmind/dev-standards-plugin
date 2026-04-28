"""Tests for hooks/phase_transition.py."""

from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from hooks import phase_transition

_STATE_FILENAME = "session-state.md"


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    memory_dir: Path,
    payload: dict[str, Any] | None = None,
) -> None:
    body = json.dumps(payload) if payload is not None else ""
    monkeypatch.setattr(sys, "stdin", StringIO(body))
    monkeypatch.setattr(phase_transition, "get_project_dir", lambda: memory_dir)
    monkeypatch.setattr(phase_transition, "get_memory_dir", lambda _d: memory_dir)


def _seed_state(memory_dir: Path, content: str) -> Path:
    p = memory_dir / _STATE_FILENAME
    p.write_text(content, encoding="utf-8")
    return p


def _read_state(memory_dir: Path) -> str:
    return (memory_dir / _STATE_FILENAME).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Detection — phase token recognised; last match wins
# ---------------------------------------------------------------------------


class TestDetection:
    @pytest.mark.parametrize(
        "phase",
        ["OBJECTIVE", "GAP", "DESIGN", "IMPLEMENT", "VALIDATE", "OBSERVE", "COMMIT", "REFLECT"],
    )
    def test_each_phase_word_recognised(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch, phase: str
    ) -> None:
        _seed_state(tmp_dir, "## Current Phase\nIMPLEMENT\n")
        _patch(monkeypatch, tmp_dir, {"prompt": f"now we are in {phase}"})

        assert phase_transition.main() == 0
        text = _read_state(tmp_dir)
        assert f"## Current Phase\n{phase}" in text

    def test_last_match_wins(self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _seed_state(tmp_dir, "## Current Phase\nGAP\n")
        _patch(
            monkeypatch,
            tmp_dir,
            {"prompt": "DESIGN done, now IMPLEMENT the next bit"},
        )

        phase_transition.main()
        text = _read_state(tmp_dir)
        assert "## Current Phase\nIMPLEMENT" in text

    def test_lowercase_phase_words_ignored(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seed = "## Current Phase\nDESIGN\n"
        _seed_state(tmp_dir, seed)
        _patch(monkeypatch, tmp_dir, {"prompt": "let's design the thing and implement it"})

        assert phase_transition.main() == 0
        # No uppercase token → no change.
        assert _read_state(tmp_dir) == seed

    def test_substring_does_not_match(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # ``DESIGNATION`` should not match ``DESIGN``.
        seed = "## Current Phase\nGAP\n"
        _seed_state(tmp_dir, seed)
        _patch(monkeypatch, tmp_dir, {"prompt": "the DESIGNATION of this role"})

        phase_transition.main()
        # Word-boundary match keeps the section unchanged.
        assert _read_state(tmp_dir) == seed


# ---------------------------------------------------------------------------
# Section mechanics — create / replace / preserve siblings
# ---------------------------------------------------------------------------


class TestSectionMechanics:
    def test_section_created_when_missing(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _seed_state(tmp_dir, "# Snapshot\n\n## Files Modified\n- `a.py`\n")
        _patch(monkeypatch, tmp_dir, {"prompt": "Now in OBJECTIVE"})

        phase_transition.main()
        text = _read_state(tmp_dir)
        assert "## Current Phase\nOBJECTIVE" in text
        # Sibling preserved.
        assert "## Files Modified" in text
        assert "- `a.py`" in text

    def test_section_body_replaced_in_place(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _seed_state(
            tmp_dir,
            "# Snapshot\n\n## Current Phase\nDESIGN\n\n## Files Modified\n- `a.py`\n",
        )
        _patch(monkeypatch, tmp_dir, {"prompt": "moving to IMPLEMENT now"})

        phase_transition.main()
        text = _read_state(tmp_dir)
        assert "## Current Phase\nIMPLEMENT" in text
        assert "DESIGN" not in text.split("## Files Modified")[0]
        assert "- `a.py`" in text  # Sibling preserved.

    def test_idempotent_when_phase_unchanged(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seed = "## Current Phase\nVALIDATE\n"
        _seed_state(tmp_dir, seed)
        _patch(monkeypatch, tmp_dir, {"prompt": "running VALIDATE checks"})

        phase_transition.main()
        # File unchanged.
        assert _read_state(tmp_dir) == seed

    def test_multi_line_existing_body_replaced_to_single_line(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _seed_state(
            tmp_dir,
            "## Current Phase\nDESIGN\n(extra notes that should be replaced)\n",
        )
        _patch(monkeypatch, tmp_dir, {"prompt": "now COMMIT"})

        phase_transition.main()
        text = _read_state(tmp_dir)
        assert "## Current Phase\nCOMMIT" in text
        assert "extra notes" not in text


# ---------------------------------------------------------------------------
# Prompt-key handling
# ---------------------------------------------------------------------------


class TestPromptKeys:
    @pytest.mark.parametrize("key", ["prompt", "user_prompt", "message"])
    def test_each_recognised_key(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch, key: str
    ) -> None:
        _seed_state(tmp_dir, "## Current Phase\nGAP\n")
        _patch(monkeypatch, tmp_dir, {key: "go to DESIGN"})

        phase_transition.main()
        assert "## Current Phase\nDESIGN" in _read_state(tmp_dir)

    def test_first_non_empty_key_wins(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _seed_state(tmp_dir, "## Current Phase\nGAP\n")
        _patch(
            monkeypatch,
            tmp_dir,
            {"prompt": "DESIGN", "user_prompt": "IMPLEMENT", "message": "VALIDATE"},
        )

        phase_transition.main()
        assert "## Current Phase\nDESIGN" in _read_state(tmp_dir)


# ---------------------------------------------------------------------------
# Fail-open / no-op cases
# ---------------------------------------------------------------------------


class TestNoOp:
    def test_no_phase_token_in_prompt(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seed = "## Current Phase\nDESIGN\n"
        _seed_state(tmp_dir, seed)
        _patch(monkeypatch, tmp_dir, {"prompt": "regular english with no phase tokens"})

        phase_transition.main()
        assert _read_state(tmp_dir) == seed

    def test_missing_state_file_is_no_op(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch(monkeypatch, tmp_dir, {"prompt": "moving to IMPLEMENT"})

        assert phase_transition.main() == 0
        # Hook never bootstraps the file.
        assert not (tmp_dir / _STATE_FILENAME).exists()

    def test_empty_prompt_field(self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        seed = "## Current Phase\nGAP\n"
        _seed_state(tmp_dir, seed)
        _patch(monkeypatch, tmp_dir, {"prompt": "   "})

        phase_transition.main()
        assert _read_state(tmp_dir) == seed

    def test_non_string_prompt(self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        seed = "## Current Phase\nGAP\n"
        _seed_state(tmp_dir, seed)
        _patch(monkeypatch, tmp_dir, {"prompt": 42})

        phase_transition.main()
        assert _read_state(tmp_dir) == seed

    def test_empty_stdin(self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        seed = "## Current Phase\nGAP\n"
        _seed_state(tmp_dir, seed)
        _patch(monkeypatch, tmp_dir, payload=None)

        assert phase_transition.main() == 0
        assert _read_state(tmp_dir) == seed
