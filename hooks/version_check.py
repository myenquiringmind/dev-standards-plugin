"""Compare the installed plugin version against the marketplace clone.

Fires on SessionStart. Reads ``<project>/.claude-plugin/plugin.json``
and the marketplace clone's plugin manifest, compares versions
semver-style, and surfaces a stderr advisory when the marketplace
clone is ahead of the installed copy.

Result is cached in ``<memory>/version-check.state.json`` for
``VERSION_CHECK_INTERVAL_SECONDS`` (24h). A cache hit short-
circuits before any disk reads of the manifests, keeping
SessionStart cheap on a busy day.

Marketplace clone resolution, in order:

1. ``DSP_MARKETPLACE_CLONE`` env override (lets tests inject a
   fixture path; lets users with a non-default install layout
   point at their actual clone).
2. ``$HOME/.claude/plugins/marketplaces/<owner>/<repo>/`` —
   derived from the installed manifest's ``repository`` URL.

If the marketplace manifest is missing or unreadable the hook
records an "unknown" result in the cache and exits silently —
many users will never sync a marketplace clone, and warning them
about it on every session would be noise.

Never networks. Never blocks. Always exits 0.

Event: SessionStart
Matcher: *
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from hooks._hook_shared import (
    VERSION_CHECK_INTERVAL_SECONDS,
    get_project_dir,
    read_hook_input,
)
from hooks._os_safe import atomic_write
from hooks._session_state_common import get_memory_dir

_CACHE_FILENAME: str = "version-check.state.json"
_PLUGIN_MANIFEST_REL: Path = Path(".claude-plugin") / "plugin.json"
_GITHUB_REPO_RE = re.compile(
    r"^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$"
)


def _read_cache(cache_path: Path) -> dict[str, Any] | None:
    """Load the cache file, returning ``None`` on any fault."""
    try:
        text = cache_path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _cache_is_fresh(cache: dict[str, Any], now: float) -> bool:
    checked_at = cache.get("checked_at_epoch")
    if not isinstance(checked_at, (int, float)):
        return False
    return (now - float(checked_at)) < VERSION_CHECK_INTERVAL_SECONDS


def _load_manifest(path: Path) -> dict[str, Any] | None:
    """Load a plugin manifest, returning ``None`` if absent/malformed."""
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _manifest_version(manifest: dict[str, Any] | None) -> str:
    if manifest is None:
        return ""
    value = manifest.get("version")
    return value.strip() if isinstance(value, str) and value.strip() else ""


def _resolve_marketplace_manifest(installed: dict[str, Any] | None) -> Path | None:
    """Resolve the marketplace clone's plugin.json path, or ``None``."""
    override = os.environ.get("DSP_MARKETPLACE_CLONE")
    if override:
        candidate = Path(override)
        if candidate.is_file():
            return candidate
        # Treat the override as a directory containing the plugin.
        return candidate / _PLUGIN_MANIFEST_REL

    if installed is None:
        return None
    repo = installed.get("repository")
    if not isinstance(repo, str):
        return None
    match = _GITHUB_REPO_RE.match(repo.strip())
    if match is None:
        return None
    owner = match.group("owner")
    repo_name = match.group("repo")
    return (
        Path.home()
        / ".claude"
        / "plugins"
        / "marketplaces"
        / owner
        / repo_name
        / _PLUGIN_MANIFEST_REL
    )


def _parse_version(version: str) -> tuple[Any, ...]:
    """Parse a dotted version into a tuple suitable for comparison.

    Numeric segments compare numerically; non-numeric segments fall
    through to lexicographic. Empty input yields an empty tuple,
    which sorts before everything else.
    """
    if not version:
        return ()
    parts: list[Any] = []
    for segment in version.split("."):
        try:
            parts.append((0, int(segment)))
        except ValueError:
            parts.append((1, segment))
    return tuple(parts)


def _is_remote_newer(local: str, remote: str) -> bool:
    """Return ``True`` only when both versions parse and remote > local."""
    if not local or not remote:
        return False
    return _parse_version(remote) > _parse_version(local)


def _build_record(
    *,
    now: float,
    installed: str,
    marketplace: str,
    update_available: bool,
) -> dict[str, Any]:
    return {
        "schema": "1.0.0",
        "checked_at_epoch": now,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "installed_version": installed,
        "marketplace_version": marketplace,
        "update_available": update_available,
    }


def _write_cache(cache_path: Path, record: dict[str, Any]) -> None:
    try:
        atomic_write(
            cache_path,
            json.dumps(record, indent=2, sort_keys=True) + "\n",
        )
    except OSError as exc:
        print(f"[version_check] could not write cache: {exc}", file=sys.stderr)


def main() -> int:
    read_hook_input()  # drain stdin

    project_dir = get_project_dir()
    memory_dir = get_memory_dir(project_dir)
    cache_path = memory_dir / _CACHE_FILENAME

    now = time.time()
    cache = _read_cache(cache_path)
    if cache is not None and _cache_is_fresh(cache, now):
        return 0

    installed_manifest = _load_manifest(project_dir / _PLUGIN_MANIFEST_REL)
    installed_version = _manifest_version(installed_manifest)

    marketplace_path = _resolve_marketplace_manifest(installed_manifest)
    marketplace_manifest = (
        _load_manifest(marketplace_path) if marketplace_path is not None else None
    )
    marketplace_version = _manifest_version(marketplace_manifest)

    update_available = _is_remote_newer(installed_version, marketplace_version)
    if update_available:
        print(
            f"[version_check] dev-standards-plugin update available: "
            f"installed {installed_version} → marketplace {marketplace_version}. "
            f"Refresh: git -C "
            f'"$HOME/.claude/plugins/marketplaces/<owner>" pull origin master',
            file=sys.stderr,
        )

    _write_cache(
        cache_path,
        _build_record(
            now=now,
            installed=installed_version,
            marketplace=marketplace_version,
            update_available=update_available,
        ),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
