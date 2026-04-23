"""Tests for hooks/_graph.py."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from hooks import _graph


def _sample_registry() -> dict[str, Any]:
    return {
        "version": "1.0.0",
        "generated_at": "2026-04-23T00:00:00Z",
        "nodes": [
            {"id": "alpha", "type": "Hook", "category": "core", "metadata": {}},
            {"id": "beta", "type": "Hook", "category": "core", "metadata": {}},
            {"id": "gamma", "type": "Agent", "category": "meta", "metadata": {}},
            {"id": "delta", "type": "Agent", "category": "meta", "metadata": {}},
        ],
        "edges": [
            {"from": "alpha", "to": "beta", "type": "triggers", "contract": "HookInput"},
            {"from": "beta", "to": "gamma", "type": "triggers", "contract": "HookInput"},
            {"from": "gamma", "to": "delta", "type": "composes", "contract": "AgentVerdict"},
        ],
    }


@pytest.fixture
def registry_root(tmp_dir: Path) -> Path:
    """Create a project-like root with a registry file."""
    (tmp_dir / "config").mkdir()
    (tmp_dir / "config" / "graph-registry.json").write_text(
        json.dumps(_sample_registry()), encoding="utf-8"
    )
    return tmp_dir


class TestLoadRegistry:
    def test_loads_valid_registry(self, registry_root: Path) -> None:
        registry = _graph.load_registry(registry_root)
        assert registry["version"] == "1.0.0"
        assert len(registry["nodes"]) == 4
        assert len(registry["edges"]) == 3

    def test_missing_file_returns_empty_stub(
        self, tmp_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        registry = _graph.load_registry(tmp_dir)
        assert registry["nodes"] == []
        assert registry["edges"] == []
        assert "not readable" in capsys.readouterr().err

    def test_malformed_json_returns_empty_stub(
        self, tmp_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        (tmp_dir / "config").mkdir()
        (tmp_dir / "config" / "graph-registry.json").write_text("{not json", encoding="utf-8")
        registry = _graph.load_registry(tmp_dir)
        assert registry["nodes"] == []
        assert "JSON malformed" in capsys.readouterr().err

    def test_wrong_shape_returns_empty_stub(
        self, tmp_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        (tmp_dir / "config").mkdir()
        (tmp_dir / "config" / "graph-registry.json").write_text(
            json.dumps({"version": "1.0.0", "generated_at": "x"}), encoding="utf-8"
        )
        registry = _graph.load_registry(tmp_dir)
        assert registry["nodes"] == []
        assert "shape invalid" in capsys.readouterr().err


class TestFindNode:
    def test_finds_existing(self) -> None:
        registry = _sample_registry()
        node = _graph.find_node(registry, "alpha")
        assert node is not None
        assert node["type"] == "Hook"

    def test_missing_returns_none(self) -> None:
        registry = _sample_registry()
        assert _graph.find_node(registry, "nope") is None

    def test_empty_registry(self) -> None:
        assert _graph.find_node({"nodes": []}, "anything") is None


class TestNodesByType:
    def test_returns_all_matching_type(self) -> None:
        registry = _sample_registry()
        hooks = _graph.nodes_by_type(registry, "Hook")
        assert {n["id"] for n in hooks} == {"alpha", "beta"}
        agents = _graph.nodes_by_type(registry, "Agent")
        assert {n["id"] for n in agents} == {"gamma", "delta"}

    def test_unknown_type_returns_empty(self) -> None:
        registry = _sample_registry()
        assert _graph.nodes_by_type(registry, "Skill") == []


class TestFindEdgesFrom:
    def test_all_edges_from_node(self) -> None:
        registry = _sample_registry()
        edges = _graph.find_edges_from(registry, "alpha")
        assert len(edges) == 1
        assert edges[0]["to"] == "beta"

    def test_filtered_by_edge_type(self) -> None:
        registry = _sample_registry()
        edges = _graph.find_edges_from(registry, "gamma", edge_type="composes")
        assert len(edges) == 1
        # Wrong type → empty.
        assert _graph.find_edges_from(registry, "gamma", edge_type="triggers") == []

    def test_no_edges_returns_empty(self) -> None:
        registry = _sample_registry()
        assert _graph.find_edges_from(registry, "delta") == []


class TestFindEdgesTo:
    def test_all_edges_to_node(self) -> None:
        registry = _sample_registry()
        edges = _graph.find_edges_to(registry, "beta")
        assert len(edges) == 1
        assert edges[0]["from"] == "alpha"

    def test_filtered_by_edge_type(self) -> None:
        registry = _sample_registry()
        edges = _graph.find_edges_to(registry, "delta", edge_type="composes")
        assert len(edges) == 1


class TestTopologicalSort:
    def test_simple_chain(self) -> None:
        registry = _sample_registry()
        # triggers chain: alpha → beta → gamma
        order = _graph.topological_sort(registry, "triggers")
        assert order is not None
        # Gamma must come after beta; beta after alpha. Delta is isolated
        # under 'triggers' and appears somewhere.
        assert order.index("alpha") < order.index("beta") < order.index("gamma")
        assert "delta" in order

    def test_composes_chain_different_order(self) -> None:
        registry = _sample_registry()
        # composes: gamma → delta only
        order = _graph.topological_sort(registry, "composes")
        assert order is not None
        assert order.index("gamma") < order.index("delta")

    def test_cycle_returns_none(self, capsys: pytest.CaptureFixture[str]) -> None:
        registry: dict[str, Any] = {
            "nodes": [
                {"id": "a", "type": "Hook", "category": "core", "metadata": {}},
                {"id": "b", "type": "Hook", "category": "core", "metadata": {}},
                {"id": "c", "type": "Hook", "category": "core", "metadata": {}},
            ],
            "edges": [
                {"from": "a", "to": "b", "type": "triggers"},
                {"from": "b", "to": "c", "type": "triggers"},
                {"from": "c", "to": "a", "type": "triggers"},
            ],
        }
        result = _graph.topological_sort(registry, "triggers")
        assert result is None
        err = capsys.readouterr().err
        assert "cycle detected" in err

    def test_isolated_nodes_included(self) -> None:
        registry: dict[str, Any] = {
            "nodes": [
                {"id": "x", "type": "Hook", "category": "core", "metadata": {}},
                {"id": "y", "type": "Hook", "category": "core", "metadata": {}},
            ],
            "edges": [],
        }
        order = _graph.topological_sort(registry, "triggers")
        assert order is not None
        assert set(order) == {"x", "y"}

    def test_ignores_other_edge_types(self) -> None:
        registry: dict[str, Any] = {
            "nodes": [
                {"id": "a", "type": "Hook", "category": "core", "metadata": {}},
                {"id": "b", "type": "Hook", "category": "core", "metadata": {}},
                {"id": "c", "type": "Hook", "category": "core", "metadata": {}},
            ],
            "edges": [
                # This would cycle if we considered both types, but since we
                # only ask for 'triggers', the 'composes' edge is invisible.
                {"from": "a", "to": "b", "type": "triggers"},
                {"from": "b", "to": "c", "type": "triggers"},
                {"from": "c", "to": "a", "type": "composes"},
            ],
        }
        order = _graph.topological_sort(registry, "triggers")
        assert order is not None
        assert order.index("a") < order.index("b") < order.index("c")

    def test_dangling_edge_ignored(self) -> None:
        """Edge referencing a node not in the node list is silently skipped."""
        registry: dict[str, Any] = {
            "nodes": [
                {"id": "a", "type": "Hook", "category": "core", "metadata": {}},
                {"id": "b", "type": "Hook", "category": "core", "metadata": {}},
            ],
            "edges": [
                {"from": "a", "to": "b", "type": "triggers"},
                {"from": "a", "to": "ghost", "type": "triggers"},  # dangling
            ],
        }
        order = _graph.topological_sort(registry, "triggers")
        assert order is not None
        assert order == ["a", "b"]


class TestDefensiveInputs:
    def test_non_dict_nodes_skipped(self) -> None:
        registry: dict[str, Any] = {
            "nodes": [
                "not-a-dict",
                {"id": "real", "type": "Hook", "category": "c", "metadata": {}},
            ],
            "edges": [],
        }
        # Should not raise, should find the one valid node.
        node = _graph.find_node(registry, "real")
        assert node is not None
        assert _graph.find_node(registry, "not-a-dict") is None

    def test_non_dict_edges_skipped(self) -> None:
        registry: dict[str, Any] = {
            "nodes": [{"id": "a", "type": "Hook", "category": "c", "metadata": {}}],
            "edges": ["not-a-dict", {"from": "a", "to": "a", "type": "x"}],
        }
        # Should not raise; find_edges_from returns only the valid edge.
        edges = _graph.find_edges_from(registry, "a")
        assert len(edges) == 1
