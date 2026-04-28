"""Tests for hooks/post_temp_file_cleanup.py."""

from __future__ import annotations

import json
import os
import sys
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from hooks import post_temp_file_cleanup
from hooks._hook_shared import TMP_FILE_AGE_THRESHOLD_SECONDS


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    project_dir: Path,
    payload: dict[str, Any],
    *,
    now: float = 1_000_000.0,
) -> None:
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(payload)))
    monkeypatch.setattr(post_temp_file_cleanup, "get_project_dir", lambda: project_dir)
    monkeypatch.setattr("time.time", lambda: now)


def _seed_file(directory: Path, name: str, mtime_offset: float, *, now: float) -> Path:
    """Create a file with mtime = now + offset (negative = older)."""
    path = directory / name
    path.write_text("x", encoding="utf-8")
    target_mtime = now + mtime_offset
    os.utime(path, (target_mtime, target_mtime))
    return path


# ---------------------------------------------------------------------------
# Sweep behaviour
# ---------------------------------------------------------------------------


class TestSweep:
    def test_old_tmpclaude_file_is_removed(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        now = 1_000_000.0
        old = _seed_file(
            tmp_dir,
            "tmpclaude-old.txt",
            -TMP_FILE_AGE_THRESHOLD_SECONDS - 1,
            now=now,
        )
        _patch(monkeypatch, tmp_dir, {"tool_name": "Edit"}, now=now)

        assert post_temp_file_cleanup.main() == 0
        assert not old.exists()

    def test_fresh_tmpclaude_file_is_kept(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        now = 1_000_000.0
        fresh = _seed_file(tmp_dir, "tmpclaude-fresh.txt", -10.0, now=now)
        _patch(monkeypatch, tmp_dir, {"tool_name": "Write"}, now=now)

        post_temp_file_cleanup.main()
        assert fresh.exists()

    def test_threshold_boundary_kept(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Exactly at the threshold (mtime == now - 300) → mtime > threshold → kept.
        now = 1_000_000.0
        boundary = _seed_file(
            tmp_dir,
            "tmpclaude-boundary.txt",
            -TMP_FILE_AGE_THRESHOLD_SECONDS,
            now=now,
        )
        _patch(monkeypatch, tmp_dir, {"tool_name": "Edit"}, now=now)

        post_temp_file_cleanup.main()
        assert boundary.exists()

    def test_non_matching_file_untouched(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        now = 1_000_000.0
        unrelated = _seed_file(
            tmp_dir,
            "important.txt",
            -TMP_FILE_AGE_THRESHOLD_SECONDS - 100,
            now=now,
        )
        _patch(monkeypatch, tmp_dir, {"tool_name": "Edit"}, now=now)

        post_temp_file_cleanup.main()
        assert unrelated.exists()

    def test_directory_named_like_tmpclaude_skipped(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        now = 1_000_000.0
        d = tmp_dir / "tmpclaude-dir"
        d.mkdir()
        # Backdate the dir's mtime past the threshold.
        old_mtime = now - TMP_FILE_AGE_THRESHOLD_SECONDS - 100
        os.utime(d, (old_mtime, old_mtime))
        _patch(monkeypatch, tmp_dir, {"tool_name": "Edit"}, now=now)

        post_temp_file_cleanup.main()
        assert d.is_dir()

    def test_multiple_files_partial_sweep(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        now = 1_000_000.0
        old_a = _seed_file(
            tmp_dir, "tmpclaude-a.txt", -TMP_FILE_AGE_THRESHOLD_SECONDS - 50, now=now
        )
        old_b = _seed_file(
            tmp_dir, "tmpclaude-b.json", -TMP_FILE_AGE_THRESHOLD_SECONDS - 1, now=now
        )
        fresh = _seed_file(tmp_dir, "tmpclaude-c.tmp", -1.0, now=now)
        _patch(monkeypatch, tmp_dir, {"tool_name": "Edit"}, now=now)

        post_temp_file_cleanup.main()
        assert not old_a.exists()
        assert not old_b.exists()
        assert fresh.exists()

    def test_recursive_subdir_files_not_touched(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Sweep is non-recursive — only the project root.
        now = 1_000_000.0
        sub = tmp_dir / "sub"
        sub.mkdir()
        nested = _seed_file(
            sub,
            "tmpclaude-nested.txt",
            -TMP_FILE_AGE_THRESHOLD_SECONDS - 100,
            now=now,
        )
        _patch(monkeypatch, tmp_dir, {"tool_name": "Edit"}, now=now)

        post_temp_file_cleanup.main()
        assert nested.exists()


# ---------------------------------------------------------------------------
# Tool-name gate
# ---------------------------------------------------------------------------


class TestToolGate:
    @pytest.mark.parametrize("tool", ["Edit", "Write", "MultiEdit"])
    def test_qualifying_tools_trigger_sweep(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        tool: str,
    ) -> None:
        now = 1_000_000.0
        target = _seed_file(
            tmp_dir,
            "tmpclaude-x.txt",
            -TMP_FILE_AGE_THRESHOLD_SECONDS - 1,
            now=now,
        )
        _patch(monkeypatch, tmp_dir, {"tool_name": tool}, now=now)

        post_temp_file_cleanup.main()
        assert not target.exists()

    @pytest.mark.parametrize("tool", ["Bash", "Read", "Grep", ""])
    def test_non_qualifying_tools_skip_sweep(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        tool: str,
    ) -> None:
        now = 1_000_000.0
        target = _seed_file(
            tmp_dir,
            "tmpclaude-x.txt",
            -TMP_FILE_AGE_THRESHOLD_SECONDS - 1,
            now=now,
        )
        _patch(monkeypatch, tmp_dir, {"tool_name": tool}, now=now)

        post_temp_file_cleanup.main()
        # Sweep was skipped — file remains.
        assert target.exists()


# ---------------------------------------------------------------------------
# Resilience
# ---------------------------------------------------------------------------


class TestResilience:
    def test_empty_stdin_returns_zero(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(sys, "stdin", StringIO(""))
        monkeypatch.setattr(post_temp_file_cleanup, "get_project_dir", lambda: tmp_dir)

        assert post_temp_file_cleanup.main() == 0

    def test_unlink_failure_logged_not_raised(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        now = 1_000_000.0
        _seed_file(
            tmp_dir,
            "tmpclaude-locked.txt",
            -TMP_FILE_AGE_THRESHOLD_SECONDS - 1,
            now=now,
        )

        original_unlink = Path.unlink

        def fail_unlink(self: Path, missing_ok: bool = False) -> None:
            if self.name == "tmpclaude-locked.txt":
                raise PermissionError("locked")
            original_unlink(self, missing_ok=missing_ok)

        monkeypatch.setattr(Path, "unlink", fail_unlink)
        _patch(monkeypatch, tmp_dir, {"tool_name": "Edit"}, now=now)

        assert post_temp_file_cleanup.main() == 0
        err = capsys.readouterr().err
        assert "could not remove" in err
        assert "tmpclaude-locked.txt" in err

    def test_no_tmpclaude_files_is_noop(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _patch(monkeypatch, tmp_dir, {"tool_name": "Edit"})

        assert post_temp_file_cleanup.main() == 0
