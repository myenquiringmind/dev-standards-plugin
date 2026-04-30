"""Detect the project's primary language profile and stamp the result.

Fires on SessionStart. Writes ``<project>/.language_profile.json`` if
the file does not already exist; otherwise no-ops. Other hooks
(``post_edit_lint``, ``post_auto_format``, future ``cwd_changed`` /
``worktree_lifecycle``) read the stamped result to drive language-
aware behaviour without re-running detection on every event.

Detection algorithm:

1. Enumerate ``config/profiles/*.json``.
2. For each profile, load + validate the shape we depend on
   (``name`` / ``priority`` / ``detection.markers``). Malformed or
   incomplete profiles are skipped silently.
3. A profile matches if any literal marker filename in
   ``detection.markers`` exists at the project root. Markers are
   treated as plain filenames — the schema's "patterns" wording is
   forward-looking; supporting globs can come when a real profile
   needs them.
4. Among matches, pick the lowest priority code (``P0`` beats ``P1``
   beats ``P2`` beats ``P3``). Stable tie-break by profile name.
5. Write the stamped record. No match → write a sentinel with empty
   ``name`` to short-circuit re-scans on subsequent SessionStarts.

Idempotent on re-runs: an existing ``.language_profile.json`` is
never overwritten by this hook. ``cwd_changed`` (Phase 2 follow-on)
deletes the file to force re-detection when the cwd moves.

Never blocks. Always exits 0.

Event: SessionStart
Matcher: *
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hooks._hook_shared import get_project_dir, read_hook_input
from hooks._os_safe import atomic_write

_TARGET_FILENAME: str = ".language_profile.json"
_PROFILES_GLOB: str = "config/profiles/*.json"
_VALID_PRIORITIES: tuple[str, ...] = ("P0", "P1", "P2", "P3")
_RECORD_SCHEMA_VERSION: str = "1.0.0"


def _safe_load_profile(path: Path) -> dict[str, Any] | None:
    """Load a profile, returning ``None`` on any shape/parse failure."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None

    name = data.get("name")
    priority = data.get("priority")
    detection = data.get("detection")
    if not isinstance(name, str) or not name.strip():
        return None
    if priority not in _VALID_PRIORITIES:
        return None
    if not isinstance(detection, dict):
        return None
    markers = detection.get("markers")
    if not isinstance(markers, list) or not all(isinstance(m, str) and m.strip() for m in markers):
        return None
    return data


def _matched_markers(profile: dict[str, Any], project_dir: Path) -> list[str]:
    """Return the subset of *profile*'s markers present at *project_dir*."""
    markers: list[str] = profile["detection"]["markers"]
    return [m for m in markers if (project_dir / m).exists()]


def _detect(project_dir: Path) -> tuple[dict[str, Any], list[str]] | None:
    """Return ``(profile, matched_markers)`` for the best match, or ``None``."""
    matches: list[tuple[str, str, dict[str, Any], list[str]]] = []
    for profile_path in sorted(project_dir.glob(_PROFILES_GLOB)):
        profile = _safe_load_profile(profile_path)
        if profile is None:
            continue
        matched = _matched_markers(profile, project_dir)
        if not matched:
            continue
        matches.append((profile["priority"], profile["name"], profile, matched))

    if not matches:
        return None

    matches.sort(key=lambda item: (item[0], item[1]))
    _, _, profile, matched = matches[0]
    return profile, matched


def _build_record(
    profile: dict[str, Any] | None,
    matched: list[str],
    now: datetime,
) -> dict[str, Any]:
    """Construct the JSON payload to stamp."""
    if profile is None:
        return {
            "schema": _RECORD_SCHEMA_VERSION,
            "name": "",
            "priority": "",
            "detected_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "markers_matched": [],
        }
    return {
        "schema": _RECORD_SCHEMA_VERSION,
        "name": profile["name"],
        "priority": profile["priority"],
        "detected_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "markers_matched": matched,
    }


def detect_and_stamp(project_dir: Path, *, force: bool = False) -> None:
    """Detect the project's profile and write the stamp.

    Public entry point shared with ``cwd_changed`` and other hooks
    that need to refresh the stamp outside SessionStart.

    Args:
        project_dir: Project root containing ``config/profiles/*.json``.
        force: When ``True``, overwrite any existing
            ``.language_profile.json``. When ``False`` (the default
            and the SessionStart behaviour), an existing stamp is
            preserved.
    """
    target = project_dir / _TARGET_FILENAME

    if target.exists() and not force:
        return

    result = _detect(project_dir)
    if result is None:
        record = _build_record(None, [], datetime.now(UTC))
    else:
        profile, matched = result
        record = _build_record(profile, matched, datetime.now(UTC))

    try:
        atomic_write(target, json.dumps(record, indent=2, sort_keys=True) + "\n")
    except OSError as exc:
        print(f"[detect_language] could not write {target}: {exc}", file=sys.stderr)


def main() -> int:
    read_hook_input()  # drain stdin even if we don't read fields
    detect_and_stamp(get_project_dir(), force=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
