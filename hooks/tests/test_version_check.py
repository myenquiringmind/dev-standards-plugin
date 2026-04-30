"""Tests for hooks/version_check.py."""

from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from hooks import version_check
from hooks._hook_shared import VERSION_CHECK_INTERVAL_SECONDS

_CACHE_FILENAME = "version-check.state.json"
_PLUGIN_MANIFEST_REL = Path(".claude-plugin") / "plugin.json"


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    project_dir: Path,
    memory_dir: Path | None = None,
    *,
    payload: dict[str, Any] | None = None,
    fixed_time: float = 1_000_000.0,
    marketplace: Path | None = None,
) -> None:
    body = json.dumps(payload) if payload is not None else ""
    monkeypatch.setattr(sys, "stdin", StringIO(body))
    monkeypatch.setattr(version_check, "get_project_dir", lambda: project_dir)
    monkeypatch.setattr(version_check, "get_memory_dir", lambda _d: memory_dir or project_dir)
    monkeypatch.setattr("time.time", lambda: fixed_time)
    if marketplace is None:
        monkeypatch.delenv("DSP_MARKETPLACE_CLONE", raising=False)
    else:
        monkeypatch.setenv("DSP_MARKETPLACE_CLONE", str(marketplace))


def _seed_manifest(directory: Path, version: str, *, repo: str | None = None) -> Path:
    """Write a minimal plugin.json under ``directory/.claude-plugin/``."""
    target = directory / _PLUGIN_MANIFEST_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {"name": "dev-standards", "version": version}
    if repo is not None:
        payload["repository"] = repo
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


def _read_cache(memory_dir: Path) -> dict[str, Any]:
    raw = json.loads((memory_dir / _CACHE_FILENAME).read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return raw


# ---------------------------------------------------------------------------
# Cache freshness — short-circuits when fresh
# ---------------------------------------------------------------------------


class TestCacheFreshness:
    def test_fresh_cache_short_circuits(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _seed_manifest(tmp_dir, "2.0.0")
        existing_cache = {
            "schema": "1.0.0",
            "checked_at_epoch": 1_000_000.0,
            "checked_at": "2026-04-28T00:00:00Z",
            "installed_version": "1.0.0",
            "marketplace_version": "1.0.0",
            "update_available": False,
        }
        (tmp_dir / _CACHE_FILENAME).write_text(json.dumps(existing_cache), encoding="utf-8")
        # 1 hour later — within the 24h window.
        _patch(monkeypatch, tmp_dir, fixed_time=1_000_000.0 + 3600)

        assert version_check.main() == 0
        # Cache untouched.
        assert _read_cache(tmp_dir) == existing_cache

    def test_stale_cache_triggers_recheck(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _seed_manifest(tmp_dir, "2.0.0")
        old_cache = {
            "schema": "1.0.0",
            "checked_at_epoch": 1_000_000.0,
            "checked_at": "2026-04-27T00:00:00Z",
            "installed_version": "1.0.0",
            "marketplace_version": "1.0.0",
            "update_available": False,
        }
        (tmp_dir / _CACHE_FILENAME).write_text(json.dumps(old_cache), encoding="utf-8")
        # Past the 24h window.
        later = 1_000_000.0 + VERSION_CHECK_INTERVAL_SECONDS + 1
        _patch(monkeypatch, tmp_dir, fixed_time=later)

        assert version_check.main() == 0
        cache = _read_cache(tmp_dir)
        assert cache["installed_version"] == "2.0.0"
        assert cache["checked_at_epoch"] == later

    def test_missing_cache_runs_check(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _seed_manifest(tmp_dir, "2.0.0")
        _patch(monkeypatch, tmp_dir)

        assert version_check.main() == 0
        cache = _read_cache(tmp_dir)
        assert cache["installed_version"] == "2.0.0"

    def test_malformed_cache_runs_check(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _seed_manifest(tmp_dir, "2.0.0")
        (tmp_dir / _CACHE_FILENAME).write_text("{not json", encoding="utf-8")
        _patch(monkeypatch, tmp_dir)

        version_check.main()
        cache = _read_cache(tmp_dir)
        assert cache["installed_version"] == "2.0.0"


# ---------------------------------------------------------------------------
# Comparison — semver-aware
# ---------------------------------------------------------------------------


class TestComparison:
    def test_remote_newer_logs_advisory(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _seed_manifest(tmp_dir, "2.0.0")
        market = tmp_dir / "marketplace"
        _seed_manifest(market, "2.1.0")
        _patch(monkeypatch, tmp_dir, marketplace=market)

        version_check.main()

        err = capsys.readouterr().err
        assert "update available" in err
        assert "2.0.0" in err
        assert "2.1.0" in err
        assert _read_cache(tmp_dir)["update_available"] is True

    def test_same_version_no_advisory(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _seed_manifest(tmp_dir, "2.0.0")
        market = tmp_dir / "marketplace"
        _seed_manifest(market, "2.0.0")
        _patch(monkeypatch, tmp_dir, marketplace=market)

        version_check.main()

        assert capsys.readouterr().err == ""
        assert _read_cache(tmp_dir)["update_available"] is False

    def test_remote_older_no_advisory(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Local development — installed is ahead of last published version.
        _seed_manifest(tmp_dir, "2.1.0")
        market = tmp_dir / "marketplace"
        _seed_manifest(market, "2.0.0")
        _patch(monkeypatch, tmp_dir, marketplace=market)

        version_check.main()

        assert capsys.readouterr().err == ""
        assert _read_cache(tmp_dir)["update_available"] is False

    def test_semver_double_digit_minor_compares_correctly(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # 2.10.0 must be greater than 2.9.0 (numeric, not lexicographic).
        _seed_manifest(tmp_dir, "2.9.0")
        market = tmp_dir / "marketplace"
        _seed_manifest(market, "2.10.0")
        _patch(monkeypatch, tmp_dir, marketplace=market)

        version_check.main()
        assert _read_cache(tmp_dir)["update_available"] is True


# ---------------------------------------------------------------------------
# Marketplace resolution
# ---------------------------------------------------------------------------


class TestMarketplaceResolution:
    def test_env_override_directory(self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _seed_manifest(tmp_dir, "2.0.0")
        market = tmp_dir / "alt-marketplace"
        _seed_manifest(market, "2.5.0")
        # Override points at the directory; helper appends .claude-plugin/plugin.json.
        _patch(monkeypatch, tmp_dir, marketplace=market)

        version_check.main()
        assert _read_cache(tmp_dir)["marketplace_version"] == "2.5.0"

    def test_env_override_full_file_path(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _seed_manifest(tmp_dir, "2.0.0")
        market = tmp_dir / "alt-marketplace"
        manifest = _seed_manifest(market, "2.5.0")
        # Override is a full file path — passed through unchanged.
        _patch(monkeypatch, tmp_dir, marketplace=manifest)

        version_check.main()
        assert _read_cache(tmp_dir)["marketplace_version"] == "2.5.0"

    def test_missing_marketplace_silent_no_advisory(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _seed_manifest(tmp_dir, "2.0.0")
        # Override points at a non-existent directory.
        _patch(monkeypatch, tmp_dir, marketplace=tmp_dir / "does-not-exist")

        version_check.main()

        assert capsys.readouterr().err == ""
        cache = _read_cache(tmp_dir)
        assert cache["installed_version"] == "2.0.0"
        assert cache["marketplace_version"] == ""
        assert cache["update_available"] is False

    def test_repository_url_drives_default_path(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # No env override — derive the marketplace path from ``repository``.
        _seed_manifest(
            tmp_dir,
            "2.0.0",
            repo="https://github.com/myenquiringmind/dev-standards-plugin",
        )
        # Without an actual clone at that path the lookup will simply return
        # an empty marketplace_version — but we should not crash.
        _patch(monkeypatch, tmp_dir)
        # Force HOME so we know the lookup target doesn't exist on this system.
        monkeypatch.setenv("HOME", str(tmp_dir / "fake-home"))

        version_check.main()
        cache = _read_cache(tmp_dir)
        assert cache["installed_version"] == "2.0.0"
        assert cache["marketplace_version"] == ""

    def test_malformed_repository_url_silent(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _seed_manifest(tmp_dir, "2.0.0", repo="not-a-github-url")
        _patch(monkeypatch, tmp_dir)

        assert version_check.main() == 0
        cache = _read_cache(tmp_dir)
        assert cache["marketplace_version"] == ""


# ---------------------------------------------------------------------------
# Resilience
# ---------------------------------------------------------------------------


class TestResilience:
    def test_missing_installed_manifest_silent(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # No plugin.json at all.
        _patch(monkeypatch, tmp_dir)

        assert version_check.main() == 0
        cache = _read_cache(tmp_dir)
        assert cache["installed_version"] == ""
        assert cache["update_available"] is False

    def test_malformed_installed_manifest_silent(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        manifest_path = tmp_dir / _PLUGIN_MANIFEST_REL
        manifest_path.parent.mkdir(parents=True)
        manifest_path.write_text("{not json", encoding="utf-8")
        _patch(monkeypatch, tmp_dir)

        version_check.main()
        cache = _read_cache(tmp_dir)
        assert cache["installed_version"] == ""

    def test_missing_version_field_silent(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        manifest_path = tmp_dir / _PLUGIN_MANIFEST_REL
        manifest_path.parent.mkdir(parents=True)
        manifest_path.write_text(json.dumps({"name": "dev-standards"}), encoding="utf-8")
        _patch(monkeypatch, tmp_dir)

        assert version_check.main() == 0
        assert _read_cache(tmp_dir)["installed_version"] == ""

    def test_empty_stdin(self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _seed_manifest(tmp_dir, "2.0.0")
        _patch(monkeypatch, tmp_dir, payload=None)

        assert version_check.main() == 0
        assert (tmp_dir / _CACHE_FILENAME).exists()
