"""Tests for hooks/session_start_gitignore_audit.py.

Covers Phase 1 exit gate assertion #13 (warns on deliberately
stripped .gitignore).
"""

from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path

import pytest

from hooks import session_start_gitignore_audit

FULL_GITIGNORE = """
.env
.env.*
*.pem
*.key
.validation_stamp*
.context_pct
session-state.md.injected
tmp/
.venv/
node_modules/
""".strip()


def _patch_io(
    monkeypatch: pytest.MonkeyPatch,
    project_dir: Path,
) -> None:
    monkeypatch.setattr(sys, "stdin", StringIO("{}"))
    monkeypatch.setattr(session_start_gitignore_audit, "get_project_dir", lambda: project_dir)


class TestFullCoverage:
    def test_no_warning_when_all_patterns_present(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        (tmp_dir / ".gitignore").write_text(FULL_GITIGNORE, encoding="utf-8")
        _patch_io(monkeypatch, tmp_dir)

        rc = session_start_gitignore_audit.main()
        captured = capsys.readouterr()

        assert rc == 0
        assert captured.out == ""
        assert captured.err == ""

    def test_comments_and_blank_lines_ignored(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        content = "# Secrets\n\n" + FULL_GITIGNORE + "\n# trailing comment\n"
        (tmp_dir / ".gitignore").write_text(content, encoding="utf-8")
        _patch_io(monkeypatch, tmp_dir)

        rc = session_start_gitignore_audit.main()
        captured = capsys.readouterr()
        assert rc == 0
        assert captured.err == ""


class TestMissingPatterns:
    def test_missing_patterns_warns_on_stderr_and_context(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Strip out stamp and context patterns
        stripped = "\n".join(
            line
            for line in FULL_GITIGNORE.splitlines()
            if line not in (".validation_stamp*", ".context_pct")
        )
        (tmp_dir / ".gitignore").write_text(stripped, encoding="utf-8")
        _patch_io(monkeypatch, tmp_dir)

        rc = session_start_gitignore_audit.main()
        captured = capsys.readouterr()

        assert rc == 0
        assert ".validation_stamp*" in captured.err
        assert ".context_pct" in captured.err

        payload = json.loads(captured.out)
        assert "additionalContext" in payload
        assert ".validation_stamp*" in payload["additionalContext"]
        assert ".context_pct" in payload["additionalContext"]

    def test_deliberately_stripped_gitignore_triggers_full_warning(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Phase 1 exit gate assertion #13."""
        (tmp_dir / ".gitignore").write_text("# empty\n", encoding="utf-8")
        _patch_io(monkeypatch, tmp_dir)

        rc = session_start_gitignore_audit.main()
        captured = capsys.readouterr()

        assert rc == 0
        assert captured.err
        payload = json.loads(captured.out)
        # All 10 required patterns should be flagged
        for pattern in (
            ".env",
            ".env.*",
            "*.pem",
            "*.key",
            ".validation_stamp*",
            ".context_pct",
            "session-state.md.injected",
            "tmp/",
            ".venv/",
            "node_modules/",
        ):
            assert pattern in payload["additionalContext"]


class TestPathVariants:
    def test_leading_slash_variant_still_matches(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # /.venv/ is equivalent to .venv/ for root-relative .gitignore entries
        content = FULL_GITIGNORE.replace(".venv/", "/.venv/")
        (tmp_dir / ".gitignore").write_text(content, encoding="utf-8")
        _patch_io(monkeypatch, tmp_dir)

        rc = session_start_gitignore_audit.main()
        captured = capsys.readouterr()
        assert rc == 0
        assert ".venv" not in captured.err


class TestMissingGitignore:
    def test_no_gitignore_file_reports_all_missing(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _patch_io(monkeypatch, tmp_dir)
        rc = session_start_gitignore_audit.main()
        captured = capsys.readouterr()
        assert rc == 0
        assert "missing required patterns" in captured.err
