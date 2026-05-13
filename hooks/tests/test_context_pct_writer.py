"""Tests for hooks/context_pct_writer.py."""

from __future__ import annotations

import json
import sys
import time
from io import StringIO
from pathlib import Path

import pytest

from hooks import context_pct_writer
from hooks._hook_shared import (
    BYTES_PER_TOKEN_ESTIMATE,
    FALLBACK_WINDOW_TOKENS,
    STATUSLINE_STALENESS_SECONDS,
    compute_hard_cut,
)


def _stub_stdin(monkeypatch: pytest.MonkeyPatch, payload: dict[str, object]) -> None:
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(payload)))


def _stub_project_dir(monkeypatch: pytest.MonkeyPatch, project_dir: Path) -> None:
    monkeypatch.setattr(context_pct_writer, "get_project_dir", lambda: project_dir)


def _make_transcript(tmp_dir: Path, size_bytes: int) -> Path:
    transcript = tmp_dir / "transcript.jsonl"
    transcript.write_bytes(b"x" * size_bytes)
    return transcript


def _cache_path(project_dir: Path) -> Path:
    return project_dir / ".claude" / ".context_pct"


def _expected_pct(bytes_count: int) -> int:
    hard_cut = compute_hard_cut(FALLBACK_WINDOW_TOKENS)
    tokens = bytes_count // BYTES_PER_TOKEN_ESTIMATE
    return tokens * 100 // hard_cut


class TestEstimation:
    def test_zero_bytes_yields_zero(self) -> None:
        assert context_pct_writer._estimate_framework_pct(0) == 0

    def test_negative_bytes_yields_zero(self) -> None:
        assert context_pct_writer._estimate_framework_pct(-1) == 0

    def test_small_transcript_under_warn(self) -> None:
        # ~1000 bytes → tiny pct
        pct = context_pct_writer._estimate_framework_pct(1_000)
        assert 0 <= pct < 5

    def test_at_hard_cut_returns_one_hundred(self) -> None:
        hard_cut_tokens = compute_hard_cut(FALLBACK_WINDOW_TOKENS)
        bytes_at_cut = hard_cut_tokens * BYTES_PER_TOKEN_ESTIMATE
        pct = context_pct_writer._estimate_framework_pct(bytes_at_cut)
        assert pct == 100

    def test_above_hard_cut_exceeds_one_hundred(self) -> None:
        hard_cut_tokens = compute_hard_cut(FALLBACK_WINDOW_TOKENS)
        bytes_above_cut = hard_cut_tokens * BYTES_PER_TOKEN_ESTIMATE * 2
        pct = context_pct_writer._estimate_framework_pct(bytes_above_cut)
        assert pct >= 100


class TestSessionStartEvent:
    def test_writes_zero_when_transcript_missing(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _stub_stdin(monkeypatch, {"hook_event_name": "SessionStart"})
        _stub_project_dir(monkeypatch, tmp_dir)
        (tmp_dir / ".claude").mkdir()

        rc = context_pct_writer.main()
        assert rc == 0
        assert _cache_path(tmp_dir).read_text(encoding="utf-8") == "0"

    def test_writes_estimate_from_transcript(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        transcript = _make_transcript(tmp_dir, 30_000)
        _stub_stdin(
            monkeypatch,
            {
                "hook_event_name": "SessionStart",
                "transcript_path": str(transcript),
            },
        )
        _stub_project_dir(monkeypatch, tmp_dir)
        (tmp_dir / ".claude").mkdir()

        rc = context_pct_writer.main()
        assert rc == 0
        written = int(_cache_path(tmp_dir).read_text(encoding="utf-8"))
        assert written == _expected_pct(30_000)

    def test_overwrites_stale_cache(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # SessionStart must reset a value left by a prior session.
        cache_dir = tmp_dir / ".claude"
        cache_dir.mkdir()
        cache = cache_dir / ".context_pct"
        cache.write_text("75", encoding="utf-8")

        _stub_stdin(monkeypatch, {"hook_event_name": "SessionStart"})
        _stub_project_dir(monkeypatch, tmp_dir)

        rc = context_pct_writer.main()
        assert rc == 0
        assert cache.read_text(encoding="utf-8") == "0"


class TestPostToolUseEvent:
    def test_writes_estimate_when_cache_missing(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        transcript = _make_transcript(tmp_dir, 60_000)
        _stub_stdin(
            monkeypatch,
            {
                "hook_event_name": "PostToolUse",
                "transcript_path": str(transcript),
                "tool_name": "Read",
            },
        )
        _stub_project_dir(monkeypatch, tmp_dir)
        (tmp_dir / ".claude").mkdir()

        rc = context_pct_writer.main()
        assert rc == 0
        written = int(_cache_path(tmp_dir).read_text(encoding="utf-8"))
        assert written == _expected_pct(60_000)

    def test_defers_to_fresh_cache(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        cache_dir = tmp_dir / ".claude"
        cache_dir.mkdir()
        cache = cache_dir / ".context_pct"
        cache.write_text("42", encoding="utf-8")  # statusline value

        transcript = _make_transcript(tmp_dir, 100_000)
        _stub_stdin(
            monkeypatch,
            {
                "hook_event_name": "PostToolUse",
                "transcript_path": str(transcript),
            },
        )
        _stub_project_dir(monkeypatch, tmp_dir)

        rc = context_pct_writer.main()
        assert rc == 0
        # Fresh statusline value must survive untouched.
        assert cache.read_text(encoding="utf-8") == "42"

    def test_overwrites_stale_cache(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        cache_dir = tmp_dir / ".claude"
        cache_dir.mkdir()
        cache = cache_dir / ".context_pct"
        cache.write_text("12", encoding="utf-8")
        # Backdate mtime past the staleness window.
        stale_mtime = time.time() - (STATUSLINE_STALENESS_SECONDS + 30)
        import os

        os.utime(cache, (stale_mtime, stale_mtime))

        transcript = _make_transcript(tmp_dir, 90_000)
        _stub_stdin(
            monkeypatch,
            {
                "hook_event_name": "PostToolUse",
                "transcript_path": str(transcript),
            },
        )
        _stub_project_dir(monkeypatch, tmp_dir)

        rc = context_pct_writer.main()
        assert rc == 0
        written = int(cache.read_text(encoding="utf-8"))
        assert written == _expected_pct(90_000)

    def test_writes_zero_when_transcript_missing(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _stub_stdin(monkeypatch, {"hook_event_name": "PostToolUse"})
        _stub_project_dir(monkeypatch, tmp_dir)
        (tmp_dir / ".claude").mkdir()

        rc = context_pct_writer.main()
        assert rc == 0
        assert _cache_path(tmp_dir).read_text(encoding="utf-8") == "0"

    def test_writes_zero_when_transcript_path_invalid(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _stub_stdin(
            monkeypatch,
            {
                "hook_event_name": "PostToolUse",
                "transcript_path": str(tmp_dir / "does-not-exist.jsonl"),
            },
        )
        _stub_project_dir(monkeypatch, tmp_dir)
        (tmp_dir / ".claude").mkdir()

        rc = context_pct_writer.main()
        assert rc == 0
        assert _cache_path(tmp_dir).read_text(encoding="utf-8") == "0"


class TestUnknownEvent:
    def test_no_op_on_unknown_event(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _stub_stdin(monkeypatch, {"hook_event_name": "WorktreeCreate"})
        _stub_project_dir(monkeypatch, tmp_dir)

        rc = context_pct_writer.main()
        assert rc == 0
        assert not _cache_path(tmp_dir).exists()

    def test_no_op_on_missing_event(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _stub_stdin(monkeypatch, {})
        _stub_project_dir(monkeypatch, tmp_dir)

        rc = context_pct_writer.main()
        assert rc == 0
        assert not _cache_path(tmp_dir).exists()


class TestCacheFreshness:
    def test_fresh_cache_detected(self, tmp_dir: Path) -> None:
        cache = tmp_dir / ".context_pct"
        cache.write_text("50", encoding="utf-8")
        assert context_pct_writer._cache_is_fresh(cache, time.time()) is True

    def test_missing_cache_is_not_fresh(self, tmp_dir: Path) -> None:
        cache = tmp_dir / ".context_pct"
        assert context_pct_writer._cache_is_fresh(cache, time.time()) is False

    def test_stale_cache_detected(self, tmp_dir: Path) -> None:
        import os

        cache = tmp_dir / ".context_pct"
        cache.write_text("50", encoding="utf-8")
        stale_mtime = time.time() - (STATUSLINE_STALENESS_SECONDS + 30)
        os.utime(cache, (stale_mtime, stale_mtime))
        assert context_pct_writer._cache_is_fresh(cache, time.time()) is False
