"""Cross-platform file-safety primitives for dev-standards-plugin hooks.

Windows-first. Every hook that writes to disk imports this module.
Provides: atomic writes, file locking, path traversal protection,
path normalization, and temporary file lifecycle management.

Event: N/A (shared module, not a hook)
"""

from __future__ import annotations

import contextlib
import os
import tempfile
import time
from pathlib import Path
from typing import IO, TYPE_CHECKING

import portalocker

if TYPE_CHECKING:
    from collections.abc import Generator


# ---------------------------------------------------------------------------
# Path normalization
# ---------------------------------------------------------------------------


def normalize_path(path: str | Path) -> Path:
    """Resolve and normalize a path for the current platform.

    Expands ``~``, resolves ``.`` and ``..``, and normalizes separators.
    The result is always an absolute ``Path``.
    """
    return Path(os.path.expanduser(path)).resolve()


# ---------------------------------------------------------------------------
# Path-traversal-safe join
# ---------------------------------------------------------------------------


def safe_join(base: str | Path, *parts: str) -> Path:
    """Join *parts* under *base*, rejecting any path-traversal attempt.

    After joining, the resolved result must remain inside (or equal to)
    the resolved *base*.  If not, ``ValueError`` is raised.

    Returns:
        The resolved, normalized joined path.

    Raises:
        ValueError: If the joined path escapes *base*.
    """
    base_resolved = normalize_path(base)
    joined = base_resolved.joinpath(*parts).resolve()

    # On Windows, Path.is_relative_to handles drive-letter differences.
    if not joined.is_relative_to(base_resolved):
        msg = f"Path traversal blocked: resulting path {joined} is outside base {base_resolved}"
        raise ValueError(msg)

    return joined


# ---------------------------------------------------------------------------
# File locking
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def locked_open(
    path: str | Path,
    mode: str = "r",
    *,
    timeout: float = 10.0,
    encoding: str | None = "utf-8",
) -> Generator[IO[str] | IO[bytes]]:
    """Open *path* with an exclusive ``portalocker`` lock.

    Yields the underlying **file handle**, not the Lock wrapper, so
    callers can use ``.read()``, ``.write()``, ``.seek()`` directly.

    Usage::

        with locked_open(some_file, "r+") as fh:
            data = fh.read()
            fh.seek(0)
            fh.write(new_data)

    The lock is released when the context exits.  Binary modes should
    pass ``encoding=None``.
    """
    lock = portalocker.Lock(
        str(path),
        mode=mode,  # type: ignore[arg-type]  # portalocker Literal union is too narrow
        timeout=timeout,
        encoding=encoding,
    )
    try:
        lock.acquire()
        fh = lock.fh
        assert fh is not None
        yield fh
    finally:
        lock.release()


# ---------------------------------------------------------------------------
# Atomic write
# ---------------------------------------------------------------------------


def atomic_write(
    path: str | Path,
    content: str,
    *,
    encoding: str = "utf-8",
    lock_timeout: float = 10.0,
) -> Path:
    """Write *content* to *path* atomically.

    Strategy:
    1. Write to a temporary file in the same directory as *path*.
    2. Acquire an exclusive lock on a **sidecar lock file** (not the
       target itself — Windows forbids ``os.replace`` on an open file).
    3. Replace the target with the temp file (``os.replace`` is atomic
       on both POSIX and NTFS within the same volume).
    4. Release the lock.

    Returns:
        The resolved ``Path`` that was written.
    """
    target = normalize_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    lock_path = target.with_suffix(target.suffix + ".lock")

    # 1. Write content to a temp file in the same directory (same volume).
    fd, tmp_path_str = tempfile.mkstemp(
        dir=str(target.parent),
        prefix=f".{target.name}.",
        suffix=".tmp",
    )
    tmp_path = Path(tmp_path_str)

    try:
        with os.fdopen(fd, "w", encoding=encoding) as fh:
            fh.write(content)

        # 2-3. Lock sidecar then replace.
        _ensure_exists(lock_path)
        with locked_open(lock_path, "r+", timeout=lock_timeout):
            _replace_with_retry(str(tmp_path), str(target))

    except BaseException:
        # Clean up the temp file on any failure.
        tmp_path.unlink(missing_ok=True)
        raise

    return target


_REPLACE_RETRIES = 5
_REPLACE_DELAY = 0.05  # seconds


def _replace_with_retry(src: str, dst: str) -> None:
    """``os.replace`` with retry for transient Windows PermissionErrors.

    On Windows, antivirus scanners, search indexers, and other processes
    can briefly hold files open, causing ``os.replace`` to fail with
    ``PermissionError``.  A short retry loop handles this reliably.
    """
    for attempt in range(_REPLACE_RETRIES):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == _REPLACE_RETRIES - 1:
                raise
            time.sleep(_REPLACE_DELAY * (attempt + 1))


def _ensure_exists(path: Path) -> None:
    """Touch *path* if it doesn't exist, so ``locked_open`` can open it."""
    if not path.exists():
        path.touch()


# ---------------------------------------------------------------------------
# Temporary file / directory lifecycle
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def temp_file(
    *,
    suffix: str = ".tmp",
    prefix: str = "dsp-",
    dir: str | Path | None = None,  # noqa: A002
    content: str | None = None,
    encoding: str = "utf-8",
) -> Generator[Path]:
    """Create a temporary file that is cleaned up on context exit.

    If *content* is provided the file is pre-populated.  The yielded
    ``Path`` is always absolute.
    """
    dir_str = str(dir) if dir is not None else None
    fd, tmp_path_str = tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=dir_str)
    tmp = Path(tmp_path_str)

    try:
        if content is not None:
            with os.fdopen(fd, "w", encoding=encoding) as fh:
                fh.write(content)
        else:
            os.close(fd)
        yield tmp
    finally:
        tmp.unlink(missing_ok=True)


@contextlib.contextmanager
def temp_directory(
    *,
    suffix: str | None = None,
    prefix: str = "dsp-",
    dir: str | Path | None = None,  # noqa: A002
) -> Generator[Path]:
    """Create a temporary directory that is cleaned up on context exit.

    The yielded ``Path`` is always absolute.
    """
    dir_str = str(dir) if dir is not None else None
    tmp_dir = Path(tempfile.mkdtemp(suffix=suffix, prefix=prefix, dir=dir_str))

    try:
        yield tmp_dir
    finally:
        _rmtree_safe(tmp_dir)


def _rmtree_safe(path: Path) -> None:
    """Remove a directory tree, handling Windows read-only files."""
    import shutil

    def _on_error(func: object, err_path: str, exc_info: object) -> None:
        """Make read-only files writable then retry removal."""
        p = Path(err_path)
        p.chmod(0o700)
        p.unlink()

    shutil.rmtree(str(path), onexc=_on_error)
