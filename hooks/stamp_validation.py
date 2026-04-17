"""CLI: write a validation stamp when all steps of a gate have passed.

Invoked by the validate pipeline (Phase 1: `/validate`) once every
step for a given gate (code, frontend, agent, db, api) has passed.
The stamp is consumed by ``pre_commit_cli_gate.py`` on ``git commit``
to decide whether the commit can proceed.

Stamp contract (per ``schemas/stamp.schema.json``):

* ``timestamp``  — ISO-8601 UTC, written by this script
* ``branch``     — current git branch
* ``steps``      — ordered list of step names that passed (from args)
* ``ttl_seconds``— const 900 (15 min)
* ``version``    — semver of the stamp format
* ``gate``       — one of ``code|frontend|agent|db|api``
* ``plugin_commit`` — optional git SHA of the installed plugin

Filename is derived from the gate: ``code`` → ``.validation_stamp``,
others → ``.<gate>_validation_stamp``. Always at the project root.

Exit codes:
* 0 — stamp written
* 1 — bad args, schema mismatch, or I/O error

Event: N/A (CLI utility invoked by /validate; not a hook)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

from hooks._hook_shared import STAMP_TTL, get_current_branch, get_project_dir
from hooks._os_safe import atomic_write

if TYPE_CHECKING:
    from collections.abc import Sequence


STAMP_VERSION: str = "1.0.0"

_STAMP_FILENAMES: dict[str, str] = {
    "code": ".validation_stamp",
    "frontend": ".frontend_validation_stamp",
    "agent": ".agent_validation_stamp",
    "db": ".db_validation_stamp",
    "api": ".api_validation_stamp",
}


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="stamp_validation")
    parser.add_argument(
        "--gate",
        required=True,
        choices=sorted(_STAMP_FILENAMES.keys()),
        help="Validation gate this stamp represents.",
    )
    parser.add_argument(
        "--step",
        action="append",
        required=True,
        metavar="NAME",
        help="Repeatable — every step name that passed.",
    )
    parser.add_argument(
        "--plugin-commit",
        default=None,
        help="Optional git SHA of the installed plugin (7-40 hex chars).",
    )
    parser.add_argument(
        "--schema",
        default=None,
        type=Path,
        help="Override schema path (defaults to schemas/stamp.schema.json under project root).",
    )
    return parser.parse_args(argv)


def _load_schema(project_dir: Path, override: Path | None) -> dict[str, Any]:
    path = override if override is not None else project_dir / "schemas" / "stamp.schema.json"
    return cast("dict[str, Any]", json.loads(Path(path).read_text(encoding="utf-8")))


def _build_stamp(args: argparse.Namespace, branch: str) -> dict[str, Any]:
    stamp: dict[str, Any] = {
        "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "branch": branch,
        "steps": list(args.step),
        "ttl_seconds": STAMP_TTL,
        "version": STAMP_VERSION,
        "gate": args.gate,
    }
    if args.plugin_commit:
        stamp["plugin_commit"] = args.plugin_commit
    return stamp


def _stamp_path(project_dir: Path, gate: str) -> Path:
    return project_dir / _STAMP_FILENAMES[gate]


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 1

    project_dir = get_project_dir()
    branch = get_current_branch(project_dir)
    if not branch:
        print("[stamp_validation] could not determine current branch", file=sys.stderr)
        return 1

    stamp = _build_stamp(args, branch)

    try:
        schema = _load_schema(project_dir, args.schema)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[stamp_validation] could not load schema: {exc}", file=sys.stderr)
        return 1

    errors = sorted(Draft202012Validator(schema).iter_errors(stamp), key=lambda e: list(e.path))
    if errors:
        for err in errors:
            path = ".".join(str(p) for p in err.path) or "(root)"
            print(f"[stamp_validation] schema error at {path}: {err.message}", file=sys.stderr)
        return 1

    target = _stamp_path(project_dir, args.gate)
    try:
        atomic_write(target, json.dumps(stamp, indent=2, sort_keys=True) + "\n")
    except OSError as exc:
        print(f"[stamp_validation] could not write stamp: {exc}", file=sys.stderr)
        return 1

    print(f"[stamp_validation] wrote {target.name} for gate '{args.gate}' on branch '{branch}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
