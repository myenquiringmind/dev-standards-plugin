"""Build ``config/graph-registry.json`` from on-disk framework components.

Walks the v2 component trees (``agents/``, ``hooks/``, ``commands/``,
``.claude/rules/``, ``config/profiles/``, ``skills/``) and emits a
registry JSON matching ``schemas/graph-registry.schema.json``. The
output is self-validated before it hits disk — a schema failure
exits non-zero without overwriting the existing file.

Phase 1 emits nodes only. Edges require cross-component link
derivation (e.g. ``hooks.json`` matcher → gated tools, command
bodies → composed agents) which lands in Phase 2+. The empty edge
array is a valid registry per the schema.

Usage:
    uv run python -m scripts.build_graph_registry
    uv run python -m scripts.build_graph_registry --output path.json
    uv run python -m scripts.build_graph_registry --check
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

_REGISTRY_VERSION: str = "1.0.0"
_HOOK_EVENT_RE = re.compile(r"^Event:\s*(.+)$", re.MULTILINE)
_HOOK_MATCHER_RE = re.compile(r"^Matcher:\s*(.+)$", re.MULTILINE)
_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def _parse_frontmatter(text: str) -> dict[str, Any] | None:
    """Tiny YAML-subset parser for agent/command frontmatter.

    Accepts scalar values, list-literals ``[a, b, c]``, quoted
    strings, bools, and ints. Nested structures are not supported
    — add ``pyyaml`` as a dev dep if that ever becomes necessary.
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return None

    result: dict[str, Any] = {}
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


def discover_agents(root: Path) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for path in sorted((root / "agents").rglob("*.md")):
        if path.name == "CLAUDE.md":
            continue
        fm = _parse_frontmatter(path.read_text(encoding="utf-8"))
        if not fm or "name" not in fm:
            continue  # v1-legacy files without frontmatter are silently skipped
        category = str(path.relative_to(root / "agents").parent).replace("\\", "/")
        if category in ("", "."):
            category = "meta"  # flat-root v2 file (rare); default category
        nodes.append(
            {
                "id": fm["name"],
                "type": "Agent",
                "category": category,
                "scope": fm.get("scope", "core"),
                "metadata": {
                    "agent_type": _infer_agent_type(fm),
                    "model": fm.get("model", "sonnet"),
                    **({"effort": fm["effort"]} if "effort" in fm else {}),
                    "tools": fm.get("tools", []),
                    **(
                        {"disallowedTools": fm["disallowedTools"]}
                        if "disallowedTools" in fm
                        else {}
                    ),
                    **({"skills": fm["skills"]} if "skills" in fm else {}),
                    "memory": fm.get("memory", "none"),
                    "maxTurns": int(fm.get("maxTurns", 10)),
                    **({"isolation": fm["isolation"]} if "isolation" in fm else {}),
                    **({"background": fm["background"]} if "background" in fm else {}),
                    **({"tier": fm["tier"]} if "tier" in fm else {}),
                },
            }
        )
    return nodes


def _infer_agent_type(fm: dict[str, Any]) -> str:
    """Map agent frontmatter to a GraphRegistry agent_type bucket."""
    if fm.get("background"):
        return "background"
    if fm.get("isolation") == "worktree":
        return "auto-fixer"
    # Blocking reviewers are reason-tier + in meta/validation; everything else advisory.
    tier = fm.get("tier")
    name = fm.get("name", "")
    if tier == "reason" and (name.startswith("meta-") or name.startswith("validation-")):
        return "blocking"
    return "advisory"


def discover_hooks(root: Path) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for path in sorted((root / "hooks").glob("*.py")):
        if path.name.startswith("_") or path.name == "__init__.py":
            continue
        text = path.read_text(encoding="utf-8")
        event_match = _HOOK_EVENT_RE.search(text)
        matcher_match = _HOOK_MATCHER_RE.search(text)
        if not event_match:
            continue  # shared-module-looking file without Event declaration
        event = event_match.group(1).strip()
        matcher = matcher_match.group(1).strip() if matcher_match else ""
        # Hook filenames use snake_case (Python convention); registry ids
        # use kebab-case (schema regex), so normalize on the way in.
        hook_id = path.stem.replace("_", "-")
        nodes.append(
            {
                "id": hook_id,
                "type": "Hook",
                "category": "core",
                "metadata": {
                    "event": event,
                    "matcher": matcher,
                    "timeout_ms": 5000,  # conservative default; tighten from hooks.json in Phase 2
                    "blocking": event.startswith("Pre") or event == "UserPromptSubmit",
                    "hook_type": "command",
                },
            }
        )
    return nodes


def discover_commands(root: Path) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for path in sorted((root / "commands").glob("*.md")):
        if path.name == "CLAUDE.md":
            continue
        fm = _parse_frontmatter(path.read_text(encoding="utf-8"))
        if not fm:
            continue  # v1-legacy commands without frontmatter are skipped
        nodes.append(
            {
                "id": path.stem,
                "type": "Command",
                "category": "core",
                "metadata": {
                    "context": fm.get("context", "none"),
                    "model": fm.get("model", "sonnet"),
                    "allowed_tools": (
                        fm.get("allowed-tools", [])
                        if isinstance(fm.get("allowed-tools"), list)
                        else [
                            x.strip()
                            for x in str(fm.get("allowed-tools", "")).split(",")
                            if x.strip()
                        ]
                    ),
                    "phase": fm.get("phase", "meta"),
                },
            }
        )
    return nodes


def discover_rules(root: Path) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    rules_dir = root / ".claude" / "rules"
    if not rules_dir.is_dir():
        return nodes
    for path in sorted(rules_dir.glob("*.md")):
        nodes.append(
            {
                "id": path.stem,
                "type": "Rule",
                "category": "core",
                "metadata": {"source_path": str(path.relative_to(root)).replace("\\", "/")},
            }
        )
    return nodes


def discover_profiles(root: Path) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    profiles_dir = root / "config" / "profiles"
    if not profiles_dir.is_dir():
        return nodes
    for path in sorted(profiles_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict) or "detection" not in data:
            continue
        nodes.append(
            {
                "id": path.stem,
                "type": "Profile",
                "category": "languages",
                "metadata": {
                    "detection": data["detection"],
                    "priority": str(data.get("priority", "P2")),
                },
            }
        )
    return nodes


def discover_skills(root: Path) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    skills_dir = root / "skills"
    if not skills_dir.is_dir():
        return nodes
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        nodes.append(
            {
                "id": skill_md.parent.name,
                "type": "Skill",
                "category": "core",
                "metadata": {"source_path": str(skill_md.relative_to(root)).replace("\\", "/")},
            }
        )
    return nodes


def _source_commit(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    sha = result.stdout.strip()
    return sha if re.fullmatch(r"[0-9a-f]{7,40}", sha) else None


def build_registry(root: Path) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    nodes.extend(discover_agents(root))
    nodes.extend(discover_hooks(root))
    nodes.extend(discover_commands(root))
    nodes.extend(discover_rules(root))
    nodes.extend(discover_profiles(root))
    nodes.extend(discover_skills(root))

    registry: dict[str, Any] = {
        "version": _REGISTRY_VERSION,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "nodes": nodes,
        "edges": [],
    }
    commit = _source_commit(root)
    if commit:
        registry["source_commit"] = commit
    return registry


def validate_registry(registry: dict[str, Any], schema_path: Path) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(schema).iter_errors(registry))
    return [f"{'.'.join(str(p) for p in e.path) or '(root)'}: {e.message}" for e in errors]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build config/graph-registry.json")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Build and validate but do not write; exit 2 on validation error.",
    )
    args = parser.parse_args(argv)

    root: Path = args.root.resolve()
    output: Path = args.output or root / "config" / "graph-registry.json"
    schema_path = root / "schemas" / "graph-registry.schema.json"

    registry = build_registry(root)
    errors = validate_registry(registry, schema_path)
    if errors:
        print("[build-graph-registry] schema validation failed:", file=sys.stderr)
        for err in errors[:10]:
            print(f"  - {err}", file=sys.stderr)
        return 2

    if args.check:
        print(f"[build-graph-registry] OK — {len(registry['nodes'])} nodes (no write)")
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
    print(f"[build-graph-registry] wrote {len(registry['nodes'])} nodes to {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
