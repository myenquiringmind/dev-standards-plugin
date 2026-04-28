"""Tests for hooks/detect_language.py."""

from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from hooks import detect_language

_TARGET = ".language_profile.json"


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    project_dir: Path,
    payload: dict[str, Any] | None = None,
) -> None:
    body = json.dumps(payload) if payload is not None else ""
    monkeypatch.setattr(sys, "stdin", StringIO(body))
    monkeypatch.setattr(detect_language, "get_project_dir", lambda: project_dir)


def _seed_profile(
    project_dir: Path,
    name: str,
    *,
    priority: str = "P0",
    markers: list[str] | None = None,
) -> Path:
    profiles_dir = project_dir / "config" / "profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "name": name,
        "priority": priority,
        "detection": {
            "markers": markers or [f"{name}.marker"],
            "extensions": [f".{name[:2]}"],
        },
        "tools": {},
        "validationSteps": [],
        "conventions": {},
    }
    path = profiles_dir / f"{name}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _read_record(project_dir: Path) -> dict[str, Any]:
    raw = json.loads((project_dir / _TARGET).read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return raw


# ---------------------------------------------------------------------------
# Idempotence — existing file is never overwritten
# ---------------------------------------------------------------------------


class TestIdempotence:
    def test_existing_file_is_preserved(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        existing = '{"name": "from-prior-session", "priority": "P0"}\n'
        (tmp_dir / _TARGET).write_text(existing, encoding="utf-8")
        # Even though python.json would match if pyproject.toml is present,
        # the existing stamp wins.
        (tmp_dir / "pyproject.toml").write_text("", encoding="utf-8")
        _seed_profile(tmp_dir, "python", markers=["pyproject.toml"])
        _patch(monkeypatch, tmp_dir)

        assert detect_language.main() == 0
        assert (tmp_dir / _TARGET).read_text(encoding="utf-8") == existing


# ---------------------------------------------------------------------------
# Detection — match + priority ordering
# ---------------------------------------------------------------------------


class TestDetection:
    def test_writes_record_when_marker_present(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_dir / "pyproject.toml").write_text("", encoding="utf-8")
        _seed_profile(tmp_dir, "python", markers=["pyproject.toml"])
        _patch(monkeypatch, tmp_dir)

        assert detect_language.main() == 0
        rec = _read_record(tmp_dir)
        assert rec["name"] == "python"
        assert rec["priority"] == "P0"
        assert rec["markers_matched"] == ["pyproject.toml"]
        assert rec["schema"] == "1.0.0"
        assert rec["detected_at"].endswith("Z")

    def test_priority_p0_beats_p1(self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Both profiles match; the P0 one wins.
        (tmp_dir / "shared.marker").write_text("", encoding="utf-8")
        _seed_profile(tmp_dir, "alpha", priority="P1", markers=["shared.marker"])
        _seed_profile(tmp_dir, "beta", priority="P0", markers=["shared.marker"])
        _patch(monkeypatch, tmp_dir)

        detect_language.main()
        rec = _read_record(tmp_dir)
        assert rec["name"] == "beta"
        assert rec["priority"] == "P0"

    def test_alphabetical_tiebreak_within_same_priority(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_dir / "shared.marker").write_text("", encoding="utf-8")
        _seed_profile(tmp_dir, "zulu", priority="P0", markers=["shared.marker"])
        _seed_profile(tmp_dir, "alpha", priority="P0", markers=["shared.marker"])
        _patch(monkeypatch, tmp_dir)

        detect_language.main()
        assert _read_record(tmp_dir)["name"] == "alpha"

    def test_only_matching_markers_recorded(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_dir / "pyproject.toml").write_text("", encoding="utf-8")
        # ``setup.py`` is in the marker list but not on disk.
        _seed_profile(
            tmp_dir, "python", markers=["pyproject.toml", "setup.py", "requirements.txt"]
        )
        _patch(monkeypatch, tmp_dir)

        detect_language.main()
        rec = _read_record(tmp_dir)
        assert rec["markers_matched"] == ["pyproject.toml"]


# ---------------------------------------------------------------------------
# No-match sentinel
# ---------------------------------------------------------------------------


class TestNoMatch:
    def test_no_profiles_writes_sentinel(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # No profiles directory at all.
        _patch(monkeypatch, tmp_dir)

        assert detect_language.main() == 0
        rec = _read_record(tmp_dir)
        assert rec["name"] == ""
        assert rec["priority"] == ""
        assert rec["markers_matched"] == []

    def test_no_markers_match_writes_sentinel(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Profile exists but no markers present in project.
        _seed_profile(tmp_dir, "python", markers=["pyproject.toml"])
        _patch(monkeypatch, tmp_dir)

        detect_language.main()
        rec = _read_record(tmp_dir)
        assert rec["name"] == ""

    def test_sentinel_idempotent_on_next_run(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # First run writes the sentinel; subsequent runs must not re-scan.
        _seed_profile(tmp_dir, "python", markers=["pyproject.toml"])
        _patch(monkeypatch, tmp_dir)
        detect_language.main()
        first = (tmp_dir / _TARGET).read_text(encoding="utf-8")

        # Now the marker exists, but the sentinel should still survive.
        (tmp_dir / "pyproject.toml").write_text("", encoding="utf-8")
        detect_language.main()
        assert (tmp_dir / _TARGET).read_text(encoding="utf-8") == first


# ---------------------------------------------------------------------------
# Resilience — malformed profiles, OS errors, empty input
# ---------------------------------------------------------------------------


class TestResilience:
    def test_malformed_profile_is_skipped(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_dir / "pyproject.toml").write_text("", encoding="utf-8")
        # Place a malformed profile alongside a good one.
        (tmp_dir / "config" / "profiles").mkdir(parents=True)
        (tmp_dir / "config" / "profiles" / "broken.json").write_text("{not json", encoding="utf-8")
        _seed_profile(tmp_dir, "python", markers=["pyproject.toml"])
        _patch(monkeypatch, tmp_dir)

        detect_language.main()
        rec = _read_record(tmp_dir)
        assert rec["name"] == "python"

    def test_profile_missing_required_field_skipped(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_dir / "pyproject.toml").write_text("", encoding="utf-8")
        (tmp_dir / "config" / "profiles").mkdir(parents=True)
        # Missing ``priority``.
        (tmp_dir / "config" / "profiles" / "halfgood.json").write_text(
            json.dumps(
                {
                    "name": "halfgood",
                    "detection": {"markers": ["pyproject.toml"]},
                }
            ),
            encoding="utf-8",
        )
        _seed_profile(tmp_dir, "python", markers=["pyproject.toml"])
        _patch(monkeypatch, tmp_dir)

        detect_language.main()
        # Halfgood was skipped → python wins.
        assert _read_record(tmp_dir)["name"] == "python"

    def test_invalid_priority_skipped(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_dir / "pyproject.toml").write_text("", encoding="utf-8")
        _seed_profile(tmp_dir, "python", priority="P0", markers=["pyproject.toml"])
        _seed_profile(
            tmp_dir,
            "imposter",
            priority="P9",
            markers=["pyproject.toml"],
        )
        _patch(monkeypatch, tmp_dir)

        detect_language.main()
        # Imposter rejected on priority validation; python wins.
        assert _read_record(tmp_dir)["name"] == "python"

    def test_empty_stdin_returns_zero(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch(monkeypatch, tmp_dir, payload=None)
        assert detect_language.main() == 0
        # Sentinel still written.
        assert (tmp_dir / _TARGET).exists()
