"""Phase 1 + Phase 2 + Phase 3 exit gate — 28-assertion self-test.

Reproduces:

- Phase 1 exit gate (assertions 1-13) per
  ``docs/phases/phase-1-bootstrap.md``.
- Phase 2 exit gate (assertions 14-21) per
  ``docs/phases/phase-2-hook-completion.md``.
- Phase 3 exit gate (assertions 22-28) per
  ``docs/phases/phase-3-language-profiles-and-scanners.md``.

Each check runs in an isolated ``temp_directory`` or invokes a
hook module via ``uv run python -m hooks.<name>``; nothing mutates
the real repo state.

Assertions that require a live LLM invocation (``/validate`` itself,
live agent verdicts, ``meta-agent-arch-doc-reviewer`` body checks)
are exercised structurally: the agent or command file must exist,
be schema-valid, and reference the expected canonical tuples. A
full live-integration smoke test is deferred to
``scripts/live_integration_smoke.py`` (Phase 2 CI harness, separate
work item).

Usage:
    uv run python -m scripts.bootstrap_smoke
    uv run python -m scripts.bootstrap_smoke --root /path/to/repo
    uv run python -m scripts.bootstrap_smoke --verbose
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

from hooks._hook_shared import (
    AGENT_VALIDATION_STEPS,
    CRITICAL_CONTEXT_PCT,
    PY_VALIDATION_STEPS,
    STAMP_TTL,
)
from hooks._os_safe import temp_directory
from hooks._session_state_common import get_memory_dir

_STAMP_VERSION: str = "1.0.0"
_SUBPROCESS_TIMEOUT: int = 15


@dataclass
class AssertionResult:
    number: int
    name: str
    passed: bool
    detail: str = ""
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_hook_module(
    module: str,
    root: Path,
    *,
    stdin_payload: Mapping[str, object] | None = None,
    extra_args: list[str] | None = None,
    env_overrides: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    cmd = ["uv", "run", "python", "-m", f"hooks.{module}"]
    if extra_args:
        cmd.extend(extra_args)
    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(root)
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        cmd,
        input=json.dumps(stdin_payload) if stdin_payload is not None else None,
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT,
        check=False,
        env=env,
    )


def _write_stamp(
    root: Path,
    *,
    gate: str,
    branch: str,
    steps: list[str],
    age_seconds: int = 0,
) -> Path:
    filenames = {
        "code": ".validation_stamp",
        "frontend": ".frontend_validation_stamp",
        "agent": ".agent_validation_stamp",
        "db": ".db_validation_stamp",
        "api": ".api_validation_stamp",
    }
    stamp = {
        "timestamp": (datetime.now(UTC) - timedelta(seconds=age_seconds)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "branch": branch,
        "steps": steps,
        "ttl_seconds": STAMP_TTL,
        "version": _STAMP_VERSION,
        "gate": gate,
    }
    path = root / filenames[gate]
    path.write_text(json.dumps(stamp, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _init_git_repo(root: Path, branch: str = "feat/smoke") -> None:
    subprocess.run(["git", "init", "-q"], cwd=str(root), check=True, capture_output=True)
    subprocess.run(
        ["git", "checkout", "-q", "-b", branch],
        cwd=str(root),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "smoke@test.local"],
        cwd=str(root),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "smoke"],
        cwd=str(root),
        check=True,
        capture_output=True,
    )


def _stage_python_file(root: Path, relpath: str = "foo.py") -> None:
    (root / relpath).write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", relpath], cwd=str(root), check=True, capture_output=True)


def _copy_schemas(real_root: Path, fixture_root: Path) -> None:
    (fixture_root / "schemas").mkdir(parents=True, exist_ok=True)
    for name in ("stamp.schema.json", "agent-frontmatter.schema.json"):
        src = real_root / "schemas" / name
        (fixture_root / "schemas" / name).write_text(
            src.read_text(encoding="utf-8"), encoding="utf-8"
        )


def _seed_registry(root: Path, nodes: list[dict[str, Any]]) -> None:
    """Write a minimal ``config/graph-registry.json`` for tier-aware hooks."""
    config_dir = root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "1.0.0",
        "generated_at": "2026-05-01T00:00:00Z",
        "nodes": nodes,
        "edges": [],
    }
    (config_dir / "graph-registry.json").write_text(json.dumps(payload), encoding="utf-8")


def _agent_node(agent_id: str, *, tier: str, max_turns: int = 10) -> dict[str, Any]:
    """Build a registry node entry suitable for the tier-aware hook gates."""
    return {
        "id": agent_id,
        "type": "Agent",
        "category": "meta",
        "metadata": {
            "agent_type": "blocking",
            "model": "opus",
            "tools": ["Read", "Bash"],
            "memory": "none",
            "maxTurns": max_turns,
            "tier": tier,
        },
    }


def _parse_frontmatter(text: str) -> dict[str, object] | None:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        return None
    result: dict[str, object] = {}
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, sep, value = line.partition(":")
        if not sep:
            continue
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            result[key] = [x.strip().strip("\"'") for x in inner.split(",") if x.strip()]
        elif value in ("true", "True"):
            result[key] = True
        elif value in ("false", "False"):
            result[key] = False
        elif value.lstrip("-").isdigit():
            result[key] = int(value)
        else:
            result[key] = value.strip("\"'")
    return result


# ---------------------------------------------------------------------------
# Assertions
# ---------------------------------------------------------------------------


def _check_validate_command_present(real_root: Path) -> AssertionResult:
    """Assertion 1: /validate runs cleanly against the bootstrap's own code.

    Structural check — the command file must exist, declare the expected
    frontmatter, and reference the canonical tuples by name.
    """
    path = real_root / "commands" / "validate.md"
    if not path.is_file():
        return AssertionResult(
            1, "validate-command-present", False, "commands/validate.md missing"
        )
    text = path.read_text(encoding="utf-8")
    fm = _parse_frontmatter(text)
    if not fm:
        return AssertionResult(1, "validate-command-present", False, "no frontmatter")
    if fm.get("phase") != "validate":
        return AssertionResult(
            1, "validate-command-present", False, f"phase != 'validate' ({fm.get('phase')})"
        )
    if "_hook_shared" not in text or "PY_VALIDATION_STEPS" not in text:
        return AssertionResult(
            1, "validate-command-present", False, "body does not reference canonical tuples"
        )
    return AssertionResult(1, "validate-command-present", True)


def _check_objective_verifier_present(real_root: Path) -> AssertionResult:
    """Assertion 2: scope violation blocked by validation-objective-verifier.

    Structural — the agent file is present with tier: reason.
    """
    path = real_root / "agents" / "validation" / "validation-objective-verifier.md"
    if not path.is_file():
        return AssertionResult(2, "objective-verifier-present", False, f"missing: {path}")
    fm = _parse_frontmatter(path.read_text(encoding="utf-8"))
    if not fm or fm.get("tier") != "reason":
        return AssertionResult(
            2,
            "objective-verifier-present",
            False,
            f"wrong tier: {fm.get('tier') if fm else 'no frontmatter'}",
        )
    return AssertionResult(2, "objective-verifier-present", True)


def _check_commit_without_stamp_blocks(real_root: Path) -> AssertionResult:
    """Assertion 3: git commit with no stamp exits 2."""
    with temp_directory(prefix="smoke-3-") as root:
        _init_git_repo(root)
        _copy_schemas(real_root, root)
        _stage_python_file(root)
        payload = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'x'"}}
        result = _run_hook_module("pre_commit_cli_gate", root, stdin_payload=payload)
        if result.returncode != 2:
            return AssertionResult(
                3,
                "commit-without-stamp-blocks",
                False,
                f"expected exit 2, got {result.returncode}: {result.stderr[:200]}",
            )
    return AssertionResult(3, "commit-without-stamp-blocks", True)


def _check_commit_with_valid_stamp_passes(real_root: Path) -> AssertionResult:
    """Assertion 4: commit with fresh, valid, branch-matched stamp exits 0."""
    branch = "feat/smoke-test"
    with temp_directory(prefix="smoke-4-") as root:
        _init_git_repo(root, branch=branch)
        _copy_schemas(real_root, root)
        _stage_python_file(root)
        _write_stamp(root, gate="code", branch=branch, steps=list(PY_VALIDATION_STEPS))
        payload = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'x'"}}
        result = _run_hook_module("pre_commit_cli_gate", root, stdin_payload=payload)
        if result.returncode != 0:
            return AssertionResult(
                4,
                "valid-stamp-passes",
                False,
                f"expected exit 0, got {result.returncode}: {result.stderr[:200]}",
            )
    return AssertionResult(4, "valid-stamp-passes", True)


def _check_stale_stamp_blocks(real_root: Path) -> AssertionResult:
    """Assertion 5: stamp older than 15 minutes blocks."""
    branch = "feat/smoke-test"
    with temp_directory(prefix="smoke-5-") as root:
        _init_git_repo(root, branch=branch)
        _copy_schemas(real_root, root)
        _stage_python_file(root)
        _write_stamp(
            root,
            gate="code",
            branch=branch,
            steps=list(PY_VALIDATION_STEPS),
            age_seconds=STAMP_TTL + 60,
        )
        payload = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'x'"}}
        result = _run_hook_module("pre_commit_cli_gate", root, stdin_payload=payload)
        if result.returncode != 2:
            return AssertionResult(
                5, "stale-stamp-blocks", False, f"expected exit 2, got {result.returncode}"
            )
    return AssertionResult(5, "stale-stamp-blocks", True)


def _check_wip_bypass(real_root: Path) -> AssertionResult:
    """Assertion 6: [WIP] in commit message bypasses the gate."""
    with temp_directory(prefix="smoke-6-") as root:
        _init_git_repo(root)
        _copy_schemas(real_root, root)
        _stage_python_file(root)
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "git commit -m '[WIP] in progress'"},
        }
        result = _run_hook_module("pre_commit_cli_gate", root, stdin_payload=payload)
        if result.returncode != 0:
            return AssertionResult(
                6, "wip-bypass", False, f"expected exit 0, got {result.returncode}"
            )
    return AssertionResult(6, "wip-bypass", True)


def _check_merge_head_bypass(real_root: Path) -> AssertionResult:
    """Assertion 7: .git/MERGE_HEAD bypasses the gate."""
    with temp_directory(prefix="smoke-7-") as root:
        _init_git_repo(root)
        _copy_schemas(real_root, root)
        _stage_python_file(root)
        (root / ".git" / "MERGE_HEAD").write_text("abc123\n", encoding="utf-8")
        payload = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'merge'"}}
        result = _run_hook_module("pre_commit_cli_gate", root, stdin_payload=payload)
        if result.returncode != 0:
            return AssertionResult(
                7, "merge-head-bypass", False, f"expected exit 0, got {result.returncode}"
            )
    return AssertionResult(7, "merge-head-bypass", True)


def _check_path_traversal_rejected(real_root: Path) -> AssertionResult:
    """Assertion 8: write_agent_memory --agent ../../etc/passwd is rejected."""
    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "hooks.write_agent_memory",
            "--agent",
            "../../etc/passwd",
            "--append",
        ],
        input="",
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT,
        check=False,
        cwd=str(real_root),
    )
    if result.returncode == 0:
        return AssertionResult(
            8, "path-traversal-rejected", False, "write_agent_memory accepted ../../etc/passwd"
        )
    return AssertionResult(8, "path-traversal-rejected", True)


def _check_agent_tier_consistency(real_root: Path) -> AssertionResult:
    """Assertion 9: every bootstrap agent declares a tier consistent with tools."""
    forbidden_for_read_reason = {"Edit", "Write", "NotebookEdit"}
    violations: list[str] = []
    checked = 0
    for path in sorted((real_root / "agents").rglob("*.md")):
        if path.name == "CLAUDE.md":
            continue
        fm = _parse_frontmatter(path.read_text(encoding="utf-8"))
        if not fm or "tier" not in fm:
            continue  # v1-legacy or non-v2 files aren't under this assertion
        checked += 1
        tier = fm["tier"]
        tools = fm.get("tools", [])
        if not isinstance(tools, list):
            violations.append(f"{path}: tools not a list")
            continue
        if tier in ("read", "reason"):
            bad = set(tools) & forbidden_for_read_reason
            if bad:
                violations.append(f"{path}: tier={tier} but has {sorted(bad)}")
    if violations:
        return AssertionResult(
            9, "agent-tier-consistency", False, f"{len(violations)} violations", notes=violations
        )
    return AssertionResult(9, "agent-tier-consistency", True, f"checked {checked} agents")


def _check_transcript_todo_extractor_schema(real_root: Path) -> AssertionResult:
    """Assertion 10: transcript-todo-extractor schema validates a synthetic report."""
    schema_path = real_root / "schemas" / "reports" / "transcript-todo-extraction.schema.json"
    if not schema_path.is_file():
        return AssertionResult(10, "transcript-todo-extractor-schema", False, "schema missing")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    report = {
        "subagent": "meta-agent-scaffolder",
        "session_id": "smoke-test",
        "extracted_at": "2026-04-22T12:00:00Z",
        "items": [
            {
                "content": "Address the deferred refactor in hooks/foo.py",
                "kind": "tier-2-sidecar",
                "confidence": "high",
                "source_excerpt": "I noticed an unused import; we should clean this up before the feature commit.",
            }
        ],
    }
    errors = list(Draft202012Validator(schema).iter_errors(report))
    if errors:
        return AssertionResult(
            10,
            "transcript-todo-extractor-schema",
            False,
            f"positive example rejected: {errors[0].message}",
        )
    bad = {"subagent": "", "session_id": "", "extracted_at": "not-a-date", "items": []}
    errors = list(Draft202012Validator(schema).iter_errors(bad))
    if not errors:
        return AssertionResult(
            10, "transcript-todo-extractor-schema", False, "negative example incorrectly accepted"
        )
    return AssertionResult(10, "transcript-todo-extractor-schema", True)


def _check_doc_size_limit(real_root: Path) -> AssertionResult:
    """Assertion 11: post_edit_doc_size blocks a 201-line markdown; allows 150."""
    with temp_directory(prefix="smoke-11-") as root:
        (root / "config").mkdir()
        (root / "config" / "doc-size-limits.json").write_text(
            json.dumps({"default": 200, "patterns": []}),
            encoding="utf-8",
        )
        # 201-line file should block.
        big = root / "big.md"
        big.write_text("\n".join(["line"] * 201) + "\n", encoding="utf-8")
        payload_big = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(big)},
        }
        r_big = _run_hook_module("post_edit_doc_size", root, stdin_payload=payload_big)
        if r_big.returncode != 2:
            return AssertionResult(
                11,
                "doc-size-limit",
                False,
                f"201-line file: expected exit 2, got {r_big.returncode}",
            )
        # 150-line file should pass.
        small = root / "small.md"
        small.write_text("\n".join(["line"] * 150) + "\n", encoding="utf-8")
        payload_small = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(small)},
        }
        r_small = _run_hook_module("post_edit_doc_size", root, stdin_payload=payload_small)
        if r_small.returncode != 0:
            return AssertionResult(
                11,
                "doc-size-limit",
                False,
                f"150-line file: expected exit 0, got {r_small.returncode}",
            )
    return AssertionResult(11, "doc-size-limit", True)


def _check_context_budget_hard_cut(real_root: Path) -> AssertionResult:
    """Assertion 12: context at CRITICAL_CONTEXT_PCT+ triggers exit 2 with /handoff."""
    with temp_directory(prefix="smoke-12-") as root:
        (root / ".claude").mkdir()
        # Write a value at the critical threshold.
        (root / ".claude" / ".context_pct").write_text(str(CRITICAL_CONTEXT_PCT), encoding="utf-8")
        result = _run_hook_module("context_budget", root, stdin_payload={})
        if result.returncode != 2:
            return AssertionResult(
                12, "context-budget-hard-cut", False, f"expected exit 2, got {result.returncode}"
            )
        if "handoff" not in result.stderr.lower():
            return AssertionResult(
                12, "context-budget-hard-cut", False, "stderr missing handoff message"
            )
    return AssertionResult(12, "context-budget-hard-cut", True)


def _check_secret_scan_and_gitignore(real_root: Path) -> AssertionResult:
    """Assertion 13: pre_write_secret_scan blocks AKIA; session_start_gitignore_audit warns."""
    # Part A — secret scan blocks AKIA on a Write.
    with temp_directory(prefix="smoke-13a-") as root:
        payload = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(root / "x.py"),
                "content": "AWS_KEY = 'AKIAIOSFODNN7EXAMPLE'",
            },
        }
        r_secret = _run_hook_module("pre_write_secret_scan", root, stdin_payload=payload)
        if r_secret.returncode != 2:
            return AssertionResult(
                13,
                "secret-scan-and-gitignore",
                False,
                f"secret_scan: expected exit 2, got {r_secret.returncode}",
            )
    # Part B — gitignore audit warns on a deliberately stripped file.
    with temp_directory(prefix="smoke-13b-") as root:
        _init_git_repo(root)
        (root / ".gitignore").write_text("# empty\n", encoding="utf-8")
        r_audit = _run_hook_module("session_start_gitignore_audit", root, stdin_payload={})
        # The audit is advisory (exit 0) with warnings on stderr.
        if r_audit.returncode != 0:
            return AssertionResult(
                13,
                "secret-scan-and-gitignore",
                False,
                f"gitignore_audit: expected exit 0 (advisory), got {r_audit.returncode}",
            )
        if not r_audit.stderr.strip():
            return AssertionResult(
                13,
                "secret-scan-and-gitignore",
                False,
                "gitignore_audit: expected stderr warning, got none",
            )
    return AssertionResult(13, "secret-scan-and-gitignore", True)


# ---------------------------------------------------------------------------
# Phase 2 assertions (14-21)
# ---------------------------------------------------------------------------


def _check_tier_enforcer_blocks_edit(real_root: Path) -> AssertionResult:
    """Assertion 14: pre_tool_use_tier_enforcer blocks Edit from a read-tier subagent."""
    with temp_directory(prefix="smoke-14-") as root:
        _seed_registry(root, [_agent_node("scanner", tier="read")])
        payload = {
            "tool_name": "Edit",
            "agent_type": "scanner",
            "tool_input": {
                "file_path": str(root / "x.py"),
                "old_string": "",
                "new_string": "y",
            },
        }
        result = _run_hook_module("pre_tool_use_tier_enforcer", root, stdin_payload=payload)
        if result.returncode != 2:
            return AssertionResult(
                14,
                "tier-enforcer-blocks-edit",
                False,
                f"expected exit 2, got {result.returncode}: {result.stderr[:200]}",
            )
    return AssertionResult(14, "tier-enforcer-blocks-edit", True)


def _check_bash_tier_guard_blocks_rm(real_root: Path) -> AssertionResult:
    """Assertion 15: pre_bash_tier_guard rejects rm from a reason-tier subagent."""
    with temp_directory(prefix="smoke-15-") as root:
        _seed_registry(root, [_agent_node("planner", tier="reason")])
        payload = {
            "tool_name": "Bash",
            "agent_type": "planner",
            "tool_input": {"command": "rm -rf /tmp/foo"},
        }
        result = _run_hook_module("pre_bash_tier_guard", root, stdin_payload=payload)
        if result.returncode != 2:
            return AssertionResult(
                15,
                "bash-tier-guard-blocks-rm",
                False,
                f"expected exit 2, got {result.returncode}: {result.stderr[:200]}",
            )
    return AssertionResult(15, "bash-tier-guard-blocks-rm", True)


def _check_stop_validation_blocks_dirty_tree(real_root: Path) -> AssertionResult:
    """Assertion 16: stop_validation blocks Stop with uncommitted changes."""
    with temp_directory(prefix="smoke-16-") as root:
        _init_git_repo(root)
        # Untracked file → git status --porcelain returns ``?? <name>``.
        (root / "dirty.py").write_text("x = 1\n", encoding="utf-8")
        result = _run_hook_module("stop_validation", root, stdin_payload={})
        if result.returncode != 2:
            return AssertionResult(
                16,
                "stop-validation-dirty-tree",
                False,
                f"expected exit 2, got {result.returncode}: {result.stderr[:200]}",
            )
    return AssertionResult(16, "stop-validation-dirty-tree", True)


def _check_stop_failure_writes_incident(real_root: Path) -> AssertionResult:
    """Assertion 17: stop_failure writes a ULID-keyed incident under the configured dir."""
    with temp_directory(prefix="smoke-17-") as root:
        incidents_dir = root / "incidents"
        result = _run_hook_module(
            "stop_failure",
            root,
            stdin_payload={"error": "smoke-test"},
            env_overrides={"CLAUDE_INCIDENTS_DIR": str(incidents_dir)},
        )
        if result.returncode != 0:
            return AssertionResult(
                17,
                "stop-failure-incident",
                False,
                f"expected exit 0, got {result.returncode}",
            )
        files = list(incidents_dir.rglob("INC-*.jsonl"))
        if len(files) != 1:
            return AssertionResult(
                17,
                "stop-failure-incident",
                False,
                f"expected 1 incident file, got {len(files)}",
            )
        record = json.loads(files[0].read_text(encoding="utf-8").splitlines()[0])
        if record.get("category") != "stop-failure":
            return AssertionResult(
                17,
                "stop-failure-incident",
                False,
                f"wrong category: {record.get('category')!r}",
            )
        ulid = record.get("ulid", "")
        if not re.match(r"^[0-9A-HJKMNP-TV-Z]{26}$", ulid):
            return AssertionResult(17, "stop-failure-incident", False, f"invalid ULID: {ulid!r}")
    return AssertionResult(17, "stop-failure-incident", True)


def _check_telemetry_concurrent_safe(real_root: Path) -> AssertionResult:
    """Assertion 18: ``_telemetry`` keeps both records intact under concurrent writes."""
    with temp_directory(prefix="smoke-18-") as root:
        telemetry_dir = root / "telemetry"
        cmd = ["uv", "run", "python", "-m", "hooks.instructions_loaded"]
        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(root)
        env["CLAUDE_TELEMETRY_DIR"] = str(telemetry_dir)

        # Spawn two subprocesses simultaneously, each emitting one record.
        # stdout/stderr go to DEVNULL — the assertion only inspects returncode
        # and the produced telemetry files, so capturing the pipes leaks file
        # descriptors that pytest's unraisable-exception collector flags.
        procs = [
            subprocess.Popen(
                cmd,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            for _ in range(2)
        ]
        payloads = [
            json.dumps({"instructions": ["a.md"]}),
            json.dumps({"instructions": ["b.md"]}),
        ]
        for proc, payload in zip(procs, payloads, strict=True):
            proc.stdin.write(payload.encode("utf-8"))  # type: ignore[union-attr]
            proc.stdin.close()  # type: ignore[union-attr]
        for proc in procs:
            proc.wait(timeout=_SUBPROCESS_TIMEOUT)
        if any(p.returncode != 0 for p in procs):
            codes = [p.returncode for p in procs]
            return AssertionResult(18, "telemetry-concurrent", False, f"non-zero exits: {codes}")

        files = list(telemetry_dir.glob("*.jsonl"))
        if not files:
            return AssertionResult(18, "telemetry-concurrent", False, "no telemetry file produced")
        records: list[dict[str, Any]] = []
        for path in files:
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    records.append(json.loads(line))
        if len(records) != 2:
            return AssertionResult(
                18,
                "telemetry-concurrent",
                False,
                f"expected 2 records, got {len(records)}",
            )
        files_seen = {tuple(r["data"]["files"]) for r in records}
        if files_seen != {("a.md",), ("b.md",)}:
            return AssertionResult(
                18,
                "telemetry-concurrent",
                False,
                f"records corrupted or interleaved: {files_seen}",
            )
    return AssertionResult(18, "telemetry-concurrent", True)


def _check_meta_agent_arch_doc_reviewer(real_root: Path) -> AssertionResult:
    """Assertion 19: meta-agent-arch-doc-reviewer present and AGENT_VALIDATION_STEPS grew."""
    path = real_root / "agents" / "meta" / "meta-agent-arch-doc-reviewer.md"
    if not path.is_file():
        return AssertionResult(19, "tuple-growth-path", False, f"missing: {path}")
    fm = _parse_frontmatter(path.read_text(encoding="utf-8"))
    if not fm or fm.get("name") != "meta-agent-arch-doc-reviewer":
        return AssertionResult(
            19,
            "tuple-growth-path",
            False,
            f"frontmatter name mismatch: {fm.get('name') if fm else 'no frontmatter'}",
        )
    # Phase 2 grew the tuple from {command-composition-reviewer} to include
    # the new reviewer. That growth is the assertion.
    if "agent-arch-doc-reviewer" not in AGENT_VALIDATION_STEPS:
        return AssertionResult(
            19,
            "tuple-growth-path",
            False,
            f"AGENT_VALIDATION_STEPS missing 'agent-arch-doc-reviewer': {AGENT_VALIDATION_STEPS}",
        )
    return AssertionResult(19, "tuple-growth-path", True)


def _check_checkpoint_gate_blocks_stale(real_root: Path) -> AssertionResult:
    """Assertion 20: checkpoint_gate blocks subagent Bash when state is stale."""
    with temp_directory(prefix="smoke-20-") as root:
        memory_dir = get_memory_dir(root)
        memory_dir.mkdir(parents=True, exist_ok=True)
        stale_ts = time.time() - 3600  # 1h ago — past the 30min threshold.
        (memory_dir / "session-checkpoint.state.json").write_text(
            json.dumps({"last_write_ts": stale_ts, "event_count": 0, "last_branch": ""}),
            encoding="utf-8",
        )
        payload = {
            "tool_name": "Bash",
            "agent_type": "scanner",
            "tool_input": {"command": "git status"},
        }
        result = _run_hook_module("checkpoint_gate", root, stdin_payload=payload)
        if result.returncode != 2:
            return AssertionResult(
                20,
                "checkpoint-gate-stale",
                False,
                f"expected exit 2, got {result.returncode}: {result.stderr[:200]}",
            )
    return AssertionResult(20, "checkpoint-gate-stale", True)


def _check_secret_scan_staged(real_root: Path) -> AssertionResult:
    """Assertion 21: pre_commit_secret_scan blocks a staged file containing AKIA."""
    with temp_directory(prefix="smoke-21-") as root:
        _init_git_repo(root)
        (root / "config.py").write_text("AWS_KEY = 'AKIAIOSFODNN7EXAMPLE'\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "config.py"],
            cwd=str(root),
            check=True,
            capture_output=True,
        )
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "git commit -m 'add config'"},
        }
        result = _run_hook_module("pre_commit_secret_scan", root, stdin_payload=payload)
        if result.returncode != 2:
            return AssertionResult(
                21,
                "secret-scan-staged",
                False,
                f"expected exit 2, got {result.returncode}: {result.stderr[:200]}",
            )
    return AssertionResult(21, "secret-scan-staged", True)


# ---------------------------------------------------------------------------
# Phase 3 assertions (22-28)
# ---------------------------------------------------------------------------


def _validate_schema_with_examples(
    real_root: Path,
    *,
    number: int,
    name: str,
    schema_examples: list[tuple[str, dict[str, Any]]],
) -> AssertionResult:
    """Helper: each (schema_filename, positive_example) pair must self-validate
    as a draft-2020-12 schema and accept its positive example."""
    for schema_filename, positive in schema_examples:
        schema_path = real_root / "schemas" / "reports" / schema_filename
        if not schema_path.is_file():
            return AssertionResult(number, name, False, f"missing: {schema_path}")
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        try:
            Draft202012Validator.check_schema(schema)
        except Exception as exc:
            return AssertionResult(
                number, name, False, f"{schema_filename}: meta-validation failed: {exc}"
            )
        errors = list(Draft202012Validator(schema).iter_errors(positive))
        if errors:
            return AssertionResult(
                number,
                name,
                False,
                f"{schema_filename}: positive example rejected: {errors[0].message[:120]}",
            )
    return AssertionResult(number, name, True, f"{len(schema_examples)} schemas")


def _check_phase_3_language_profiles(real_root: Path) -> AssertionResult:
    """Assertion 22: every config/profiles/*.json validates against
    profile.schema.json; typescript markers don't collide with python."""
    schema_path = real_root / "schemas" / "profile.schema.json"
    if not schema_path.is_file():
        return AssertionResult(
            22, "phase-3-language-profiles", False, "profile.schema.json missing"
        )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    profiles_dir = real_root / "config" / "profiles"
    profile_files = sorted(profiles_dir.glob("*.json"))
    if not profile_files:
        return AssertionResult(22, "phase-3-language-profiles", False, "no profile files found")
    markers_by_profile: dict[str, set[str]] = {}
    for path in profile_files:
        profile = json.loads(path.read_text(encoding="utf-8"))
        errors = list(Draft202012Validator(schema).iter_errors(profile))
        if errors:
            return AssertionResult(
                22,
                "phase-3-language-profiles",
                False,
                f"{path.name} invalid: {errors[0].message[:120]}",
            )
        markers_by_profile[profile["name"]] = set(profile["detection"]["markers"])
    if "python" in markers_by_profile and "typescript" in markers_by_profile:
        overlap = markers_by_profile["python"] & markers_by_profile["typescript"]
        if overlap:
            return AssertionResult(
                22,
                "phase-3-language-profiles",
                False,
                f"python/typescript marker collision: {sorted(overlap)}",
            )
    return AssertionResult(22, "phase-3-language-profiles", True, f"{len(profile_files)} profiles")


def _check_agent_files_present(
    real_root: Path,
    *,
    number: int,
    name: str,
    expected: list[tuple[str, str, str]],
) -> AssertionResult:
    """Helper: each (relative_path, expected_name, expected_tier) tuple must
    point at a real file with valid frontmatter matching the expected fields."""
    schema_path = real_root / "schemas" / "agent-frontmatter.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    for relpath, expected_name, expected_tier in expected:
        path = real_root / relpath
        if not path.is_file():
            return AssertionResult(number, name, False, f"missing: {relpath}")
        fm = _parse_frontmatter(path.read_text(encoding="utf-8"))
        if not fm:
            return AssertionResult(number, name, False, f"{relpath}: no frontmatter")
        if fm.get("name") != expected_name:
            return AssertionResult(
                number, name, False, f"{relpath}: name={fm.get('name')!r} != {expected_name!r}"
            )
        if fm.get("tier") != expected_tier:
            return AssertionResult(
                number, name, False, f"{relpath}: tier={fm.get('tier')!r} != {expected_tier!r}"
            )
        errors = list(Draft202012Validator(schema).iter_errors(fm))
        if errors:
            return AssertionResult(
                number, name, False, f"{relpath}: frontmatter invalid: {errors[0].message[:120]}"
            )
    return AssertionResult(number, name, True, f"{len(expected)} agents")


def _check_phase_3_codebase_scanner_agents(real_root: Path) -> AssertionResult:
    """Assertion 23: the four codebase R-tier scanner agents are present
    with valid frontmatter and tier=read."""
    return _check_agent_files_present(
        real_root,
        number=23,
        name="phase-3-codebase-scanners",
        expected=[
            (
                "agents/codebase/codebase-inventory-scanner.md",
                "codebase-inventory-scanner",
                "read",
            ),
            (
                "agents/codebase/codebase-dependency-grapher.md",
                "codebase-dependency-grapher",
                "read",
            ),
            (
                "agents/codebase/codebase-dead-code-detector.md",
                "codebase-dead-code-detector",
                "read",
            ),
            (
                "agents/codebase/codebase-convention-profiler.md",
                "codebase-convention-profiler",
                "read",
            ),
        ],
    )


def _check_phase_3_db_api_scanner_agents(real_root: Path) -> AssertionResult:
    """Assertion 24: db-schema-scanner and api-contract-extractor are
    present with valid frontmatter and tier=read."""
    return _check_agent_files_present(
        real_root,
        number=24,
        name="phase-3-db-api-scanners",
        expected=[
            ("agents/database/db-schema-scanner.md", "db-schema-scanner", "read"),
            ("agents/api/api-contract-extractor.md", "api-contract-extractor", "read"),
        ],
    )


def _check_phase_3_reason_analyst_agents(real_root: Path) -> AssertionResult:
    """Assertion 25: the three reason-tier analysts are present with
    valid frontmatter, tier=reason, and model=opus."""
    expected = [
        (
            "agents/codebase/codebase-architecture-reconstructor.md",
            "codebase-architecture-reconstructor",
            "reason",
        ),
        ("agents/database/db-migration-planner.md", "db-migration-planner", "reason"),
        ("agents/api/api-breaking-change-analyzer.md", "api-breaking-change-analyzer", "reason"),
    ]
    base = _check_agent_files_present(
        real_root, number=25, name="phase-3-reason-analysts", expected=expected
    )
    if not base.passed:
        return base
    # Phase 3 reason analysts are all model: opus per the established pattern.
    for relpath, _, _ in expected:
        fm = _parse_frontmatter((real_root / relpath).read_text(encoding="utf-8"))
        assert fm is not None  # base check guarantees this
        if fm.get("model") != "opus":
            return AssertionResult(
                25,
                "phase-3-reason-analysts",
                False,
                f"{relpath}: model={fm.get('model')!r} != 'opus'",
            )
    return AssertionResult(25, "phase-3-reason-analysts", True, f"{len(expected)} analysts")


def _check_phase_3_codebase_report_schemas(real_root: Path) -> AssertionResult:
    """Assertion 26: the four codebase scanner report schemas
    self-validate and accept a minimal positive example."""
    examples: list[tuple[str, dict[str, Any]]] = [
        (
            "codebase-inventory.schema.json",
            {
                "generated_at": "2026-05-04T08:00:00Z",
                "project_dir": "/p",
                "file_count_total": 1,
                "file_counts_by_extension": {".py": 1},
                "loc_total": 3,
                "loc_by_extension": {".py": 3},
                "top_level_dirs": ["src"],
                "depth_max": 1,
                "languages_detected": ["python"],
            },
        ),
        (
            "dependency-graph.schema.json",
            {
                "generated_at": "2026-05-04T08:00:00Z",
                "project_dir": "/p",
                "summary": {
                    "node_count": 2,
                    "edge_count": 1,
                    "internal_node_count": 2,
                    "external_node_count": 0,
                },
                "nodes": [
                    {"id": "a", "kind": "internal", "language": "python", "path": "src/a.py"},
                    {"id": "b", "kind": "internal", "language": "python", "path": "src/b.py"},
                ],
                "edges": [{"source": "a", "target": "b", "kind": "import"}],
            },
        ),
        (
            "dead-code.schema.json",
            {
                "generated_at": "2026-05-04T08:00:00Z",
                "project_dir": "/p",
                "summary": {"unused_import_count": 0, "tool_finding_count": 0},
                "unused_imports": [],
                "orphan_modules": [],
                "tool_reports": [],
            },
        ),
        (
            "convention-profile.schema.json",
            {
                "generated_at": "2026-05-04T08:00:00Z",
                "project_dir": "/p",
                "summary": {
                    "files_scanned": 0,
                    "identifiers_checked": 0,
                    "deviations_count": 0,
                    "conformance_by_kind": {},
                },
                "deviations": [],
            },
        ),
    ]
    return _validate_schema_with_examples(
        real_root, number=26, name="phase-3-codebase-schemas", schema_examples=examples
    )


def _check_phase_3_db_api_report_schemas(real_root: Path) -> AssertionResult:
    """Assertion 27: db-schema and api-contract report schemas
    self-validate and accept a minimal positive example."""
    examples: list[tuple[str, dict[str, Any]]] = [
        (
            "db-schema.schema.json",
            {
                "generated_at": "2026-05-04T08:00:00Z",
                "project_dir": "/p",
                "engine": None,
                "database_name": None,
                "schema_name": None,
                "summary": {
                    "table_count": 0,
                    "column_count_total": 0,
                    "index_count_total": 0,
                    "constraint_count_total": 0,
                    "relationship_count": 0,
                },
                "tables": [],
                "relationships": [],
                "notes": ["DATABASE_URL not set; no schema introspected."],
            },
        ),
        (
            "api-contract.schema.json",
            {
                "generated_at": "2026-05-04T08:00:00Z",
                "project_dir": "/p",
                "summary": {
                    "contract_count": 0,
                    "openapi_count": 0,
                    "trpc_count": 0,
                    "graphql_count": 0,
                    "total_paths": 0,
                },
                "contracts": [],
            },
        ),
    ]
    return _validate_schema_with_examples(
        real_root, number=27, name="phase-3-db-api-schemas", schema_examples=examples
    )


def _check_phase_3_analyst_report_schemas(real_root: Path) -> AssertionResult:
    """Assertion 28: the three reason-analyst report schemas
    self-validate and accept a minimal positive example."""
    examples: list[tuple[str, dict[str, Any]]] = [
        (
            "architecture-reconstruction.schema.json",
            {
                "generated_at": "2026-05-04T08:00:00Z",
                "project_dir": "/p",
                "inputs": [],
                "summary": {
                    "findings_count": 0,
                    "findings_by_severity": {"high": 0, "medium": 0, "low": 0},
                    "recommendations_count": 0,
                    "inputs_consumed": 0,
                    "layering_status": "unclear",
                },
                "findings": [],
                "recommendations": [],
            },
        ),
        (
            "migration-plan.schema.json",
            {
                "generated_at": "2026-05-04T08:00:00Z",
                "project_dir": "/p",
                "inputs": [],
                "summary": {
                    "changes_count": 0,
                    "steps_count": 0,
                    "steps_by_risk": {"high": 0, "medium": 0, "low": 0},
                    "inputs_consumed": 0,
                    "target_provided": False,
                    "planning_status": "no_current",
                },
                "changes": [],
                "steps": [],
            },
        ),
        (
            "api-breaking-changes.schema.json",
            {
                "generated_at": "2026-05-04T08:00:00Z",
                "project_dir": "/p",
                "inputs": [],
                "summary": {
                    "changes_count": 0,
                    "changes_by_breaking": {
                        "breaking": 0,
                        "potentially-breaking": 0,
                        "non-breaking": 0,
                    },
                    "changes_by_severity": {"high": 0, "medium": 0, "low": 0},
                    "inputs_consumed": 0,
                    "analysis_status": "skipped",
                },
                "changes": [],
            },
        ),
    ]
    return _validate_schema_with_examples(
        real_root, number=28, name="phase-3-analyst-schemas", schema_examples=examples
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


ASSERTIONS: list[Callable[[Path], AssertionResult]] = [
    _check_validate_command_present,
    _check_objective_verifier_present,
    _check_commit_without_stamp_blocks,
    _check_commit_with_valid_stamp_passes,
    _check_stale_stamp_blocks,
    _check_wip_bypass,
    _check_merge_head_bypass,
    _check_path_traversal_rejected,
    _check_agent_tier_consistency,
    _check_transcript_todo_extractor_schema,
    _check_doc_size_limit,
    _check_context_budget_hard_cut,
    _check_secret_scan_and_gitignore,
    _check_tier_enforcer_blocks_edit,
    _check_bash_tier_guard_blocks_rm,
    _check_stop_validation_blocks_dirty_tree,
    _check_stop_failure_writes_incident,
    _check_telemetry_concurrent_safe,
    _check_meta_agent_arch_doc_reviewer,
    _check_checkpoint_gate_blocks_stale,
    _check_secret_scan_staged,
    _check_phase_3_language_profiles,
    _check_phase_3_codebase_scanner_agents,
    _check_phase_3_db_api_scanner_agents,
    _check_phase_3_reason_analyst_agents,
    _check_phase_3_codebase_report_schemas,
    _check_phase_3_db_api_report_schemas,
    _check_phase_3_analyst_report_schemas,
]


def run_all(root: Path) -> list[AssertionResult]:
    return [check(root) for check in ASSERTIONS]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 1+2 bootstrap-smoke exit-gate test")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    root: Path = args.root.resolve()
    results = run_all(root)
    total = len(results)

    for r in results:
        status = "PASS" if r.passed else "FAIL"
        line = f"[bootstrap-smoke] {r.number:>2}/{total} [{status}] {r.name}"
        if r.detail:
            line += f" - {r.detail}"
        print(line)
        if args.verbose and r.notes:
            for note in r.notes:
                print(f"    · {note}")

    passed = sum(1 for r in results if r.passed)
    outcome = "OK" if passed == total else "FAILED"
    print(f"[bootstrap-smoke] {passed}/{total} passed - Phase 1+2+3 exit gate {outcome}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
