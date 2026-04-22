"""Tests for hooks/_telemetry.py."""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from hooks import _telemetry


@pytest.fixture
def telemetry_root(tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate telemetry writes under tmp_dir via CLAUDE_TELEMETRY_DIR."""
    root = tmp_dir / "telemetry"
    monkeypatch.setenv("CLAUDE_TELEMETRY_DIR", str(root))
    return root


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


class TestEmit:
    def test_single_record_written(self, telemetry_root: Path) -> None:
        _telemetry.emit("hook-failure", {"tool": "Edit", "exit": 2})

        files = list(telemetry_root.glob("*.jsonl"))
        assert len(files) == 1
        records = _read_jsonl(files[0])
        assert len(records) == 1
        assert records[0]["category"] == "hook-failure"
        assert records[0]["data"] == {"tool": "Edit", "exit": 2}
        assert records[0]["timestamp"].endswith("Z")

    def test_filename_is_date(self, telemetry_root: Path) -> None:
        _telemetry.emit("x", {"n": 1})
        files = list(telemetry_root.glob("*.jsonl"))
        assert len(files) == 1
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        assert files[0].name == f"{today}.jsonl"

    def test_multiple_emits_same_day_append(self, telemetry_root: Path) -> None:
        for i in range(5):
            _telemetry.emit("x", {"n": i})

        files = list(telemetry_root.glob("*.jsonl"))
        assert len(files) == 1
        records = _read_jsonl(files[0])
        assert [r["data"]["n"] for r in records] == [0, 1, 2, 3, 4]

    def test_record_is_json_serialisable_shape(self, telemetry_root: Path) -> None:
        _telemetry.emit("stamp-write", {"gate": "code", "steps": ["ruff-check", "pytest"]})

        files = list(telemetry_root.glob("*.jsonl"))
        records = _read_jsonl(files[0])
        assert records[0]["data"]["gate"] == "code"
        assert records[0]["data"]["steps"] == ["ruff-check", "pytest"]


class TestCategoryValidation:
    @pytest.mark.parametrize(
        "bad",
        [
            "Hook-Failure",  # uppercase
            "hook_failure",  # underscore
            "hook failure",  # space
            "../traversal",  # path escape
            "",  # empty
            "-leading-hyphen",
            "hook.failure",  # dot
        ],
    )
    def test_invalid_category_rejected(
        self,
        telemetry_root: Path,
        bad: str,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _telemetry.emit(bad, {"n": 1})

        assert list(telemetry_root.glob("*.jsonl")) == []
        err = capsys.readouterr().err
        assert "refusing invalid category" in err

    def test_valid_category_accepted(self, telemetry_root: Path) -> None:
        _telemetry.emit("hook-failure-123", {"n": 1})
        assert list(telemetry_root.glob("*.jsonl"))


class TestEmitMany:
    def test_atomic_batch_write(self, telemetry_root: Path) -> None:
        _telemetry.emit_many(
            "tier-violation",
            [
                {"agent": "a", "tool": "Edit"},
                {"agent": "b", "tool": "Write"},
                {"agent": "c", "tool": "NotebookEdit"},
            ],
        )

        files = list(telemetry_root.glob("*.jsonl"))
        assert len(files) == 1
        records = _read_jsonl(files[0])
        assert len(records) == 3
        assert [r["data"]["agent"] for r in records] == ["a", "b", "c"]

    def test_empty_list_no_file(self, telemetry_root: Path) -> None:
        _telemetry.emit_many("x", [])
        assert list(telemetry_root.glob("*.jsonl")) == []

    def test_invalid_category_rejects_whole_batch(
        self, telemetry_root: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _telemetry.emit_many("BadCat", [{"n": 1}, {"n": 2}])
        assert list(telemetry_root.glob("*.jsonl")) == []
        assert "refusing invalid category" in capsys.readouterr().err

    def test_non_serialisable_aborts_batch(
        self, telemetry_root: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Object with a non-JSON-serialisable value — whole batch is dropped.
        class NotJson:
            pass

        _telemetry.emit_many("x", [{"n": 1}, {"bad": NotJson()}])
        assert list(telemetry_root.glob("*.jsonl")) == []
        assert "not JSON-serialisable" in capsys.readouterr().err


class TestConcurrency:
    def test_concurrent_emits_no_corruption(self, telemetry_root: Path) -> None:
        threads = []
        n_per_thread = 20
        n_threads = 4

        def worker(idx: int) -> None:
            for i in range(n_per_thread):
                _telemetry.emit("x", {"thread": idx, "i": i})

        for idx in range(n_threads):
            t = threading.Thread(target=worker, args=(idx,))
            t.start()
            threads.append(t)
        for t in threads:
            t.join()

        files = list(telemetry_root.glob("*.jsonl"))
        assert len(files) == 1
        records = _read_jsonl(files[0])
        assert len(records) == n_threads * n_per_thread

        # Every record should have the expected shape, no partial lines.
        for rec in records:
            assert rec["category"] == "x"
            assert "thread" in rec["data"]
            assert "i" in rec["data"]


class TestErrorHandling:
    def test_non_serialisable_does_not_raise(
        self, telemetry_root: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        class NotJson:
            pass

        # Must not raise.
        _telemetry.emit("x", {"bad": NotJson()})

        assert list(telemetry_root.glob("*.jsonl")) == []
        assert "not JSON-serialisable" in capsys.readouterr().err

    def test_bad_telemetry_dir_logs_stderr(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Point CLAUDE_TELEMETRY_DIR at a file, not a directory, so mkdir fails.
        bad = tmp_dir / "not-a-dir"
        bad.write_text("nope", encoding="utf-8")
        monkeypatch.setenv("CLAUDE_TELEMETRY_DIR", str(bad / "sub"))

        # The parent 'bad' exists as a file; mkdir(bad/sub) raises
        # FileExistsError or NotADirectoryError depending on platform.
        _telemetry.emit("x", {"n": 1})

        err = capsys.readouterr().err
        assert "could not write" in err or "refusing invalid" in err
