"""Shared fixtures for hooks test suite."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from hooks._os_safe import temp_directory

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def tmp_dir() -> Generator[Path]:
    """Yield a temporary directory that is cleaned up after the test."""
    with temp_directory(prefix="dsp-test-") as d:
        yield d


@pytest.fixture
def tmp_git_repo(tmp_dir: Path) -> Path:
    """Create a minimal git repo in a temp directory and return its path."""
    subprocess.run(
        ["git", "init"],
        cwd=str(tmp_dir),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init"],
        cwd=str(tmp_dir),
        check=True,
        capture_output=True,
    )
    return tmp_dir


@pytest.fixture
def fake_hook_input(tmp_dir: Path) -> Path:
    """Write a minimal hook input JSON file and return its path."""
    payload = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": str(tmp_dir / "example.py"),
            "old_string": "",
            "new_string": "x = 1",
        },
    }
    input_file = tmp_dir / "hook_input.json"
    input_file.write_text(json.dumps(payload), encoding="utf-8")
    return input_file
