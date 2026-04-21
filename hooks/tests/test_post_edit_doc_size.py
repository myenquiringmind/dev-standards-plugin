"""Tests for hooks/post_edit_doc_size.py.

Covers Phase 1 exit gate assertion #11: 201-line markdown blocked,
150-line allowed.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from io import StringIO
from pathlib import Path

import pytest

from hooks import post_edit_doc_size


def _patch_io(
    monkeypatch: pytest.MonkeyPatch,
    payload: Mapping[str, object],
    project_dir: Path,
) -> None:
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(payload)))
    monkeypatch.setattr(post_edit_doc_size, "get_project_dir", lambda: project_dir)


def _write_markdown(path: Path, line_count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(f"line {i}" for i in range(line_count)), encoding="utf-8")


def _write_config(project_dir: Path, config: dict[str, object]) -> None:
    config_dir = project_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "doc-size-limits.json").write_text(json.dumps(config), encoding="utf-8")


class TestPhase1ExitGateAssertion11:
    """201-line blocks, 150-line allowed."""

    def test_201_line_markdown_blocked(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _write_config(tmp_dir, {"default": 200, "patterns": []})
        md = tmp_dir / "big.md"
        _write_markdown(md, 201)

        _patch_io(
            monkeypatch,
            {"tool_name": "Write", "tool_input": {"file_path": str(md)}},
            tmp_dir,
        )

        rc = post_edit_doc_size.main()
        captured = capsys.readouterr()

        assert rc == 2
        assert "201 lines" in captured.err
        assert "limit 200" in captured.err

    def test_150_line_markdown_allowed(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _write_config(tmp_dir, {"default": 200, "patterns": []})
        md = tmp_dir / "fine.md"
        _write_markdown(md, 150)

        _patch_io(
            monkeypatch,
            {"tool_name": "Write", "tool_input": {"file_path": str(md)}},
            tmp_dir,
        )

        rc = post_edit_doc_size.main()
        captured = capsys.readouterr()

        assert rc == 0
        assert captured.err == ""


class TestPatternMatching:
    def test_specific_pattern_overrides_default(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_config(
            tmp_dir,
            {
                "default": 200,
                "patterns": [{"glob": "**/CHANGELOG.md", "limit": -1}],
            },
        )
        md = tmp_dir / "CHANGELOG.md"
        _write_markdown(md, 500)

        _patch_io(
            monkeypatch,
            {"tool_name": "Write", "tool_input": {"file_path": str(md)}},
            tmp_dir,
        )

        assert post_edit_doc_size.main() == 0

    def test_first_matching_pattern_wins(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_config(
            tmp_dir,
            {
                "default": 500,
                "patterns": [
                    {"glob": "docs/**/*.md", "limit": 200},
                    {"glob": "**/*.md", "limit": 400},
                ],
            },
        )
        md = tmp_dir / "docs" / "deep.md"
        _write_markdown(md, 300)

        _patch_io(
            monkeypatch,
            {"tool_name": "Write", "tool_input": {"file_path": str(md)}},
            tmp_dir,
        )

        # 300 > 200, so docs/** pattern blocks
        assert post_edit_doc_size.main() == 2

    def test_negative_limit_exempts(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_config(
            tmp_dir,
            {
                "default": 200,
                "patterns": [
                    {
                        "glob": "docs/decision-records/v2-architecture-planning-session.md",
                        "limit": -1,
                    }
                ],
            },
        )
        md = tmp_dir / "docs" / "decision-records" / "v2-architecture-planning-session.md"
        _write_markdown(md, 3000)

        _patch_io(
            monkeypatch,
            {"tool_name": "Write", "tool_input": {"file_path": str(md)}},
            tmp_dir,
        )
        assert post_edit_doc_size.main() == 0


class TestNonMarkdown:
    @pytest.mark.parametrize("suffix", [".py", ".json", ".txt", ""])
    def test_non_markdown_is_noop(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        suffix: str,
    ) -> None:
        _write_config(tmp_dir, {"default": 10, "patterns": []})
        f = tmp_dir / f"big{suffix}"
        _write_markdown(f, 500)

        _patch_io(
            monkeypatch,
            {"tool_name": "Write", "tool_input": {"file_path": str(f)}},
            tmp_dir,
        )
        assert post_edit_doc_size.main() == 0


class TestMissingConfig:
    def test_missing_config_uses_hard_default(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        md = tmp_dir / "big.md"
        _write_markdown(md, 201)

        _patch_io(
            monkeypatch,
            {"tool_name": "Write", "tool_input": {"file_path": str(md)}},
            tmp_dir,
        )
        # No config → default 200 applies → 201 blocks
        assert post_edit_doc_size.main() == 2

    def test_malformed_config_still_defaults(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        config_dir = tmp_dir / "config"
        config_dir.mkdir()
        (config_dir / "doc-size-limits.json").write_text("not json", encoding="utf-8")
        md = tmp_dir / "big.md"
        _write_markdown(md, 150)

        _patch_io(
            monkeypatch,
            {"tool_name": "Write", "tool_input": {"file_path": str(md)}},
            tmp_dir,
        )
        assert post_edit_doc_size.main() == 0


class TestMalformedInput:
    def test_no_file_path(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _patch_io(monkeypatch, {"tool_name": "Edit", "tool_input": {}}, tmp_dir)
        assert post_edit_doc_size.main() == 0

    def test_missing_file(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _patch_io(
            monkeypatch,
            {"tool_name": "Write", "tool_input": {"file_path": str(tmp_dir / "ghost.md")}},
            tmp_dir,
        )
        assert post_edit_doc_size.main() == 0

    def test_tool_input_not_a_dict(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        payload: Mapping[str, object] = {"tool_name": "Write", "tool_input": "bad"}
        _patch_io(monkeypatch, payload, tmp_dir)
        assert post_edit_doc_size.main() == 0


class TestMultiEditFilesArray:
    def test_picks_first_file_from_files_array(
        self,
        tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_config(tmp_dir, {"default": 200, "patterns": []})
        md = tmp_dir / "x.md"
        _write_markdown(md, 201)

        _patch_io(
            monkeypatch,
            {"tool_name": "MultiEdit", "tool_input": {"files": [{"file_path": str(md)}]}},
            tmp_dir,
        )
        assert post_edit_doc_size.main() == 2
