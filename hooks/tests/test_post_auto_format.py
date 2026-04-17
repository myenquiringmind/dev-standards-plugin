"""Tests for hooks/post_auto_format.py."""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Mapping
from io import StringIO
from pathlib import Path

import pytest

from hooks import post_auto_format


def _run(monkeypatch: pytest.MonkeyPatch, payload: Mapping[str, object]) -> int:
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(payload)))
    return post_auto_format.main()


def _write_python_profile(project_dir: Path) -> None:
    profiles = project_dir / "config" / "profiles"
    profiles.mkdir(parents=True)
    (profiles / "python.json").write_text(
        json.dumps(
            {
                "name": "python",
                "detection": {"extensions": [".py"]},
                "tools": {"formatter": {"command": "ruff format {file}"}},
            }
        ),
        encoding="utf-8",
    )


class TestHappyPath:
    def test_runs_formatter_successfully(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _write_python_profile(tmp_dir)
        f = tmp_dir / "main.py"
        f.write_text("x=1\n", encoding="utf-8")
        monkeypatch.setattr(post_auto_format, "get_project_dir", lambda: tmp_dir)

        captured_argv: list[list[str]] = []

        def fake_run(
            argv: list[str],
            *,
            capture_output: bool,
            text: bool,
            timeout: int,
            check: bool,
        ) -> subprocess.CompletedProcess[str]:
            captured_argv.append(argv)
            return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

        monkeypatch.setattr("hooks.post_auto_format.subprocess.run", fake_run)

        rc = _run(monkeypatch, {"tool_name": "Write", "tool_input": {"file_path": str(f)}})
        captured = capsys.readouterr()

        assert rc == 0
        assert captured.err == ""
        assert captured_argv[0][:2] == ["ruff", "format"]


class TestFormatterFailure:
    def test_reports_failure_output(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _write_python_profile(tmp_dir)
        f = tmp_dir / "broken.py"
        f.write_text("def x(\n", encoding="utf-8")
        monkeypatch.setattr(post_auto_format, "get_project_dir", lambda: tmp_dir)

        def fake_run(
            argv: list[str],
            *,
            capture_output: bool,
            text: bool,
            timeout: int,
            check: bool,
        ) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                argv,
                1,
                stdout="",
                stderr="error: syntax",
            )

        monkeypatch.setattr("hooks.post_auto_format.subprocess.run", fake_run)

        rc = _run(monkeypatch, {"tool_name": "Write", "tool_input": {"file_path": str(f)}})
        captured = capsys.readouterr()

        assert rc == 0
        assert "formatter failed for broken.py" in captured.err


class TestMissingExecutable:
    def test_file_not_found_is_logged_not_raised(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _write_python_profile(tmp_dir)
        f = tmp_dir / "main.py"
        f.write_text("x = 1\n", encoding="utf-8")
        monkeypatch.setattr(post_auto_format, "get_project_dir", lambda: tmp_dir)

        def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
            raise FileNotFoundError("no ruff")

        monkeypatch.setattr("hooks.post_auto_format.subprocess.run", fake_run)

        rc = _run(monkeypatch, {"tool_name": "Edit", "tool_input": {"file_path": str(f)}})
        captured = capsys.readouterr()
        assert rc == 0
        assert "not found on PATH" in captured.err


class TestTimeout:
    def test_timeout_exits_zero(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _write_python_profile(tmp_dir)
        f = tmp_dir / "main.py"
        f.write_text("x = 1\n", encoding="utf-8")
        monkeypatch.setattr(post_auto_format, "get_project_dir", lambda: tmp_dir)

        def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
            raise subprocess.TimeoutExpired(cmd=["ruff"], timeout=5)

        monkeypatch.setattr("hooks.post_auto_format.subprocess.run", fake_run)

        rc = _run(monkeypatch, {"tool_name": "Edit", "tool_input": {"file_path": str(f)}})
        captured = capsys.readouterr()
        assert rc == 0
        assert "timed out" in captured.err


class TestNoProfile:
    def test_unmatched_extension_is_silent(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        (tmp_dir / "config" / "profiles").mkdir(parents=True)
        f = tmp_dir / "readme.md"
        f.write_text("hi", encoding="utf-8")
        monkeypatch.setattr(post_auto_format, "get_project_dir", lambda: tmp_dir)

        rc = _run(monkeypatch, {"tool_name": "Write", "tool_input": {"file_path": str(f)}})
        captured = capsys.readouterr()
        assert rc == 0
        assert captured.err == ""


class TestMalformedInput:
    def test_missing_file_path(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(post_auto_format, "get_project_dir", lambda: tmp_dir)
        assert _run(monkeypatch, {"tool_name": "Edit", "tool_input": {}}) == 0

    def test_tool_input_not_a_dict(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(post_auto_format, "get_project_dir", lambda: tmp_dir)
        payload: Mapping[str, object] = {"tool_name": "Edit", "tool_input": "bad"}
        assert _run(monkeypatch, payload) == 0
