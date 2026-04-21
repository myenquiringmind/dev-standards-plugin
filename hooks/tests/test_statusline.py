"""Tests for hooks/statusline.py."""

from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path

import pytest

from hooks import statusline
from hooks._hook_shared import CC_COMPACTION_FRACTION, HARD_CUT_FRACTION

_BUDGET_FRACTION = CC_COMPACTION_FRACTION * HARD_CUT_FRACTION


def _patch_io(
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, object] | str,
    project_dir: Path,
    *,
    branch: str = "feat/example",
) -> None:
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr(sys, "stdin", StringIO(stdin))
    monkeypatch.setattr(statusline, "get_project_dir", lambda: project_dir)
    monkeypatch.setattr(statusline, "get_current_branch", lambda _d: branch)


def _read_cache(project_dir: Path) -> int:
    return int((project_dir / ".claude" / ".context_pct").read_text(encoding="utf-8"))


def _cc_payload(
    *,
    used_pct: float | None = 20.0,
    window: int | None = 200_000,
    model_name: str = "Opus",
    model_id: str = "claude-opus-4-7",
) -> dict[str, object]:
    cw: dict[str, object] = {}
    if used_pct is not None:
        cw["used_percentage"] = used_pct
    if window is not None:
        cw["context_window_size"] = window
    return {
        "model": {"id": model_id, "display_name": model_name},
        "context_window": cw,
    }


class TestCacheWrite:
    def test_raw_20_pct_writes_framework_pct(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _patch_io(monkeypatch, _cc_payload(used_pct=20.0), tmp_dir)

        rc = statusline.main()

        assert rc == 0
        # raw 20% / 0.62625 ≈ 31.94 → int 31
        expected = int(20.0 / _BUDGET_FRACTION)
        assert _read_cache(tmp_dir) == expected

    def test_raw_at_cut_writes_100(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # raw_pct at exactly the hard cut fraction writes framework 100%.
        _patch_io(monkeypatch, _cc_payload(used_pct=_BUDGET_FRACTION * 100), tmp_dir)

        rc = statusline.main()

        assert rc == 0
        assert _read_cache(tmp_dir) == 100

    def test_past_cut_writes_over_100(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # raw_pct above the budget fraction produces framework_pct > 100.
        _patch_io(monkeypatch, _cc_payload(used_pct=75.0), tmp_dir)

        rc = statusline.main()

        assert rc == 0
        assert _read_cache(tmp_dir) > 100

    def test_zero_pct_writes_zero(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _patch_io(monkeypatch, _cc_payload(used_pct=0.0), tmp_dir)

        rc = statusline.main()

        assert rc == 0
        assert _read_cache(tmp_dir) == 0

    def test_missing_used_pct_skips_cache(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _patch_io(monkeypatch, _cc_payload(used_pct=None), tmp_dir)

        rc = statusline.main()

        assert rc == 0
        assert not (tmp_dir / ".claude" / ".context_pct").exists()


class TestStatusLineText:
    def test_full_payload_prints_all_segments(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _patch_io(monkeypatch, _cc_payload(used_pct=20.0), tmp_dir, branch="feat/foo")

        rc = statusline.main()

        out = capsys.readouterr().out.strip()
        assert rc == 0
        assert "Opus" in out
        assert "ctx" in out
        assert "%" in out
        assert "feat/foo" in out
        # token format should include K suffix for 200K window
        assert "K" in out

    def test_missing_window_omits_token_fraction(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _patch_io(monkeypatch, _cc_payload(used_pct=20.0, window=None), tmp_dir)

        rc = statusline.main()

        out = capsys.readouterr().out.strip()
        assert rc == 0
        assert "ctx" in out
        # no parenthesised token count when window is absent
        assert "(" not in out

    def test_missing_pct_omits_ctx(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _patch_io(monkeypatch, _cc_payload(used_pct=None), tmp_dir)

        rc = statusline.main()

        out = capsys.readouterr().out.strip()
        assert rc == 0
        assert "ctx" not in out
        assert "Opus" in out

    def test_model_id_fallback(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        payload: dict[str, object] = {
            "model": {"id": "claude-opus-4-7"},
            "context_window": {"used_percentage": 5.0, "context_window_size": 200_000},
        }
        _patch_io(monkeypatch, payload, tmp_dir)

        rc = statusline.main()

        out = capsys.readouterr().out.strip()
        assert rc == 0
        assert "claude-opus-4-7" in out

    def test_missing_model_omits_name(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        payload: dict[str, object] = {
            "context_window": {"used_percentage": 5.0, "context_window_size": 200_000},
        }
        _patch_io(monkeypatch, payload, tmp_dir, branch="master")

        rc = statusline.main()

        out = capsys.readouterr().out.strip()
        assert rc == 0
        assert out.startswith("ctx")
        assert "master" in out

    def test_empty_branch_omits_branch(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _patch_io(monkeypatch, _cc_payload(used_pct=5.0), tmp_dir, branch="")

        rc = statusline.main()

        out = capsys.readouterr().out.strip()
        assert rc == 0
        assert "·" in out  # Opus · ctx X%
        assert not out.endswith("·")


class TestEmptyInput:
    def test_empty_stdin_prints_branch_only(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _patch_io(monkeypatch, "", tmp_dir, branch="feat/foo")

        rc = statusline.main()

        out = capsys.readouterr().out.strip()
        assert rc == 0
        assert out == "feat/foo"
        assert not (tmp_dir / ".claude" / ".context_pct").exists()

    def test_malformed_json_prints_branch_only(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _patch_io(monkeypatch, "{not json", tmp_dir, branch="feat/foo")

        rc = statusline.main()

        out = capsys.readouterr().out.strip()
        assert rc == 0
        assert out == "feat/foo"

    def test_no_branch_no_data_prints_nothing(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _patch_io(monkeypatch, "", tmp_dir, branch="")

        rc = statusline.main()

        out = capsys.readouterr().out
        assert rc == 0
        assert out == ""


class TestTokenFormat:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (999, "999"),
            (1_000, "1K"),
            (1_500, "2K"),
            (125_000, "125K"),
            (1_000_000, "1.0M"),
            (1_250_000, "1.2M"),
        ],
    )
    def test_format_tokens(self, value: int, expected: str) -> None:
        assert statusline._format_tokens(value) == expected


class TestCacheFailure:
    def test_oserror_logged_still_exits_zero(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        def fake_atomic_write(*_args: object, **_kwargs: object) -> Path:
            raise OSError("disk full")

        monkeypatch.setattr(statusline, "atomic_write", fake_atomic_write)
        _patch_io(monkeypatch, _cc_payload(used_pct=10.0), tmp_dir, branch="master")

        rc = statusline.main()

        out = capsys.readouterr()
        assert rc == 0
        assert "could not write .context_pct" in out.err
        # Status line still printed despite cache failure.
        assert "Opus" in out.out
