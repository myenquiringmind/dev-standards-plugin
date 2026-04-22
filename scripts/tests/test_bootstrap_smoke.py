"""Tests for scripts/bootstrap_smoke.py.

Unit-tests focus on the smoke runner's orchestration, result reporting,
and frontmatter parsing. The 13 assertion functions are not exhaustively
unit-tested here — their full exercise is the smoke test itself, which
this suite runs via ``run_all`` against the real tree in one test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import bootstrap_smoke as bs


class TestAssertionResult:
    def test_pass_with_detail(self) -> None:
        r = bs.AssertionResult(1, "example", True, "extra info")
        assert r.number == 1
        assert r.name == "example"
        assert r.passed is True
        assert r.detail == "extra info"
        assert r.notes == []

    def test_default_notes_list(self) -> None:
        r = bs.AssertionResult(2, "x", False)
        assert r.notes == []


class TestFrontmatterParser:
    def test_parses_scalars_and_lists(self) -> None:
        text = "---\nname: foo\ntier: reason\ntools: [Read, Bash]\n---\n\nbody"
        fm = bs._parse_frontmatter(text)
        assert fm == {"name": "foo", "tier": "reason", "tools": ["Read", "Bash"]}

    def test_no_frontmatter(self) -> None:
        assert bs._parse_frontmatter("# heading only\n") is None

    def test_ignores_comments_and_blanks(self) -> None:
        text = "---\n# a comment\n\ntier: write\n---\n"
        assert bs._parse_frontmatter(text) == {"tier": "write"}


class TestRealTreeSmokeRun:
    """Single integration test: running against the real repo passes 13/13."""

    def test_real_tree_passes_all_13(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        results = bs.run_all(project_root)
        failed = [r for r in results if not r.passed]
        assert len(results) == 13
        assert not failed, "\n".join(f"  {r.number}/13 {r.name}: {r.detail}" for r in failed)


class TestMainCLIShape:
    def test_prints_one_line_per_assertion(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Monkey-patch ASSERTIONS to three cheap always-pass stubs so the CLI
        # shape test doesn't re-run the full 60s smoke suite.
        def _p1(_root: Path) -> bs.AssertionResult:
            return bs.AssertionResult(1, "alpha", True)

        def _p2(_root: Path) -> bs.AssertionResult:
            return bs.AssertionResult(2, "beta", True, "with detail")

        def _p3(_root: Path) -> bs.AssertionResult:
            return bs.AssertionResult(3, "gamma", False, "oops")

        monkeypatch.setattr(bs, "ASSERTIONS", [_p1, _p2, _p3])

        rc = bs.main(["--root", "."])

        out = capsys.readouterr().out
        assert "1/13 [PASS] alpha" in out
        assert "2/13 [PASS] beta - with detail" in out
        assert "3/13 [FAIL] gamma - oops" in out
        assert "2/3 passed" in out
        assert "FAILED" in out
        assert rc == 1

    def test_all_pass_returns_zero(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(
            bs,
            "ASSERTIONS",
            [lambda _r: bs.AssertionResult(1, "x", True)],
        )
        rc = bs.main(["--root", "."])
        out = capsys.readouterr().out
        assert rc == 0
        assert "1/1 passed" in out
        assert "OK" in out


class TestVerboseMode:
    def test_verbose_surfaces_notes(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        def _with_notes(_root: Path) -> bs.AssertionResult:
            return bs.AssertionResult(
                9,
                "example",
                False,
                "violations",
                notes=["agents/x.md: bad tier", "agents/y.md: missing tools"],
            )

        monkeypatch.setattr(bs, "ASSERTIONS", [_with_notes])

        rc = bs.main(["--root", ".", "--verbose"])

        out = capsys.readouterr().out
        assert rc == 1
        assert "agents/x.md: bad tier" in out
        assert "agents/y.md: missing tools" in out

    def test_non_verbose_hides_notes(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        def _with_notes(_root: Path) -> bs.AssertionResult:
            return bs.AssertionResult(9, "example", False, "v", notes=["hidden"])

        monkeypatch.setattr(bs, "ASSERTIONS", [_with_notes])
        bs.main(["--root", "."])
        out = capsys.readouterr().out
        assert "hidden" not in out
