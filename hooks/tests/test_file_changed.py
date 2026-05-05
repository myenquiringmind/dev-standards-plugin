"""Tests for hooks/file_changed.py."""

from __future__ import annotations

import json
import re
import shutil
import sys
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from hooks import _memory, file_changed

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    project_dir: Path,
    payload: dict[str, Any],
) -> None:
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(payload)))
    monkeypatch.setattr(file_changed, "get_project_dir", lambda: project_dir)


def _seed_project(tmp_dir: Path) -> Path:
    """Build a minimal project layout: schemas/ + config/."""
    (tmp_dir / "schemas").mkdir()
    shutil.copy(
        _PROJECT_ROOT / "schemas" / "graph-registry.schema.json",
        tmp_dir / "schemas" / "graph-registry.schema.json",
    )
    shutil.copy(
        _PROJECT_ROOT / "schemas" / "profile.schema.json",
        tmp_dir / "schemas" / "profile.schema.json",
    )
    (tmp_dir / "config" / "profiles").mkdir(parents=True)
    return tmp_dir


def _valid_registry() -> dict[str, Any]:
    return {
        "version": "1.0.0",
        "generated_at": "2026-04-28T00:00:00Z",
        "nodes": [],
        "edges": [],
    }


def _valid_profile() -> dict[str, Any]:
    """Minimal valid profile matching the real schema shape."""
    return {
        "name": "python",
        "priority": "P0",
        "detection": {
            "markers": ["pyproject.toml"],
            "extensions": [".py"],
        },
        "tools": {
            "linter": {"command": "ruff check", "extensions": [".py"]},
            "formatter": {"command": "ruff format", "extensions": [".py"]},
        },
        "conventions": {
            "fileNaming": "snake_case",
        },
        "validationSteps": ["ruff-check"],
    }


# ---------------------------------------------------------------------------
# Off-watch / missing payload — silent no-ops
# ---------------------------------------------------------------------------


class TestNoOpPaths:
    def test_no_path_in_payload_returns_zero(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _seed_project(tmp_dir)
        _patch(monkeypatch, tmp_dir, {})

        rc = file_changed.main()
        captured = capsys.readouterr()

        assert rc == 0
        assert captured.err == ""

    def test_off_watch_path_is_no_op(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _seed_project(tmp_dir)
        target = tmp_dir / "src" / "main.py"
        target.parent.mkdir(parents=True)
        target.write_text("x = 1", encoding="utf-8")
        _patch(monkeypatch, tmp_dir, {"path": str(target)})

        rc = file_changed.main()
        assert rc == 0
        assert capsys.readouterr().err == ""

    def test_outside_project_path_is_no_op(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        tmp_path_factory: pytest.TempPathFactory,
    ) -> None:
        _seed_project(tmp_dir)
        outsider = tmp_path_factory.mktemp("outside") / "graph-registry.json"
        outsider.write_text(json.dumps(_valid_registry()), encoding="utf-8")

        _patch(monkeypatch, tmp_dir, {"path": str(outsider)})

        rc = file_changed.main()
        assert rc == 0
        assert capsys.readouterr().err == ""

    def test_relative_path_resolved_against_project(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _seed_project(tmp_dir)
        registry = tmp_dir / "config" / "graph-registry.json"
        registry.write_text(json.dumps(_valid_registry()), encoding="utf-8")

        # Pass relative path; hook should resolve it under project_dir.
        _patch(monkeypatch, tmp_dir, {"path": "config/graph-registry.json"})

        rc = file_changed.main()
        assert rc == 0
        assert capsys.readouterr().err == ""


# ---------------------------------------------------------------------------
# Watched paths: valid → silent; invalid → stderr
# ---------------------------------------------------------------------------


class TestWatchedPaths:
    def test_valid_graph_registry_is_silent(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _seed_project(tmp_dir)
        registry = tmp_dir / "config" / "graph-registry.json"
        registry.write_text(json.dumps(_valid_registry()), encoding="utf-8")
        _patch(monkeypatch, tmp_dir, {"path": str(registry)})

        rc = file_changed.main()
        assert rc == 0
        assert capsys.readouterr().err == ""

    def test_invalid_graph_registry_logs_error(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _seed_project(tmp_dir)
        registry = tmp_dir / "config" / "graph-registry.json"
        bad = _valid_registry()
        del bad["version"]  # required field
        registry.write_text(json.dumps(bad), encoding="utf-8")
        _patch(monkeypatch, tmp_dir, {"path": str(registry)})

        rc = file_changed.main()
        err = capsys.readouterr().err

        assert rc == 0
        assert "schema violation" in err
        assert "graph-registry.json" in err

    def test_valid_profile_is_silent(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _seed_project(tmp_dir)
        profile = tmp_dir / "config" / "profiles" / "python.json"
        profile.write_text(json.dumps(_valid_profile()), encoding="utf-8")
        _patch(monkeypatch, tmp_dir, {"path": str(profile)})

        rc = file_changed.main()
        assert rc == 0
        assert capsys.readouterr().err == ""

    def test_invalid_profile_logs_error(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _seed_project(tmp_dir)
        profile = tmp_dir / "config" / "profiles" / "broken.json"
        bad = _valid_profile()
        bad["priority"] = "PX"  # invalid enum
        profile.write_text(json.dumps(bad), encoding="utf-8")
        _patch(monkeypatch, tmp_dir, {"path": str(profile)})

        rc = file_changed.main()
        err = capsys.readouterr().err

        assert rc == 0
        assert "schema violation" in err
        assert "broken.json" in err
        assert "priority" in err

    def test_nested_profile_path_is_not_watched(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Only direct children of config/profiles/ are watched.
        _seed_project(tmp_dir)
        nested = tmp_dir / "config" / "profiles" / "deep" / "x.json"
        nested.parent.mkdir(parents=True)
        nested.write_text("{}", encoding="utf-8")
        _patch(monkeypatch, tmp_dir, {"path": str(nested)})

        rc = file_changed.main()
        assert rc == 0
        assert capsys.readouterr().err == ""


# ---------------------------------------------------------------------------
# Fail-open paths
# ---------------------------------------------------------------------------


class TestFailOpen:
    def test_missing_file_logs_and_returns_zero(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _seed_project(tmp_dir)
        registry = tmp_dir / "config" / "graph-registry.json"
        # File does not exist.
        _patch(monkeypatch, tmp_dir, {"path": str(registry)})

        rc = file_changed.main()
        err = capsys.readouterr().err

        assert rc == 0
        assert "missing" in err

    def test_malformed_json_logs_and_returns_zero(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _seed_project(tmp_dir)
        registry = tmp_dir / "config" / "graph-registry.json"
        registry.write_text("{not json", encoding="utf-8")
        _patch(monkeypatch, tmp_dir, {"path": str(registry)})

        rc = file_changed.main()
        err = capsys.readouterr().err

        assert rc == 0
        assert "not valid JSON" in err

    def test_missing_schema_logs_and_returns_zero(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Project layout without the schemas dir.
        (tmp_dir / "config" / "profiles").mkdir(parents=True)
        registry = tmp_dir / "config" / "graph-registry.json"
        registry.write_text(json.dumps(_valid_registry()), encoding="utf-8")
        _patch(monkeypatch, tmp_dir, {"path": str(registry)})

        rc = file_changed.main()
        err = capsys.readouterr().err

        assert rc == 0
        assert "schema missing" in err

    def test_empty_stdin_is_no_op(self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _seed_project(tmp_dir)
        monkeypatch.setattr(sys, "stdin", StringIO(""))
        monkeypatch.setattr(file_changed, "get_project_dir", lambda: tmp_dir)

        assert file_changed.main() == 0

    def test_alt_payload_field_file_path(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _seed_project(tmp_dir)
        registry = tmp_dir / "config" / "graph-registry.json"
        registry.write_text(json.dumps(_valid_registry()), encoding="utf-8")
        _patch(monkeypatch, tmp_dir, {"file_path": str(registry)})

        assert file_changed.main() == 0


# ---------------------------------------------------------------------------
# Phase 4 stream 3 — graph-history snapshot
# ---------------------------------------------------------------------------


def _setup_snapshot_test(
    tmp_dir: Path, monkeypatch: pytest.MonkeyPatch, payload: dict[str, Any]
) -> Path:
    """Wire the hook + force ``graph_history_dir`` under *tmp_dir*.

    Returns the expected ``framework-memory/graph-history/`` path.
    """
    _seed_project(tmp_dir)
    # Clear env vars so framework_memory_dir falls back to get_project_dir().
    monkeypatch.delenv("CLAUDE_PLUGIN_DATA", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.setattr(_memory, "get_project_dir", lambda: tmp_dir)
    _patch(monkeypatch, tmp_dir, payload)
    return tmp_dir / ".claude" / "framework-memory" / "graph-history"


class TestSnapshotFilename:
    """`_snapshot_filename` produces a Windows-safe ISO timestamp."""

    def test_filename_shape_matches_iso_with_millis(self) -> None:
        from datetime import UTC, datetime

        name = file_changed._snapshot_filename(datetime(2026, 5, 5, 12, 34, 56, 789_000, UTC))
        assert name == "2026-05-05T12-34-56-789Z.json"

    def test_filename_pads_microseconds_to_three_digits(self) -> None:
        from datetime import UTC, datetime

        # 7_000 µs == 7 ms — must render as "007", not "7".
        name = file_changed._snapshot_filename(datetime(2026, 5, 5, 0, 0, 0, 7_000, UTC))
        assert name.endswith("-007Z.json")

    def test_filename_uses_only_filesystem_safe_chars(self) -> None:
        from datetime import UTC, datetime

        name = file_changed._snapshot_filename(datetime(2026, 5, 5, 12, 34, 56, 0, UTC))
        # ":" is invalid on Windows; "." is reserved for the extension.
        assert ":" not in name
        assert name.count(".") == 1  # only the .json extension


class TestRegistrySnapshot:
    """Every change to ``config/graph-registry.json`` snapshots to graph-history/."""

    def test_valid_registry_change_creates_snapshot(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        registry = tmp_dir / "config" / "graph-registry.json"
        history_dir = _setup_snapshot_test(tmp_dir, monkeypatch, {"path": str(registry)})
        content = json.dumps(_valid_registry(), indent=2)
        registry.write_text(content, encoding="utf-8")

        rc = file_changed.main()

        assert rc == 0
        snapshots = list(history_dir.glob("*.json"))
        assert len(snapshots) == 1
        assert snapshots[0].read_text(encoding="utf-8") == content

    def test_invalid_registry_still_snapshots(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Phase 10 retrospectives need to see the broken state, not just the fix.
        registry = tmp_dir / "config" / "graph-registry.json"
        history_dir = _setup_snapshot_test(tmp_dir, monkeypatch, {"path": str(registry)})
        bad = _valid_registry()
        del bad["version"]
        content = json.dumps(bad)
        registry.write_text(content, encoding="utf-8")

        rc = file_changed.main()

        err = capsys.readouterr().err
        assert rc == 0
        assert "schema violation" in err  # validation still surfaces the break
        snapshots = list(history_dir.glob("*.json"))
        assert len(snapshots) == 1
        assert snapshots[0].read_text(encoding="utf-8") == content

    def test_malformed_json_still_snapshots(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Snapshot reads the file as text, before JSON parse — bytes captured as-is.
        registry = tmp_dir / "config" / "graph-registry.json"
        history_dir = _setup_snapshot_test(tmp_dir, monkeypatch, {"path": str(registry)})
        registry.write_text("{not json", encoding="utf-8")

        rc = file_changed.main()

        err = capsys.readouterr().err
        assert rc == 0
        assert "not valid JSON" in err  # validation still complains
        snapshots = list(history_dir.glob("*.json"))
        assert len(snapshots) == 1
        assert snapshots[0].read_text(encoding="utf-8") == "{not json"

    def test_profile_change_does_not_snapshot(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # graph-history is for the registry only; profiles are out of scope.
        profile = tmp_dir / "config" / "profiles" / "python.json"
        history_dir = _setup_snapshot_test(tmp_dir, monkeypatch, {"path": str(profile)})
        profile.write_text(json.dumps(_valid_profile()), encoding="utf-8")

        rc = file_changed.main()

        assert rc == 0
        # Either the dir was never created, or it exists and is empty.
        assert not history_dir.exists() or not list(history_dir.iterdir())

    def test_off_watch_path_does_not_snapshot(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_dir / "src" / "main.py"
        target.parent.mkdir(parents=True)
        target.write_text("x = 1", encoding="utf-8")
        history_dir = _setup_snapshot_test(tmp_dir, monkeypatch, {"path": str(target)})

        rc = file_changed.main()

        assert rc == 0
        assert not history_dir.exists() or not list(history_dir.iterdir())

    def test_snapshot_filename_in_history_is_iso_pattern(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        registry = tmp_dir / "config" / "graph-registry.json"
        history_dir = _setup_snapshot_test(tmp_dir, monkeypatch, {"path": str(registry)})
        registry.write_text(json.dumps(_valid_registry()), encoding="utf-8")

        rc = file_changed.main()
        assert rc == 0

        snapshots = list(history_dir.glob("*.json"))
        assert len(snapshots) == 1
        # YYYY-MM-DDTHH-MM-SS-mmmZ.json
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}-\d{3}Z\.json", snapshots[0].name)

    def test_snapshot_io_failure_is_advisory(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # When atomic_write raises OSError, the hook still returns 0.
        registry = tmp_dir / "config" / "graph-registry.json"
        history_dir = _setup_snapshot_test(tmp_dir, monkeypatch, {"path": str(registry)})
        registry.write_text(json.dumps(_valid_registry()), encoding="utf-8")

        def _boom(target: Path, content: str) -> None:
            raise OSError("simulated disk full")

        monkeypatch.setattr(file_changed, "atomic_write", _boom)

        rc = file_changed.main()
        err = capsys.readouterr().err

        assert rc == 0
        assert "could not write graph-history snapshot" in err
        # Validation still ran on the (valid) content — no schema-violation noise.
        assert "schema violation" not in err
        # Nothing landed on disk.
        assert not history_dir.exists() or not list(history_dir.iterdir())
