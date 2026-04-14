"""Tests for hooks/_os_safe.py — atomic writes, locking, path safety, temp lifecycle."""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import IO, cast

import pytest

from hooks._os_safe import (
    atomic_write,
    locked_open,
    normalize_path,
    safe_join,
    temp_directory,
    temp_file,
)

# ---------------------------------------------------------------------------
# normalize_path
# ---------------------------------------------------------------------------


class TestNormalizePath:
    def test_resolves_relative(self) -> None:
        result = normalize_path(".")
        assert result.is_absolute()

    def test_resolves_dot_dot(self, tmp_dir: Path) -> None:
        child = tmp_dir / "a" / "b"
        child.mkdir(parents=True)
        result = normalize_path(child / "..")
        assert result == tmp_dir / "a"

    def test_expands_tilde(self) -> None:
        result = normalize_path("~")
        assert result.is_absolute()
        assert "~" not in str(result)

    def test_accepts_path_object(self, tmp_dir: Path) -> None:
        result = normalize_path(tmp_dir)
        assert result == tmp_dir.resolve()

    def test_forward_slashes_on_windows(self, tmp_dir: Path) -> None:
        """Forward slashes in a path string should resolve correctly."""
        path_str = str(tmp_dir).replace("\\", "/")
        result = normalize_path(path_str)
        assert result == tmp_dir.resolve()


# ---------------------------------------------------------------------------
# safe_join
# ---------------------------------------------------------------------------


class TestSafeJoin:
    def test_simple_join(self, tmp_dir: Path) -> None:
        result = safe_join(tmp_dir, "subdir", "file.txt")
        assert result == (tmp_dir / "subdir" / "file.txt").resolve()

    def test_rejects_dot_dot_escape(self, tmp_dir: Path) -> None:
        with pytest.raises(ValueError, match="Path traversal blocked"):
            safe_join(tmp_dir, "..", "..", "etc", "passwd")

    def test_rejects_absolute_escape(self, tmp_dir: Path) -> None:
        escape = "C:\\Windows\\System32\\evil.txt" if os.name == "nt" else "/etc/passwd"
        with pytest.raises(ValueError, match="Path traversal blocked"):
            safe_join(tmp_dir, escape)

    def test_allows_dot_dot_within_base(self, tmp_dir: Path) -> None:
        """``a/b/../c`` is fine if the result stays inside base."""
        (tmp_dir / "a" / "b").mkdir(parents=True)
        (tmp_dir / "a" / "c").mkdir(parents=True)
        result = safe_join(tmp_dir, "a", "b", "..", "c")
        assert result == (tmp_dir / "a" / "c").resolve()

    def test_rejects_agent_memory_traversal(self, tmp_dir: Path) -> None:
        """The canonical example: ``--agent ../../etc/passwd`` must fail."""
        with pytest.raises(ValueError, match="Path traversal blocked"):
            safe_join(tmp_dir, "agents", "../../etc/passwd")

    def test_empty_parts(self, tmp_dir: Path) -> None:
        result = safe_join(tmp_dir)
        assert result == tmp_dir.resolve()


# ---------------------------------------------------------------------------
# locked_open
# ---------------------------------------------------------------------------


class TestLockedOpen:
    def test_read_write_cycle(self, tmp_dir: Path) -> None:
        target = tmp_dir / "locktest.txt"
        target.write_text("hello", encoding="utf-8")

        with locked_open(target, "r+") as raw_fh:
            # locked_open yields IO[str] | IO[bytes]; we opened in text mode.
            fh = cast("IO[str]", raw_fh)
            data = fh.read()
            assert data == "hello"
            fh.seek(0)
            fh.write("world")
            fh.truncate()

        assert target.read_text(encoding="utf-8") == "world"

    def test_lock_blocks_concurrent_access(self, tmp_dir: Path) -> None:
        """A second lock attempt should block until the first releases."""
        target = tmp_dir / "concurrent.txt"
        target.write_text("init", encoding="utf-8")
        results: list[str] = []
        barrier = threading.Barrier(2, timeout=5)

        def writer(label: str) -> None:
            barrier.wait()
            with locked_open(target, "r+", timeout=10) as raw_fh:
                fh = cast("IO[str]", raw_fh)
                fh.seek(0)
                fh.write(label)
                fh.truncate()
                results.append(label)

        t1 = threading.Thread(target=writer, args=("A",))
        t2 = threading.Thread(target=writer, args=("B",))
        t1.start()
        t2.start()
        t1.join(timeout=15)
        t2.join(timeout=15)

        # Both threads completed; the file has the last writer's content.
        assert len(results) == 2
        final = target.read_text(encoding="utf-8")
        assert final in ("A", "B")


# ---------------------------------------------------------------------------
# atomic_write
# ---------------------------------------------------------------------------


class TestAtomicWrite:
    def test_creates_file(self, tmp_dir: Path) -> None:
        target = tmp_dir / "new.txt"
        result = atomic_write(target, "content")
        assert result.read_text(encoding="utf-8") == "content"

    def test_overwrites_existing(self, tmp_dir: Path) -> None:
        target = tmp_dir / "existing.txt"
        target.write_text("old", encoding="utf-8")
        atomic_write(target, "new")
        assert target.read_text(encoding="utf-8") == "new"

    def test_creates_parent_dirs(self, tmp_dir: Path) -> None:
        target = tmp_dir / "a" / "b" / "deep.txt"
        atomic_write(target, "deep")
        assert target.read_text(encoding="utf-8") == "deep"

    def test_no_partial_write_on_error(self, tmp_dir: Path) -> None:
        """If writing fails, the original file should be untouched."""
        target = tmp_dir / "safe.txt"
        target.write_text("original", encoding="utf-8")

        class BoomError(Exception):
            pass

        # Monkey-patch os.replace to simulate a failure after temp write.
        real_replace = os.replace

        def fake_replace(src: str, dst: str) -> None:
            raise BoomError("simulated failure")

        os.replace = fake_replace  # type: ignore[assignment]
        try:
            with pytest.raises(BoomError):
                atomic_write(target, "should not appear")
        finally:
            os.replace = real_replace

        assert target.read_text(encoding="utf-8") == "original"

    def test_concurrent_writers_no_corruption(self, tmp_dir: Path) -> None:
        """Multiple threads writing atomically should never produce corruption."""
        target = tmp_dir / "concurrent_atomic.txt"
        target.write_text("seed", encoding="utf-8")
        num_threads = 8
        writes_per_thread = 20
        barrier = threading.Barrier(num_threads, timeout=10)
        errors: list[Exception] = []

        def writer(thread_id: int) -> None:
            barrier.wait()
            for i in range(writes_per_thread):
                try:
                    payload = f"thread-{thread_id}-write-{i}"
                    atomic_write(target, payload)
                except Exception as exc:
                    errors.append(exc)

        threads = [threading.Thread(target=writer, args=(tid,)) for tid in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert not errors, f"Errors during concurrent writes: {errors}"
        # The file should contain one complete payload (the last writer wins).
        final = target.read_text(encoding="utf-8")
        assert final.startswith("thread-")
        assert "-write-" in final

    def test_returns_resolved_path(self, tmp_dir: Path) -> None:
        target = tmp_dir / "ret.txt"
        result = atomic_write(target, "x")
        assert result.is_absolute()
        assert result == target.resolve()


# ---------------------------------------------------------------------------
# temp_file
# ---------------------------------------------------------------------------


class TestTempFile:
    def test_creates_and_cleans_up(self) -> None:
        with temp_file() as p:
            assert p.exists()
            path_copy = p
        assert not path_copy.exists()

    def test_pre_populates_content(self) -> None:
        with temp_file(content="hello") as p:
            assert p.read_text(encoding="utf-8") == "hello"

    def test_custom_suffix_and_prefix(self) -> None:
        with temp_file(suffix=".json", prefix="test-") as p:
            assert p.name.startswith("test-")
            assert p.name.endswith(".json")

    def test_respects_dir(self, tmp_dir: Path) -> None:
        with temp_file(dir=tmp_dir) as p:
            assert p.parent == tmp_dir


# ---------------------------------------------------------------------------
# temp_directory
# ---------------------------------------------------------------------------


class TestTempDirectory:
    def test_creates_and_cleans_up(self) -> None:
        with temp_directory() as d:
            assert d.is_dir()
            dir_copy = d
        assert not dir_copy.exists()

    def test_cleans_up_contents(self) -> None:
        with temp_directory() as d:
            (d / "child.txt").write_text("x", encoding="utf-8")
            (d / "subdir").mkdir()
            (d / "subdir" / "nested.txt").write_text("y", encoding="utf-8")
            dir_copy = d
        assert not dir_copy.exists()

    def test_custom_prefix(self) -> None:
        with temp_directory(prefix="mytest-") as d:
            assert d.name.startswith("mytest-")

    def test_handles_readonly_files(self) -> None:
        """Windows read-only files should still be cleaned up."""
        with temp_directory() as d:
            ro_file = d / "readonly.txt"
            ro_file.write_text("locked", encoding="utf-8")
            ro_file.chmod(0o444)
            dir_copy = d
        assert not dir_copy.exists()
