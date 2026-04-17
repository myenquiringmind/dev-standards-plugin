"""Tests for hooks/_profiles.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hooks._profiles import build_tool_argv, detect_language, load_profile


def _write_profile(profiles_dir: Path, data: dict[str, object]) -> Path:
    path = profiles_dir / f"{data['name']}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.fixture
def project_with_profiles(tmp_dir: Path) -> Path:
    profiles_dir = tmp_dir / "config" / "profiles"
    profiles_dir.mkdir(parents=True)
    _write_profile(
        profiles_dir,
        {
            "name": "python",
            "detection": {"extensions": [".py"]},
            "tools": {
                "linter": {"command": "ruff check {file}"},
                "formatter": {"command": "ruff format {file}"},
            },
        },
    )
    _write_profile(
        profiles_dir,
        {
            "name": "javascript",
            "detection": {"extensions": [".js", ".jsx", ".ts", ".tsx"]},
            "tools": {
                "linter": {"command": "eslint {file}", "args": ["--fix"]},
                "formatter": {"command": "prettier --write {file}"},
            },
        },
    )
    return tmp_dir


class TestDetectLanguage:
    def test_matches_python_by_py_extension(self, project_with_profiles: Path) -> None:
        assert detect_language("/path/to/main.py", project_with_profiles) == "python"

    def test_matches_javascript_by_tsx_extension(self, project_with_profiles: Path) -> None:
        assert detect_language("/app/Button.tsx", project_with_profiles) == "javascript"

    def test_case_insensitive_extension(self, project_with_profiles: Path) -> None:
        assert detect_language("/path/Main.PY", project_with_profiles) == "python"

    def test_unknown_extension_returns_none(self, project_with_profiles: Path) -> None:
        assert detect_language("/path/main.rs", project_with_profiles) is None

    def test_no_extension_returns_none(self, project_with_profiles: Path) -> None:
        assert detect_language("/path/Makefile", project_with_profiles) is None

    def test_missing_profiles_dir_returns_none(self, tmp_dir: Path) -> None:
        assert detect_language("/path/main.py", tmp_dir) is None

    def test_malformed_profile_file_is_skipped(self, project_with_profiles: Path) -> None:
        bad = project_with_profiles / "config" / "profiles" / "bad.json"
        bad.write_text("not valid json", encoding="utf-8")
        # detect still works — bad file skipped, valid profiles still match
        assert detect_language("/path/main.py", project_with_profiles) == "python"


class TestLoadProfile:
    def test_returns_parsed_dict(self, project_with_profiles: Path) -> None:
        profile = load_profile("python", project_with_profiles)
        assert profile is not None
        assert profile["name"] == "python"

    def test_missing_profile_returns_none(self, project_with_profiles: Path) -> None:
        assert load_profile("rust", project_with_profiles) is None

    def test_malformed_json_returns_none(self, project_with_profiles: Path) -> None:
        path = project_with_profiles / "config" / "profiles" / "broken.json"
        path.write_text("not json", encoding="utf-8")
        assert load_profile("broken", project_with_profiles) is None


class TestBuildToolArgv:
    def test_substitutes_file(self) -> None:
        spec: dict[str, object] = {"command": "ruff check {file}"}
        assert build_tool_argv(spec, "/path/x.py") == ["ruff", "check", "/path/x.py"]

    def test_appends_args(self) -> None:
        spec: dict[str, object] = {"command": "eslint {file}", "args": ["--fix", "--quiet"]}
        argv = build_tool_argv(spec, "/path/x.js")
        assert argv is not None
        assert argv[0] == "eslint"
        assert argv[-2:] == ["--fix", "--quiet"]

    def test_none_spec_returns_none(self) -> None:
        assert build_tool_argv(None, "/path/x.py") is None

    def test_missing_command_returns_none(self) -> None:
        assert build_tool_argv({}, "/path/x.py") is None

    def test_empty_command_returns_none(self) -> None:
        assert build_tool_argv({"command": "   "}, "/path/x.py") is None

    def test_non_string_command_returns_none(self) -> None:
        assert build_tool_argv({"command": 42}, "/path/x.py") is None

    def test_windows_path_survives_shlex(self) -> None:
        argv = build_tool_argv({"command": "ruff check {file}"}, r"C:\proj\x.py")
        assert argv is not None
        assert argv[-1] == r"C:\proj\x.py"
