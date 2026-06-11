"""Tests for hooks/run_cli_checks.py."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from hooks import run_cli_checks
from hooks._profiles import load_profile


def _write_python_profile(project_dir: Path) -> None:
    profiles = project_dir / "config" / "profiles"
    profiles.mkdir(parents=True)
    (profiles / "python.json").write_text(
        json.dumps(
            {
                "name": "python",
                "tools": {
                    "formatter": {"command": "ruff format {file}"},
                    "linter": {"command": "ruff check --fix {file}"},
                    "typeChecker": {"command": "mypy {file} --strict"},
                    "testRunner": {"command": "pytest {file}"},
                },
                "validationSteps": [
                    "ruff-check",
                    "ruff-format",
                    "mypy-strict",
                    "pytest",
                    "objective-verifier",
                ],
            }
        ),
        encoding="utf-8",
    )


class _FakeCompleted:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class TestBuildCheckArgv:
    def test_linter_strips_fix_and_placeholder_and_appends_targets(self) -> None:
        argv = run_cli_checks._build_check_argv(
            "linter", {"command": "ruff check --fix {file}"}, ["hooks/"]
        )
        assert argv == ["ruff", "check", "hooks/"]

    def test_formatter_adds_check_flag(self) -> None:
        argv = run_cli_checks._build_check_argv(
            "formatter", {"command": "ruff format {file}"}, ["hooks/"]
        )
        assert argv == ["ruff", "format", "--check", "hooks/"]

    def test_type_checker_keeps_trailing_flags(self) -> None:
        argv = run_cli_checks._build_check_argv(
            "typeChecker", {"command": "mypy {file} --strict"}, ["hooks/"]
        )
        assert argv == ["mypy", "--strict", "hooks/"]

    def test_test_runner_runs_whole_suite_without_targets(self) -> None:
        argv = run_cli_checks._build_check_argv(
            "testRunner", {"command": "pytest {file}"}, ["hooks/"]
        )
        assert argv == ["pytest"]

    def test_extra_args_are_appended(self) -> None:
        argv = run_cli_checks._build_check_argv(
            "linter", {"command": "eslint {file}", "args": ["--max-warnings=0"]}, ["src/"]
        )
        assert argv == ["eslint", "--max-warnings=0", "src/"]

    def test_missing_command_returns_none(self) -> None:
        assert run_cli_checks._build_check_argv("linter", {}, ["."]) is None


class TestPlanSteps:
    def test_only_cli_steps_are_planned(self, tmp_dir: Path) -> None:
        _write_python_profile(tmp_dir)
        profile = load_profile("python", tmp_dir)
        assert profile is not None
        planned = run_cli_checks._plan_steps(profile, ["."])
        names = [name for name, _ in planned]
        # objective-verifier is an agent step → excluded.
        assert names == ["ruff-check", "ruff-format", "mypy-strict", "pytest"]


class TestRunChecks:
    def test_missing_profile_reports_error(self, tmp_dir: Path) -> None:
        summary = run_cli_checks.run_checks("nope", ["."], tmp_dir)
        assert summary["all_passed"] is False
        assert "no profile" in summary["error"]
        assert summary["steps"] == []

    def test_all_steps_pass(self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_python_profile(tmp_dir)
        monkeypatch.setattr(
            "subprocess.run", lambda *a, **k: _FakeCompleted(0, stdout="All checks passed!")
        )
        summary = run_cli_checks.run_checks("python", ["."], tmp_dir)
        assert summary["all_passed"] is True
        assert {s["name"] for s in summary["steps"]} == {
            "ruff-check",
            "ruff-format",
            "mypy-strict",
            "pytest",
        }
        assert all(s["passed"] for s in summary["steps"])

    def test_one_failing_step_fails_overall(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_python_profile(tmp_dir)

        def fake_run(argv: list[str], **_: Any) -> _FakeCompleted:
            if argv[0] == "mypy":
                return _FakeCompleted(1, stderr="error: type mismatch")
            return _FakeCompleted(0)

        monkeypatch.setattr("subprocess.run", fake_run)
        summary = run_cli_checks.run_checks("python", ["."], tmp_dir)
        assert summary["all_passed"] is False
        failed = [s for s in summary["steps"] if not s["passed"]]
        assert len(failed) == 1
        assert failed[0]["name"] == "mypy-strict"
        assert "type mismatch" in failed[0]["output"]

    def test_missing_tool_is_a_failed_step(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_python_profile(tmp_dir)

        def fake_run(argv: list[str], **_: Any) -> _FakeCompleted:
            raise FileNotFoundError(argv[0])

        monkeypatch.setattr("subprocess.run", fake_run)
        summary = run_cli_checks.run_checks("python", ["."], tmp_dir)
        assert summary["all_passed"] is False
        assert all("not found" in s["output"] for s in summary["steps"])

    def test_timeout_is_a_failed_step(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_python_profile(tmp_dir)

        def fake_run(argv: list[str], **_: Any) -> _FakeCompleted:
            raise subprocess.TimeoutExpired(cmd=argv, timeout=1)

        monkeypatch.setattr("subprocess.run", fake_run)
        summary = run_cli_checks.run_checks("python", ["."], tmp_dir)
        assert summary["all_passed"] is False
        assert all("timed out" in s["output"] for s in summary["steps"])


class TestMain:
    def test_exit_zero_when_all_pass(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write_python_profile(tmp_dir)
        monkeypatch.setattr(run_cli_checks, "get_project_dir", lambda: tmp_dir)
        monkeypatch.setattr("subprocess.run", lambda *a, **k: _FakeCompleted(0))
        rc = run_cli_checks.main(["--language", "python"])
        out = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert out["all_passed"] is True
        assert out["language"] == "python"

    def test_exit_one_when_a_step_fails(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write_python_profile(tmp_dir)
        monkeypatch.setattr(run_cli_checks, "get_project_dir", lambda: tmp_dir)
        monkeypatch.setattr("subprocess.run", lambda *a, **k: _FakeCompleted(1, stderr="boom"))
        rc = run_cli_checks.main(["--language", "python"])
        capsys.readouterr()
        assert rc == 1

    def test_bad_args_exit_two(self) -> None:
        assert run_cli_checks.main([]) == 2
