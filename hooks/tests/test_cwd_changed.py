"""Tests for hooks/cwd_changed.py."""

from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from hooks import cwd_changed, detect_language

_TARGET = ".language_profile.json"


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    project_dir: Path,
    payload: dict[str, Any] | None = None,
) -> None:
    body = json.dumps(payload) if payload is not None else ""
    monkeypatch.setattr(sys, "stdin", StringIO(body))
    monkeypatch.setattr(cwd_changed, "get_project_dir", lambda: project_dir)
    # detect_and_stamp uses its own get_project_dir reference; intercept that too
    # so the helper doesn't fall through to the real project root.
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
# Force-overwrite — the headline behaviour
# ---------------------------------------------------------------------------


class TestForceOverwrite:
    def test_existing_stamp_overwritten(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pre-seed an out-of-date stamp.
        stale = '{"name": "stale", "priority": "P3"}\n'
        (tmp_dir / _TARGET).write_text(stale, encoding="utf-8")
        # Profile + marker so the rerun has something to detect.
        (tmp_dir / "pyproject.toml").write_text("", encoding="utf-8")
        _seed_profile(tmp_dir, "python", markers=["pyproject.toml"])
        _patch(monkeypatch, tmp_dir)

        assert cwd_changed.main() == 0

        # Stamp was overwritten — old name gone, new detection in place.
        text = (tmp_dir / _TARGET).read_text(encoding="utf-8")
        assert "stale" not in text
        rec = _read_record(tmp_dir)
        assert rec["name"] == "python"

    def test_no_match_overwrites_with_sentinel(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Stale stamp claims a real profile, but no markers exist now.
        existing = '{"name": "python", "priority": "P0"}\n'
        (tmp_dir / _TARGET).write_text(existing, encoding="utf-8")
        _seed_profile(tmp_dir, "python", markers=["pyproject.toml"])
        _patch(monkeypatch, tmp_dir)

        cwd_changed.main()

        rec = _read_record(tmp_dir)
        assert rec["name"] == ""
        assert rec["priority"] == ""

    def test_creates_stamp_when_absent(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # No prior stamp at all.
        (tmp_dir / "pyproject.toml").write_text("", encoding="utf-8")
        _seed_profile(tmp_dir, "python", markers=["pyproject.toml"])
        _patch(monkeypatch, tmp_dir)

        cwd_changed.main()
        assert (tmp_dir / _TARGET).exists()
        assert _read_record(tmp_dir)["name"] == "python"


# ---------------------------------------------------------------------------
# Resilience
# ---------------------------------------------------------------------------


class TestResilience:
    def test_empty_stdin_still_runs(self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _seed_profile(tmp_dir, "python", markers=["pyproject.toml"])
        (tmp_dir / "pyproject.toml").write_text("", encoding="utf-8")
        _patch(monkeypatch, tmp_dir, payload=None)

        assert cwd_changed.main() == 0
        assert _read_record(tmp_dir)["name"] == "python"

    def test_arbitrary_payload_ignored(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The hook does not consume payload fields — anything CC sends
        # should pass through without affecting behaviour.
        _seed_profile(tmp_dir, "python", markers=["pyproject.toml"])
        (tmp_dir / "pyproject.toml").write_text("", encoding="utf-8")
        _patch(
            monkeypatch,
            tmp_dir,
            {"new_cwd": "/some/path", "old_cwd": "/other/path"},
        )

        assert cwd_changed.main() == 0
        assert _read_record(tmp_dir)["name"] == "python"


# ---------------------------------------------------------------------------
# Integration with the shared helper
# ---------------------------------------------------------------------------


class TestDetectAndStampSharedHelper:
    """Pin the contract that ``cwd_changed`` relies on."""

    def test_force_true_overwrites_existing(self, tmp_dir: Path) -> None:
        (tmp_dir / _TARGET).write_text('{"name": "stale"}\n', encoding="utf-8")
        (tmp_dir / "pyproject.toml").write_text("", encoding="utf-8")
        _seed_profile(tmp_dir, "python", markers=["pyproject.toml"])

        detect_language.detect_and_stamp(tmp_dir, force=True)

        rec = _read_record(tmp_dir)
        assert rec["name"] == "python"

    def test_force_false_preserves_existing(self, tmp_dir: Path) -> None:
        existing = '{"name": "preserved"}\n'
        (tmp_dir / _TARGET).write_text(existing, encoding="utf-8")
        (tmp_dir / "pyproject.toml").write_text("", encoding="utf-8")
        _seed_profile(tmp_dir, "python", markers=["pyproject.toml"])

        detect_language.detect_and_stamp(tmp_dir, force=False)

        # Existing file untouched.
        assert (tmp_dir / _TARGET).read_text(encoding="utf-8") == existing
