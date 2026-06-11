"""Tests for hooks/scaffold_red_gate.py."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from hooks import scaffold_red_gate
from hooks.scaffold_red_gate import Verdict


def _write_python_profile(project_dir: Path, *, test_runner: bool = True) -> None:
    profiles = project_dir / "config" / "profiles"
    profiles.mkdir(parents=True)
    tools: dict[str, Any] = {
        "formatter": {"command": "ruff format {file}"},
        "linter": {"command": "ruff check {file}"},
    }
    if test_runner:
        tools["testRunner"] = {"command": "pytest {file}"}
    (profiles / "python.json").write_text(
        json.dumps({"name": "python", "tools": tools, "validationSteps": ["pytest"]}),
        encoding="utf-8",
    )


class _FakeCompleted:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class TestParseCounts:
    def test_failures_only(self) -> None:
        assert scaffold_red_gate._parse_counts("= 3 failed in 0.10s =") == {
            "passed": 0,
            "failed": 3,
            "error": 0,
        }

    def test_failed_and_error(self) -> None:
        counts = scaffold_red_gate._parse_counts("= 2 failed, 1 error in 0.2s =")
        assert counts["failed"] == 2
        assert counts["error"] == 1

    def test_plural_errors_label(self) -> None:
        assert scaffold_red_gate._parse_counts("= 2 errors in 0.1s =")["error"] == 2

    def test_no_counts(self) -> None:
        assert scaffold_red_gate._parse_counts("no tests ran in 0.01s") == {
            "passed": 0,
            "failed": 0,
            "error": 0,
        }


class TestClassify:
    def test_only_failures_is_red(self) -> None:
        assert scaffold_red_gate.classify("= 3 failed in 0.1s =", 1) is Verdict.RED

    def test_any_error_is_errored(self) -> None:
        assert scaffold_red_gate.classify("= 2 failed, 1 error =", 1) is Verdict.ERRORED

    def test_any_pass_is_passed(self) -> None:
        assert scaffold_red_gate.classify("= 1 passed, 2 failed =", 1) is Verdict.PASSED

    def test_no_counts_rc_zero_is_passed(self) -> None:
        assert scaffold_red_gate.classify("everything fine", 0) is Verdict.PASSED

    def test_no_counts_rc_nonzero_is_unknown(self) -> None:
        assert scaffold_red_gate.classify("segfault", 139) is Verdict.UNKNOWN

    def test_no_tests_collected_is_no_tests(self) -> None:
        # pytest exits 5 with no count summary when it collects nothing.
        assert scaffold_red_gate.classify("no tests ran in 0.01s", 5) is Verdict.NO_TESTS


class TestRunnerArgv:
    def test_drops_placeholder_and_appends_tests(self, tmp_dir: Path) -> None:
        _write_python_profile(tmp_dir)
        from hooks._profiles import load_profile

        profile = load_profile("python", tmp_dir)
        assert profile is not None
        argv = scaffold_red_gate._runner_argv(profile, ["tests/test_a.py", "tests/test_b.py"])
        assert argv == ["pytest", "tests/test_a.py", "tests/test_b.py"]

    def test_missing_test_runner_returns_none(self, tmp_dir: Path) -> None:
        _write_python_profile(tmp_dir, test_runner=False)
        from hooks._profiles import load_profile

        profile = load_profile("python", tmp_dir)
        assert profile is not None
        assert scaffold_red_gate._runner_argv(profile, ["t.py"]) is None


class TestRunGate:
    def test_no_profile_is_unknown(self, tmp_dir: Path) -> None:
        verdict, detail = scaffold_red_gate.run_gate("nope", ["t.py"], tmp_dir)
        assert verdict is Verdict.UNKNOWN
        assert "no profile" in detail

    def test_red_run(self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_python_profile(tmp_dir)
        monkeypatch.setattr(
            "subprocess.run", lambda *a, **k: _FakeCompleted(1, stdout="= 3 failed in 0.1s =")
        )
        verdict, _ = scaffold_red_gate.run_gate("python", ["t.py"], tmp_dir)
        assert verdict is Verdict.RED

    def test_errored_run(self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_python_profile(tmp_dir)
        monkeypatch.setattr(
            "subprocess.run",
            lambda *a, **k: _FakeCompleted(1, stdout="= 1 failed, 2 error in 0.1s ="),
        )
        verdict, _ = scaffold_red_gate.run_gate("python", ["t.py"], tmp_dir)
        assert verdict is Verdict.ERRORED

    def test_runner_not_found_is_unknown(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_python_profile(tmp_dir)

        def boom(argv: list[str], **_: Any) -> _FakeCompleted:
            raise FileNotFoundError(argv[0])

        monkeypatch.setattr("subprocess.run", boom)
        verdict, detail = scaffold_red_gate.run_gate("python", ["t.py"], tmp_dir)
        assert verdict is Verdict.UNKNOWN
        assert "not found" in detail


class TestMain:
    def test_red_exits_zero(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write_python_profile(tmp_dir)
        monkeypatch.setattr(scaffold_red_gate, "get_project_dir", lambda: tmp_dir)
        monkeypatch.setattr(
            "subprocess.run", lambda *a, **k: _FakeCompleted(1, stdout="= 2 failed in 0.1s =")
        )
        rc = scaffold_red_gate.main(["--language", "python", "--test", "t.py"])
        assert rc == 0
        assert "RED confirmed" in capsys.readouterr().out

    def test_passed_exits_two(
        self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write_python_profile(tmp_dir)
        monkeypatch.setattr(scaffold_red_gate, "get_project_dir", lambda: tmp_dir)
        monkeypatch.setattr(
            "subprocess.run", lambda *a, **k: _FakeCompleted(0, stdout="= 2 passed in 0.1s =")
        )
        rc = scaffold_red_gate.main(["--language", "python", "--test", "t.py"])
        assert rc == 2
        assert "NOT_RED" in capsys.readouterr().err

    def test_no_profile_exits_one(self, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(scaffold_red_gate, "get_project_dir", lambda: tmp_dir)
        rc = scaffold_red_gate.main(["--language", "nope", "--test", "t.py"])
        assert rc == 1

    def test_bad_args_exits_two(self) -> None:
        assert scaffold_red_gate.main([]) == 2
