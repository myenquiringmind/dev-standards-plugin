"""Emit telemetry for which CLAUDE.md / rules files CC loaded this session.

Fires on the InstructionsLoaded event. Records one
``instructions-loaded`` telemetry entry per fire under
``<project>/.claude/telemetry/<YYYY-MM-DD>.jsonl`` containing the
list of loaded paths plus a count. Phase 4's
``closed-loop-quality-scorer`` correlates session outcomes against
which rules were actively in scope; that pipeline is the consumer
of these records.

Payload shape handling: CC's InstructionsLoaded contract is not
fully nailed down across versions, so we accept a small set of
candidate fields and either a list of strings or a list of dicts
with a ``path`` key. Anything we cannot normalise to a string list
is silently dropped from the emitted record (the count drops with
it). The hook errs toward emitting a record with whatever it could
parse — a partial audit beats no audit.

Never blocks. Always exits 0. ``_telemetry.emit`` swallows I/O
failures internally.

Event: InstructionsLoaded
Matcher: *
"""

from __future__ import annotations

import sys

from hooks._hook_shared import read_hook_input
from hooks._telemetry import emit

_CANDIDATE_KEYS: tuple[str, ...] = (
    "instructions",
    "loaded_files",
    "files",
    "paths",
)


def _normalise_to_path_list(value: object) -> list[str]:
    """Coerce *value* to a list of non-empty path strings."""
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
        elif isinstance(item, dict):
            path = item.get("path")
            if isinstance(path, str) and path.strip():
                out.append(path.strip())
    return out


def _extract_files(data: dict[str, object]) -> list[str]:
    """Find the first candidate key that yields a non-empty path list."""
    for key in _CANDIDATE_KEYS:
        files = _normalise_to_path_list(data.get(key))
        if files:
            return files
    return []


def main() -> int:
    data = read_hook_input()

    files = _extract_files(data)
    emit("instructions-loaded", {"files": files, "count": len(files)})
    return 0


if __name__ == "__main__":
    sys.exit(main())
