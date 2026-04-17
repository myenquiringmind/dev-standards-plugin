"""Tests for hooks/post_edit_lint.py."""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Mapping
from io import StringIO
from pathlib import Path

import pytest

from hooks import post_edit_lint


def _run(monkeypatch: pytest.MonkeyPatch, payload: Mapping[str, object]) -> int:
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(payload)))
    return post_edit_lint.main()


def _write_python_profile(project_dir: Path) -> None:
    profiles = project_dir / "config" / "profiles"
    profiles.mkdir(parents=True)
    (profiles / "python.json").write_text(
        json.dumps(
            {
                "name": "python",
                "detection": {"extensions": [".py"]},
                "tools": {"linter": {"command": "ruff check {file}"}},
            }
        ),
        encoding="utf-8",
    )


class TestLanguageDetection:
    def test_unmatched_extension_is_silent_noop(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        f = tmp_dir / "readme.md"
        f.write_text("hi", encoding="utf-8")
        monkeypatch.setattr(post_edit_lint, "get_project_dir", lambda: tmp_dir)

        rc = _run(monkeypatch, {"tool_name": "Edit", "tool_input": {"file_path": str(f)}})
        captured = capsys.readouterr()
        assert rc == 0
        assert captured.err == ""

    def test_missing_file_is_noop(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(post_edit_lint, "get_project_dir", lambda: tmp_dir)
        payload = {"tool_name": "Edit", "tool_input": {"file_path": str(tmp_dir / "ghost.py")}}
        assert _run(monkeypatch, payload) == 0

    def test_no_file_path_is_noop(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(post_edit_lint, "get_project_dir", lambda: tmp_dir)
        assert _run(monkeypatch, {"tool_name": "Edit", "tool_input": {}}) == 0


class TestLinterInvocation:
    def test_runs_and_exits_zero_on_success(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _write_python_profile(tmp_dir)
        f = tmp_dir / "main.py"
        f.write_text("x = 1\n", encoding="utf-8")
        monkeypatch.setattr(post_edit_lint, "get_project_dir", lambda: tmp_dir)

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

        monkeypatch.setattr("hooks.post_edit_lint.subprocess.run", fake_run)

        rc = _run(monkeypatch, {"tool_name": "Edit", "tool_input": {"file_path": str(f)}})
        captured = capsys.readouterr()

        assert rc == 0
        assert captured.err == ""
        assert len(captured_argv) == 1
        assert captured_argv[0][:2] == ["ruff", "check"]
        assert captured_argv[0][-1].endswith("main.py")

    def test_reports_linter_output_on_failure(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _write_python_profile(tmp_dir)
        f = tmp_dir / "broken.py"
        f.write_text("x=1", encoding="utf-8")
        monkeypatch.setattr(post_edit_lint, "get_project_dir", lambda: tmp_dir)

        def fake_run(
            argv: list[str],
            *,
            capture_output: bool,
            text: bool,
            timeout: int,
            check: bool,
        ) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(argv, 1, stdout="E501 line too long", stderr="")

        monkeypatch.setattr("hooks.post_edit_lint.subprocess.run", fake_run)

        rc = _run(monkeypatch, {"tool_name": "Edit", "tool_input": {"file_path": str(f)}})
        captured = capsys.readouterr()

        assert rc == 0
        assert "python issues in broken.py" in captured.err
        assert "E501" in captured.err

    def test_missing_executable_logs_and_exits_zero(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _write_python_profile(tmp_dir)
        f = tmp_dir / "main.py"
        f.write_text("x = 1\n", encoding="utf-8")
        monkeypatch.setattr(post_edit_lint, "get_project_dir", lambda: tmp_dir)

        def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
            raise FileNotFoundError("no ruff")

        monkeypatch.setattr("hooks.post_edit_lint.subprocess.run", fake_run)

        rc = _run(monkeypatch, {"tool_name": "Edit", "tool_input": {"file_path": str(f)}})
        captured = capsys.readouterr()
        assert rc == 0
        assert "not found on PATH" in captured.err

    def test_timeout_logs_and_exits_zero(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _write_python_profile(tmp_dir)
        f = tmp_dir / "main.py"
        f.write_text("x = 1\n", encoding="utf-8")
        monkeypatch.setattr(post_edit_lint, "get_project_dir", lambda: tmp_dir)

        def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
            raise subprocess.TimeoutExpired(cmd=["ruff"], timeout=5)

        monkeypatch.setattr("hooks.post_edit_lint.subprocess.run", fake_run)

        rc = _run(monkeypatch, {"tool_name": "Edit", "tool_input": {"file_path": str(f)}})
        captured = capsys.readouterr()
        assert rc == 0
        assert "timed out" in captured.err


class TestProfileWithoutLinter:
    def test_skip_when_profile_has_no_linter(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        profiles = tmp_dir / "config" / "profiles"
        profiles.mkdir(parents=True)
        (profiles / "python.json").write_text(
            json.dumps(
                {
                    "name": "python",
                    "detection": {"extensions": [".py"]},
                    "tools": {},  # no linter
                }
            ),
            encoding="utf-8",
        )
        f = tmp_dir / "main.py"
        f.write_text("x = 1\n", encoding="utf-8")
        monkeypatch.setattr(post_edit_lint, "get_project_dir", lambda: tmp_dir)

        rc = _run(monkeypatch, {"tool_name": "Edit", "tool_input": {"file_path": str(f)}})
        captured = capsys.readouterr()
        assert rc == 0
        assert captured.err == ""


class TestMultiEditFilesArray:
    def test_extracts_first_file_from_files_array(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_python_profile(tmp_dir)
        f = tmp_dir / "x.py"
        f.write_text("x = 1\n", encoding="utf-8")
        monkeypatch.setattr(post_edit_lint, "get_project_dir", lambda: tmp_dir)

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

        monkeypatch.setattr("hooks.post_edit_lint.subprocess.run", fake_run)

        payload = {
            "tool_name": "MultiEdit",
            "tool_input": {"files": [{"file_path": str(f)}]},
        }
        _run(monkeypatch, payload)
        assert captured_argv
        assert captured_argv[0][-1].endswith("x.py")
