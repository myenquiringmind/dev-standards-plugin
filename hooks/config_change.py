"""Invalidate on-disk caches when CC reports a config-file change.

Hooks are stateless — there is no in-memory state to "reload" when
a config file changes. What there *is* is a small set of on-disk
caches written by other hooks, and those need to be removed so the
next hook fire reads fresh data.

Watched files and the cache they invalidate:

- ``config/profiles/*.json`` → ``<project>/.language_profile.json``
  (the stamped detection result; ``detect_language`` will rebuild
  it on the next SessionStart, or ``cwd_changed`` will if the user
  navigates away and back).
- ``.claude-plugin/plugin.json`` → ``<memory>/version-check.state.json``
  (the 24-hour cached marketplace-diff result; the next SessionStart
  will re-run ``version_check`` because the cache is gone).
- ``config/graph-registry.json`` → no on-disk cache currently exists
  (the registry is loaded on demand by ``_graph.load_registry``).
  Tracked here as a known no-op for documentation; future cache
  files added for the registry will join the dispatch table.

Off-watch paths and paths outside the project root are silent
no-ops. Per-file unlink failures (typical: Windows AV holding a
stale handle) log to stderr and continue — the rest of the
invalidation is not short-circuited.

Never networks. Never blocks. Always exits 0.

Event: ConfigChange
Matcher: *
"""

from __future__ import annotations

import sys
from pathlib import Path

from hooks._hook_shared import get_project_dir, read_hook_input
from hooks._session_state_common import get_memory_dir

_PROFILES_DIR_NAME: str = "profiles"
_CONFIG_DIR_NAME: str = "config"
_GRAPH_REGISTRY: tuple[str, ...] = ("config", "graph-registry.json")
_PLUGIN_MANIFEST: tuple[str, ...] = (".claude-plugin", "plugin.json")

_LANGUAGE_PROFILE_CACHE: str = ".language_profile.json"
_VERSION_CHECK_CACHE: str = "version-check.state.json"


def _extract_changed_path(data: dict[str, object]) -> str:
    """Pull a non-empty path string from the ConfigChange payload."""
    for key in ("path", "file_path"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _resolve_in_project(raw: str, project_dir: Path) -> Path | None:
    """Return *raw* as an absolute ``Path`` under *project_dir*, or ``None``."""
    candidate = Path(raw)
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


def _caches_to_invalidate(rel_parts: tuple[str, ...], project_dir: Path) -> list[Path]:
    """Map the watched relative path to the cache files it invalidates."""
    targets: list[Path] = []
    if (
        len(rel_parts) == 3
        and rel_parts[0] == _CONFIG_DIR_NAME
        and rel_parts[1] == _PROFILES_DIR_NAME
        and rel_parts[2].endswith(".json")
    ):
        targets.append(project_dir / _LANGUAGE_PROFILE_CACHE)
    elif rel_parts == _PLUGIN_MANIFEST:
        targets.append(get_memory_dir(project_dir) / _VERSION_CHECK_CACHE)
    # ``_GRAPH_REGISTRY`` falls through — known no-op until a registry cache
    # exists. Documented in the module docstring.
    return targets


def _unlink_quiet(path: Path) -> None:
    """Best-effort delete. Missing → silent. OSError → stderr."""
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        print(
            f"[config_change] could not invalidate {path}: {exc}",
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

    try:
        rel_parts = target.relative_to(project_dir.resolve(strict=False)).parts
    except ValueError:
        return 0

    for cache in _caches_to_invalidate(rel_parts, project_dir):
        _unlink_quiet(cache)

    return 0


if __name__ == "__main__":
    sys.exit(main())
