"""Tests for hooks/config_change.py."""

from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from hooks import config_change

_LANGUAGE_PROFILE_CACHE = ".language_profile.json"
_VERSION_CHECK_CACHE = "version-check.state.json"


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    project_dir: Path,
    memory_dir: Path | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    body = json.dumps(payload) if payload is not None else ""
    monkeypatch.setattr(sys, "stdin", StringIO(body))
    monkeypatch.setattr(config_change, "get_project_dir", lambda: project_dir)
    monkeypatch.setattr(config_change, "get_memory_dir", lambda _d: memory_dir or project_dir)


def _seed_cache(path: Path, content: str = '{"stale": true}') -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Profile change → invalidate language-profile cache
# ---------------------------------------------------------------------------


class TestProfileChange:
    def test_profile_change_deletes_language_cache(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cache = tmp_dir / _LANGUAGE_PROFILE_CACHE
        _seed_cache(cache)
        # Path is given as a project-relative string.
        _patch(
            monkeypatch,
            tmp_dir,
            payload={"path": "config/profiles/python.json"},
        )

        assert config_change.main() == 0
        assert not cache.exists()

    def test_profile_change_with_absolute_path(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cache = tmp_dir / _LANGUAGE_PROFILE_CACHE
        _seed_cache(cache)
        target = tmp_dir / "config" / "profiles" / "javascript.json"
        target.parent.mkdir(parents=True)
        target.write_text("{}", encoding="utf-8")
        _patch(monkeypatch, tmp_dir, payload={"path": str(target)})

        config_change.main()
        assert not cache.exists()

    def test_missing_cache_is_silent_noop(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # No cache to delete; hook should still exit 0 and stay silent.
        _patch(
            monkeypatch,
            tmp_dir,
            payload={"path": "config/profiles/python.json"},
        )

        assert config_change.main() == 0
        assert capsys.readouterr().err == ""

    def test_nested_profile_path_not_watched(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Only direct children of ``config/profiles/`` count as watched.
        cache = tmp_dir / _LANGUAGE_PROFILE_CACHE
        _seed_cache(cache)
        _patch(
            monkeypatch,
            tmp_dir,
            payload={"path": "config/profiles/nested/inner.json"},
        )

        config_change.main()
        # Cache survives because the path is off-watch.
        assert cache.exists()


# ---------------------------------------------------------------------------
# Plugin manifest change → invalidate version-check cache
# ---------------------------------------------------------------------------


class TestManifestChange:
    def test_manifest_change_deletes_version_check_cache(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        memory = tmp_dir / "memory"
        memory.mkdir()
        cache = memory / _VERSION_CHECK_CACHE
        _seed_cache(cache)

        _patch(
            monkeypatch,
            tmp_dir,
            memory_dir=memory,
            payload={"path": ".claude-plugin/plugin.json"},
        )

        assert config_change.main() == 0
        assert not cache.exists()

    def test_manifest_change_does_not_touch_language_cache(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The two caches are independent — a manifest change should leave
        # the language-profile cache alone.
        memory = tmp_dir / "memory"
        memory.mkdir()
        version_cache = memory / _VERSION_CHECK_CACHE
        language_cache = tmp_dir / _LANGUAGE_PROFILE_CACHE
        _seed_cache(version_cache)
        _seed_cache(language_cache)

        _patch(
            monkeypatch,
            tmp_dir,
            memory_dir=memory,
            payload={"path": ".claude-plugin/plugin.json"},
        )

        config_change.main()
        assert not version_cache.exists()
        assert language_cache.exists()


# ---------------------------------------------------------------------------
# Off-watch / out-of-project paths — no-op
# ---------------------------------------------------------------------------


class TestOffWatch:
    def test_unrelated_file_is_noop(self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        cache = tmp_dir / _LANGUAGE_PROFILE_CACHE
        _seed_cache(cache)
        _patch(monkeypatch, tmp_dir, payload={"path": "src/foo.py"})

        config_change.main()
        # Nothing watched changed; cache untouched.
        assert cache.exists()

    def test_graph_registry_is_no_op(self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Documented no-op — no on-disk cache is invalidated for the
        # graph registry yet.
        cache = tmp_dir / _LANGUAGE_PROFILE_CACHE
        _seed_cache(cache)
        _patch(
            monkeypatch,
            tmp_dir,
            payload={"path": "config/graph-registry.json"},
        )

        assert config_change.main() == 0
        # Language cache untouched.
        assert cache.exists()

    def test_outside_project_is_noop(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path_factory: pytest.TempPathFactory,
    ) -> None:
        cache = tmp_dir / _LANGUAGE_PROFILE_CACHE
        _seed_cache(cache)
        outside = tmp_path_factory.mktemp("elsewhere") / "config" / "profiles" / "x.json"
        outside.parent.mkdir(parents=True)
        outside.write_text("{}", encoding="utf-8")

        _patch(monkeypatch, tmp_dir, payload={"path": str(outside)})

        config_change.main()
        assert cache.exists()

    def test_no_path_in_payload_is_noop(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cache = tmp_dir / _LANGUAGE_PROFILE_CACHE
        _seed_cache(cache)
        _patch(monkeypatch, tmp_dir, payload={})

        assert config_change.main() == 0
        assert cache.exists()

    def test_alt_payload_field_file_path(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cache = tmp_dir / _LANGUAGE_PROFILE_CACHE
        _seed_cache(cache)
        _patch(
            monkeypatch,
            tmp_dir,
            payload={"file_path": "config/profiles/python.json"},
        )

        config_change.main()
        assert not cache.exists()


# ---------------------------------------------------------------------------
# Resilience
# ---------------------------------------------------------------------------


class TestResilience:
    def test_unlink_failure_logged_not_raised(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Make the cache path a directory so ``unlink`` raises.
        cache = tmp_dir / _LANGUAGE_PROFILE_CACHE
        cache.mkdir()
        _patch(
            monkeypatch,
            tmp_dir,
            payload={"path": "config/profiles/python.json"},
        )

        assert config_change.main() == 0
        err = capsys.readouterr().err
        assert "could not invalidate" in err

    def test_empty_stdin_is_noop(self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        cache = tmp_dir / _LANGUAGE_PROFILE_CACHE
        _seed_cache(cache)
        monkeypatch.setattr(sys, "stdin", StringIO(""))
        monkeypatch.setattr(config_change, "get_project_dir", lambda: tmp_dir)
        monkeypatch.setattr(config_change, "get_memory_dir", lambda _d: tmp_dir)

        assert config_change.main() == 0
        assert cache.exists()
