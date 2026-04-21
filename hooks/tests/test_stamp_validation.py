"""Tests for hooks/stamp_validation.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hooks import stamp_validation

SCHEMA_SOURCE = Path(__file__).resolve().parent.parent.parent / "schemas" / "stamp.schema.json"


@pytest.fixture
def project_dir_with_schema(tmp_dir: Path) -> Path:
    schemas = tmp_dir / "schemas"
    schemas.mkdir()
    (schemas / "stamp.schema.json").write_text(
        SCHEMA_SOURCE.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return tmp_dir


def _run(
    monkeypatch: pytest.MonkeyPatch,
    project_dir: Path,
    branch: str,
    argv: list[str],
) -> int:
    monkeypatch.setattr(stamp_validation, "get_project_dir", lambda: project_dir)
    monkeypatch.setattr(stamp_validation, "get_current_branch", lambda _d=None: branch)
    return stamp_validation.main(argv)


class TestHappyPath:
    def test_writes_code_gate_stamp(
        self,
        project_dir_with_schema: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        rc = _run(
            monkeypatch,
            project_dir_with_schema,
            "feat/test",
            ["--gate", "code", "--step", "ruff-check", "--step", "pytest"],
        )
        captured = capsys.readouterr()
        assert rc == 0
        assert ".validation_stamp" in captured.out

        stamp_file = project_dir_with_schema / ".validation_stamp"
        stamp = json.loads(stamp_file.read_text(encoding="utf-8"))
        assert stamp["gate"] == "code"
        assert stamp["branch"] == "feat/test"
        assert stamp["steps"] == ["ruff-check", "pytest"]
        assert stamp["ttl_seconds"] == 900
        assert stamp["version"] == "1.0.0"
        assert "plugin_commit" not in stamp

    def test_frontend_gate_filename(
        self,
        project_dir_with_schema: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        rc = _run(
            monkeypatch,
            project_dir_with_schema,
            "feat/ui",
            ["--gate", "frontend", "--step", "eslint"],
        )
        assert rc == 0
        assert (project_dir_with_schema / ".frontend_validation_stamp").exists()

    @pytest.mark.parametrize(
        "gate,filename",
        [
            ("code", ".validation_stamp"),
            ("frontend", ".frontend_validation_stamp"),
            ("agent", ".agent_validation_stamp"),
            ("db", ".db_validation_stamp"),
            ("api", ".api_validation_stamp"),
        ],
    )
    def test_filename_for_every_gate(
        self,
        project_dir_with_schema: Path,
        monkeypatch: pytest.MonkeyPatch,
        gate: str,
        filename: str,
    ) -> None:
        rc = _run(
            monkeypatch,
            project_dir_with_schema,
            "feat/x",
            ["--gate", gate, "--step", "some-step"],
        )
        assert rc == 0
        assert (project_dir_with_schema / filename).exists()

    def test_plugin_commit_round_trips(
        self,
        project_dir_with_schema: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        rc = _run(
            monkeypatch,
            project_dir_with_schema,
            "feat/x",
            ["--gate", "code", "--step", "s1", "--plugin-commit", "abc1234"],
        )
        assert rc == 0
        stamp = json.loads(
            (project_dir_with_schema / ".validation_stamp").read_text(encoding="utf-8")
        )
        assert stamp["plugin_commit"] == "abc1234"


class TestSchemaViolation:
    def test_invalid_plugin_commit_rejected(
        self,
        project_dir_with_schema: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        rc = _run(
            monkeypatch,
            project_dir_with_schema,
            "feat/x",
            ["--gate", "code", "--step", "s1", "--plugin-commit", "not-a-sha"],
        )
        captured = capsys.readouterr()
        assert rc == 1
        assert "schema error" in captured.err
        assert not (project_dir_with_schema / ".validation_stamp").exists()


class TestBranchResolution:
    def test_empty_branch_fails(
        self,
        project_dir_with_schema: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        rc = _run(
            monkeypatch,
            project_dir_with_schema,
            "",
            ["--gate", "code", "--step", "s1"],
        )
        captured = capsys.readouterr()
        assert rc == 1
        assert "could not determine current branch" in captured.err


class TestMissingArgs:
    def test_missing_gate(
        self,
        project_dir_with_schema: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        rc = _run(monkeypatch, project_dir_with_schema, "feat/x", ["--step", "s1"])
        assert rc != 0

    def test_missing_step(
        self,
        project_dir_with_schema: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        rc = _run(monkeypatch, project_dir_with_schema, "feat/x", ["--gate", "code"])
        assert rc != 0


class TestSchemaLoadFailure:
    def test_missing_schema_reports_error(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # No schemas/stamp.schema.json under tmp_dir
        rc = _run(
            monkeypatch,
            tmp_dir,
            "feat/x",
            ["--gate", "code", "--step", "s1"],
        )
        captured = capsys.readouterr()
        assert rc == 1
        assert "could not load schema" in captured.err


class TestAtomicWriteFailure:
    def test_oserror_during_write(
        self,
        project_dir_with_schema: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        def boom(*_args: object, **_kwargs: object) -> Path:
            raise OSError("disk full")

        monkeypatch.setattr("hooks.stamp_validation.atomic_write", boom)
        rc = _run(
            monkeypatch,
            project_dir_with_schema,
            "feat/x",
            ["--gate", "code", "--step", "s1"],
        )
        captured = capsys.readouterr()
        assert rc == 1
        assert "could not write stamp" in captured.err


class TestTimestampFormat:
    def test_iso_8601_utc(
        self,
        project_dir_with_schema: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _run(
            monkeypatch,
            project_dir_with_schema,
            "feat/x",
            ["--gate", "code", "--step", "s1"],
        )
        stamp = json.loads(
            (project_dir_with_schema / ".validation_stamp").read_text(encoding="utf-8")
        )
        # Shape: 2026-04-17T06:12:34Z
        assert len(stamp["timestamp"]) == 20
        assert stamp["timestamp"].endswith("Z")
