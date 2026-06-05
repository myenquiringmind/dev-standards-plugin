"""Schema tests for schemas/reports/quality-scores.schema.json.

The quality-scores schema is the output contract for
closed-loop-quality-scorer (Phase 4 stream 5). These tests pin the
shape the agent must produce: the schema self-validates, accepts the
minimal empty-tree document and a populated one, and rejects the
malformations most likely to slip through (out-of-range precision,
non-null recall, wrong schema_version, run_count below 1).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_PATH = _REPO_ROOT / "schemas" / "reports" / "quality-scores.schema.json"


def _load_schema() -> dict[str, Any]:
    parsed: dict[str, Any] = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    return parsed


def _errors(doc: dict[str, Any]) -> list[str]:
    schema = _load_schema()
    return [e.message for e in Draft202012Validator(schema).iter_errors(doc)]


_EMPTY_TREE: dict[str, Any] = {
    "schema_version": "1",
    "generated_at": "2026-06-05T00:00:00Z",
    "summary": {
        "total_agents": 0,
        "total_runs": 0,
        "window_start": None,
        "window_end": None,
    },
    "agents": {},
}

_POPULATED: dict[str, Any] = {
    "schema_version": "1",
    "generated_at": "2026-06-05T00:00:00Z",
    "summary": {
        "total_agents": 2,
        "total_runs": 7,
        "window_start": "2026-06-01T08:00:00Z",
        "window_end": "2026-06-05T08:00:00Z",
    },
    "agents": {
        "py-solid-dry-reviewer": {
            "precision": 0.92,
            "recall": None,
            "latency_ms_p95": 4200.0,
            "cost_usd_p95": 0.031,
            "run_count": 5,
            "last_updated": "2026-06-05T08:00:00Z",
        },
        "codebase-dead-code-scanner": {
            "precision": None,
            "recall": None,
            "latency_ms_p95": None,
            "cost_usd_p95": None,
            "run_count": 2,
            "last_updated": "2026-06-03T08:00:00Z",
        },
    },
}


class TestSelfValidation:
    def test_schema_meta_validates(self) -> None:
        Draft202012Validator.check_schema(_load_schema())


class TestPositiveExamples:
    def test_empty_tree_document_accepted(self) -> None:
        assert _errors(_EMPTY_TREE) == []

    def test_populated_document_accepted(self) -> None:
        assert _errors(_POPULATED) == []

    def test_scanner_with_all_null_metrics_accepted(self) -> None:
        # A scanner that produces reports, not verdicts, has null precision
        # and null p95s but still a positive run_count.
        doc = json.loads(json.dumps(_EMPTY_TREE))
        doc["summary"] = {
            "total_agents": 1,
            "total_runs": 1,
            "window_start": "2026-06-05T08:00:00Z",
            "window_end": "2026-06-05T08:00:00Z",
        }
        doc["agents"] = {
            "codebase-inventory-scanner": {
                "precision": None,
                "recall": None,
                "latency_ms_p95": None,
                "cost_usd_p95": None,
                "run_count": 1,
                "last_updated": "2026-06-05T08:00:00Z",
            }
        }
        assert _errors(doc) == []


class TestNegativeExamples:
    def test_precision_above_one_rejected(self) -> None:
        doc = json.loads(json.dumps(_POPULATED))
        doc["agents"]["py-solid-dry-reviewer"]["precision"] = 1.4
        assert _errors(doc)

    def test_non_null_recall_rejected(self) -> None:
        # Phase 4 fixes recall to null; a number must be rejected so a
        # later phase can't quietly start populating it off-contract.
        doc = json.loads(json.dumps(_POPULATED))
        doc["agents"]["py-solid-dry-reviewer"]["recall"] = 0.5
        assert _errors(doc)

    def test_wrong_schema_version_rejected(self) -> None:
        doc = json.loads(json.dumps(_EMPTY_TREE))
        doc["schema_version"] = "2"
        assert _errors(doc)

    def test_zero_run_count_rejected(self) -> None:
        # An agent in the map must have at least one record; run_count 0
        # means it should have been omitted entirely.
        doc = json.loads(json.dumps(_POPULATED))
        doc["agents"]["py-solid-dry-reviewer"]["run_count"] = 0
        assert _errors(doc)

    def test_unknown_agent_key_rejected(self) -> None:
        # Agent keys must carry a PSF scope prefix.
        doc = json.loads(json.dumps(_EMPTY_TREE))
        doc["agents"] = {
            "not-a-real-prefix-thing": {
                "precision": None,
                "recall": None,
                "latency_ms_p95": None,
                "cost_usd_p95": None,
                "run_count": 1,
                "last_updated": "2026-06-05T08:00:00Z",
            }
        }
        assert _errors(doc)

    def test_additional_top_level_property_rejected(self) -> None:
        doc = json.loads(json.dumps(_EMPTY_TREE))
        doc["unexpected"] = True
        assert _errors(doc)

    def test_missing_summary_rejected(self) -> None:
        doc = json.loads(json.dumps(_EMPTY_TREE))
        del doc["summary"]
        assert _errors(doc)
