"""Tests for hooks/_memory.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from hooks import _memory


class TestFrameworkMemoryDir:
    def test_plugin_data_env_var_wins(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plugin_root = tmp_dir / "plugin-data"
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(plugin_root))
        # Set the project env var too — plugin-data must take priority.
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_dir / "irrelevant"))

        result = _memory.framework_memory_dir()

        assert result == plugin_root.resolve() / "framework-memory"

    def test_project_dir_env_var_when_no_plugin_data(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("CLAUDE_PLUGIN_DATA", raising=False)
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_dir))

        result = _memory.framework_memory_dir()

        assert result == tmp_dir.resolve() / ".claude" / "framework-memory"

    def test_falls_back_to_get_project_dir(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("CLAUDE_PLUGIN_DATA", raising=False)
        monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
        monkeypatch.setattr(_memory, "get_project_dir", lambda: tmp_dir)

        result = _memory.framework_memory_dir()

        assert result == tmp_dir / ".claude" / "framework-memory"


class TestIncidentDir:
    def test_env_override_wins(self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLAUDE_INCIDENTS_DIR", str(tmp_dir / "explicit-incidents"))
        # Even with PLUGIN_DATA set, the per-tier env var wins for backwards
        # compatibility with Phase 2 _incident.py and its test fixtures.
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_dir / "plugin"))

        result = _memory.incident_dir()

        assert result == (tmp_dir / "explicit-incidents").resolve()

    def test_falls_under_framework_memory_dir(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("CLAUDE_INCIDENTS_DIR", raising=False)
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_dir))

        result = _memory.incident_dir()

        assert result == tmp_dir.resolve() / "framework-memory" / "incidents"


class TestTelemetryDir:
    def test_env_override_wins(self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLAUDE_TELEMETRY_DIR", str(tmp_dir / "explicit-telemetry"))
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_dir / "plugin"))

        result = _memory.telemetry_dir()

        assert result == (tmp_dir / "explicit-telemetry").resolve()

    def test_falls_under_framework_memory_dir(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("CLAUDE_TELEMETRY_DIR", raising=False)
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_dir))

        result = _memory.telemetry_dir()

        assert result == tmp_dir.resolve() / "framework-memory" / "telemetry"


class TestGraphHistoryDir:
    def test_returns_subdir_under_framework_memory(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_dir))

        result = _memory.graph_history_dir()

        assert result == tmp_dir.resolve() / "framework-memory" / "graph-history"

    def test_no_env_var_override(self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # graph-history has no per-subdir env var override; setting any other
        # env var should not affect its resolution.
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_dir))
        monkeypatch.setenv("CLAUDE_INCIDENTS_DIR", str(tmp_dir / "irrelevant"))
        monkeypatch.setenv("CLAUDE_TELEMETRY_DIR", str(tmp_dir / "irrelevant2"))

        result = _memory.graph_history_dir()

        assert result == tmp_dir.resolve() / "framework-memory" / "graph-history"


class TestQualityScoresPath:
    def test_returns_file_under_framework_memory(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_dir))

        result = _memory.quality_scores_path()

        assert result == tmp_dir.resolve() / "framework-memory" / "quality-scores.json"


class TestAllSubdirs:
    def test_returns_every_owned_subdir(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_dir))
        monkeypatch.delenv("CLAUDE_INCIDENTS_DIR", raising=False)
        monkeypatch.delenv("CLAUDE_TELEMETRY_DIR", raising=False)

        result = _memory.all_subdirs()

        framework = tmp_dir.resolve() / "framework-memory"
        assert set(result) == {
            framework / "incidents",
            framework / "telemetry",
            framework / "graph-history",
            framework / "principles",
            framework / "retrospectives",
        }

    def test_includes_phase_10_reservations(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """principles/ and retrospectives/ are reserved for Phase 10 but
        all_subdirs() returns them so the SessionStart hook creates them
        defensively — directory layout must be stable across phases."""
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_dir))
        monkeypatch.delenv("CLAUDE_INCIDENTS_DIR", raising=False)
        monkeypatch.delenv("CLAUDE_TELEMETRY_DIR", raising=False)

        names = {p.name for p in _memory.all_subdirs()}

        assert "principles" in names
        assert "retrospectives" in names
