"""Re-validate watched config files when CC reports a FileChanged.

Two paths are watched:

- ``config/graph-registry.json`` → ``schemas/graph-registry.schema.json``
- ``config/profiles/*.json``     → ``schemas/profile.schema.json``

When CC fires ``FileChanged`` against either, the hook loads the
file and the matching schema and runs JSON Schema validation. A
schema violation surfaces a stderr warning naming the file and the
first validation error path. The hook is **advisory only** — the
file has already been written by the time CC fires this event, so
blocking is not an option. The intent is to give the author an
immediate signal when a hand-edit drifts the file out of contract,
ahead of the next ``/validate`` cycle catching it.

Off-watch paths are silent no-ops. The hook never blocks. All
fail-open cases (missing file, missing schema, malformed JSON,
non-JSON content) log to stderr and exit 0.

Event: FileChanged
Matcher: *
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

from hooks._hook_shared import get_project_dir, read_hook_input

_SCHEMA_FOR_REGISTRY: str = "graph-registry.schema.json"
_SCHEMA_FOR_PROFILE: str = "profile.schema.json"


def _extract_changed_path(data: dict[str, object]) -> str:
    """Pull a non-empty path string from the FileChanged payload."""
    for key in ("path", "file_path"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _resolve_in_project(raw_path: str, project_dir: Path) -> Path | None:
    """Return *raw_path* as an absolute ``Path`` under *project_dir*, or ``None``.

    Accepts both absolute and project-relative inputs. Paths outside
    the project root are rejected (no-op upstream).
    """
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = project_dir / candidate

    try:
        resolved = candidate.resolve(strict=False)
        project_resolved = project_dir.resolve(strict=False)
    except OSError:
        return None

    try:
        resolved.relative_to(project_resolved)
    except ValueError:
        return None
    return resolved


def _schema_for(path: Path, project_dir: Path) -> str | None:
    """Return the schema filename for *path*, or ``None`` if not watched."""
    try:
        rel = path.relative_to(project_dir.resolve(strict=False))
    except ValueError:
        return None

    parts = rel.parts
    if parts == ("config", "graph-registry.json"):
        return _SCHEMA_FOR_REGISTRY
    if (
        len(parts) == 3
        and parts[0] == "config"
        and parts[1] == "profiles"
        and parts[2].endswith(".json")
    ):
        return _SCHEMA_FOR_PROFILE
    return None


def _load_json(path: Path, label: str) -> Any:
    """Load JSON from *path*, logging and returning ``None`` on failure."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"[file_changed] {label} missing: {path}", file=sys.stderr)
        return None
    except OSError as exc:
        print(f"[file_changed] could not read {label} {path}: {exc}", file=sys.stderr)
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"[file_changed] {label} is not valid JSON: {path}: {exc}", file=sys.stderr)
        return None


def _validate(instance: Any, schema: dict[str, Any], file_path: Path) -> None:
    """Run the schema; surface the first error to stderr (advisory)."""
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    if not errors:
        return

    first = errors[0]
    location = "/".join(str(p) for p in first.absolute_path) or "<root>"
    print(
        f"[file_changed] schema violation in {file_path}: {location}: {first.message}",
        file=sys.stderr,
    )


def main() -> int:
    data = read_hook_input()

    raw = _extract_changed_path(data)
    if not raw:
        return 0

    project_dir = get_project_dir()
    target = _resolve_in_project(raw, project_dir)
    if target is None:
        return 0

    schema_name = _schema_for(target, project_dir)
    if schema_name is None:
        return 0

    instance = _load_json(target, "config")
    if instance is None:
        return 0

    schema_path = project_dir / "schemas" / schema_name
    schema = _load_json(schema_path, "schema")
    if schema is None:
        return 0

    _validate(instance, cast("dict[str, Any]", schema), target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
