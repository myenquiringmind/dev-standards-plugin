"""Tests for hooks/context_budget.py."""

from __future__ import annotations

import sys
from io import StringIO
from pathlib import Path

import pytest

from hooks import context_budget


def _patch_io(
    monkeypatch: pytest.MonkeyPatch,
    pct: int | None,
    project_dir: Path,
) -> None:
    monkeypatch.setattr(sys, "stdin", StringIO("{}"))
    monkeypatch.setattr(context_budget, "get_project_dir", lambda: project_dir)
    monkeypatch.setattr(context_budget, "read_cached_pct", lambda _d: pct)


class TestCacheAbsent:
    def test_exits_zero_with_offline_advisory(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _patch_io(monkeypatch, None, tmp_dir)
        rc = context_budget.main()
        captured = capsys.readouterr()
        assert rc == 0
        assert "monitoring offline" in captured.err
        assert ".context_pct" in captured.err
        assert "statusline" in captured.err
        assert captured.out == ""


class TestUnderWarn:
    def test_exits_zero_no_output(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _patch_io(monkeypatch, 50, tmp_dir)
        rc = context_budget.main()
        captured = capsys.readouterr()
        assert rc == 0
        assert captured.err == ""


class TestAtWarn:
    def test_exits_zero_with_advisory(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _patch_io(monkeypatch, 80, tmp_dir)
        rc = context_budget.main()
        captured = capsys.readouterr()
        assert rc == 0
        assert "80%" in captured.err
        assert "/handoff" in captured.err

    def test_between_warn_and_critical_also_advises(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _patch_io(monkeypatch, 90, tmp_dir)
        rc = context_budget.main()
        captured = capsys.readouterr()
        assert rc == 0
        assert "90%" in captured.err


class TestAtCritical:
    def test_exits_two_with_handoff(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _patch_io(monkeypatch, 100, tmp_dir)
        rc = context_budget.main()
        captured = capsys.readouterr()
        assert rc == 2
        assert "100%" in captured.err
        assert "hard cut" in captured.err
        assert "Commit current work" in captured.err  # HANDOFF_STEPS snippet

    def test_above_critical_exits_two(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _patch_io(monkeypatch, 133, tmp_dir)
        rc = context_budget.main()
        assert rc == 2

    def test_just_below_critical_only_advises(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # 99 is in the warn band; the principle-aligned hard cut is 100.
        _patch_io(monkeypatch, 99, tmp_dir)
        rc = context_budget.main()
        captured = capsys.readouterr()
        assert rc == 0
        assert "99%" in captured.err
