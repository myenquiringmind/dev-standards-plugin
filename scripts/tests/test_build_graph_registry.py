"""Tests for scripts/build_graph_registry.py."""

from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path

import pytest

from hooks._os_safe import temp_directory
from scripts import build_graph_registry as bgr


@pytest.fixture
def tmp_project() -> Generator[Path]:
    """Build a minimal on-disk framework tree for testing."""
    with temp_directory(prefix="dsp-bgr-") as path:
        yield _seed_project(path)


def _seed_project(root: Path) -> Path:
    # agents/meta/meta-example-reviewer.md — valid v2 agent
    (root / "agents" / "meta").mkdir(parents=True)
    (root / "agents" / "meta" / "meta-example-reviewer.md").write_text(
        "---\n"
        "name: meta-example-reviewer\n"
        "description: Example meta reviewer for tests\n"
        "tools: [Read, Bash, Glob, Grep]\n"
        "model: opus\n"
        "effort: medium\n"
        "memory: none\n"
        "maxTurns: 10\n"
        "tier: reason\n"
        "pack: core\n"
        "scope: core\n"
        "---\n\n"
        "# meta-example-reviewer\n",
        encoding="utf-8",
    )

    # agents/code-reviewer.md — v1 legacy without frontmatter; must be skipped
    (root / "agents" / "code-reviewer.md").write_text(
        "# Code Reviewer\n\nA v1 legacy agent.\n",
        encoding="utf-8",
    )

    # hooks/example_hook.py — valid v2 hook with Event + Matcher
    (root / "hooks").mkdir()
    (root / "hooks" / "example_hook.py").write_text(
        '"""Example hook.\n\nEvent: PreToolUse\nMatcher: Bash\n"""\n\ndef main() -> int:\n    return 0\n',
        encoding="utf-8",
    )

    # hooks/_shared.py — underscore prefix, must be skipped
    (root / "hooks" / "_shared.py").write_text('"""Shared module."""\n', encoding="utf-8")

    # commands/example.md — valid v2 command
    (root / "commands").mkdir()
    (root / "commands" / "example.md").write_text(
        "---\n"
        "context: none\n"
        "model: haiku\n"
        "allowed-tools: [Read, Write]\n"
        "description: Example command\n"
        "phase: meta\n"
        "---\n\n"
        "# /example\n",
        encoding="utf-8",
    )

    # commands/legacy.md — v1 legacy without frontmatter
    (root / "commands" / "legacy.md").write_text("# Legacy command\n", encoding="utf-8")

    # .claude/rules/example-rule.md
    (root / ".claude" / "rules").mkdir(parents=True)
    (root / ".claude" / "rules" / "example-rule.md").write_text(
        "# Example rule\n", encoding="utf-8"
    )

    # config/profiles/python.json
    (root / "config" / "profiles").mkdir(parents=True)
    (root / "config" / "profiles" / "python.json").write_text(
        json.dumps(
            {
                "detection": {"markers": ["pyproject.toml"], "extensions": [".py"]},
                "priority": "P0",
            }
        ),
        encoding="utf-8",
    )

    # Copy the real schema so validate_registry has something to check against
    schema_src = Path(__file__).resolve().parents[2] / "schemas" / "graph-registry.schema.json"
    (root / "schemas").mkdir()
    (root / "schemas" / "graph-registry.schema.json").write_text(
        schema_src.read_text(encoding="utf-8"), encoding="utf-8"
    )
    return root


class TestFrontmatterParser:
    def test_parses_scalars_and_lists(self) -> None:
        text = "---\nname: foo\ntools: [Read, Bash]\nmaxTurns: 12\nbackground: true\n---\n\nbody"
        fm = bgr._parse_frontmatter(text)
        assert fm == {"name": "foo", "tools": ["Read", "Bash"], "maxTurns": 12, "background": True}

    def test_no_frontmatter_returns_none(self) -> None:
        assert bgr._parse_frontmatter("# just a heading\n") is None

    def test_ignores_blank_and_comment_lines(self) -> None:
        text = "---\n# a comment\n\nname: bar\n---\n"
        assert bgr._parse_frontmatter(text) == {"name": "bar"}

    def test_negative_int(self) -> None:
        text = "---\nmaxTurns: -5\n---\n"
        assert bgr._parse_frontmatter(text) == {"maxTurns": -5}


class TestDiscoverAgents:
    def test_picks_up_v2_agent_and_skips_v1(self, tmp_project: Path) -> None:
        nodes = bgr.discover_agents(tmp_project)
        assert len(nodes) == 1
        node = nodes[0]
        assert node["id"] == "meta-example-reviewer"
        assert node["type"] == "Agent"
        assert node["category"] == "meta"
        assert node["metadata"]["agent_type"] == "blocking"  # reason tier + meta- name
        assert node["metadata"]["tools"] == ["Read", "Bash", "Glob", "Grep"]


class TestDiscoverHooks:
    def test_parses_event_and_matcher(self, tmp_project: Path) -> None:
        nodes = bgr.discover_hooks(tmp_project)
        assert len(nodes) == 1
        node = nodes[0]
        assert node["id"] == "example-hook"  # snake_case filename → kebab-case id
        assert node["metadata"]["event"] == "PreToolUse"
        assert node["metadata"]["matcher"] == "Bash"
        assert node["metadata"]["blocking"] is True

    def test_skips_underscore_prefix(self, tmp_project: Path) -> None:
        nodes = bgr.discover_hooks(tmp_project)
        ids = [n["id"] for n in nodes]
        assert not any(i.endswith("shared") for i in ids)


class TestDiscoverCommands:
    def test_picks_up_v2_command_and_skips_v1(self, tmp_project: Path) -> None:
        nodes = bgr.discover_commands(tmp_project)
        assert len(nodes) == 1
        assert nodes[0]["id"] == "example"
        assert nodes[0]["metadata"]["phase"] == "meta"


class TestDiscoverRules:
    def test_rules_emit_minimal_metadata(self, tmp_project: Path) -> None:
        nodes = bgr.discover_rules(tmp_project)
        assert len(nodes) == 1
        assert nodes[0]["id"] == "example-rule"
        assert nodes[0]["type"] == "Rule"


class TestDiscoverProfiles:
    def test_profile_node_carries_detection(self, tmp_project: Path) -> None:
        nodes = bgr.discover_profiles(tmp_project)
        assert len(nodes) == 1
        assert nodes[0]["id"] == "python"
        assert nodes[0]["metadata"]["detection"]["extensions"] == [".py"]
        assert nodes[0]["metadata"]["priority"] == "P0"


class TestBuildRegistry:
    def test_full_registry_is_schema_valid(self, tmp_project: Path) -> None:
        registry = bgr.build_registry(tmp_project)
        assert registry["version"] == "1.0.0"
        assert len(registry["nodes"]) == 5  # agent + hook + command + rule + profile
        assert registry["edges"] == []

        errors = bgr.validate_registry(
            registry, tmp_project / "schemas" / "graph-registry.schema.json"
        )
        assert errors == []


class TestMain:
    def test_check_mode_does_not_write(
        self, tmp_project: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        output = tmp_project / "config" / "graph-registry.json"
        assert not output.exists()

        rc = bgr.main(["--root", str(tmp_project), "--check"])

        assert rc == 0
        assert not output.exists()
        assert "OK" in capsys.readouterr().out

    def test_write_mode_writes_valid_json(self, tmp_project: Path) -> None:
        output = tmp_project / "config" / "graph-registry.json"

        rc = bgr.main(["--root", str(tmp_project)])

        assert rc == 0
        assert output.is_file()
        data = json.loads(output.read_text(encoding="utf-8"))
        assert data["version"] == "1.0.0"
        assert len(data["nodes"]) == 5

    def test_schema_failure_exits_2(
        self,
        tmp_project: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Monkeypatch build_registry to return an invalid registry shape.
        monkeypatch.setattr(bgr, "build_registry", lambda _root: {"version": "bad", "nodes": []})

        rc = bgr.main(["--root", str(tmp_project)])

        err = capsys.readouterr().err
        assert rc == 2
        assert "schema validation failed" in err
