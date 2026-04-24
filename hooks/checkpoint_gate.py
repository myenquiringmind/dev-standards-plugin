"""Block subagent Bash calls when session-state is stale.

Third of the tier-enforcement group, but orthogonal to R/R/W tiering
itself: this hook fires regardless of the subagent's declared tier.
It is a staleness gate — not a tier gate.

Failure mode it guards against: a subagent runs a pure-Bash workflow
(``git log``, ``curl``, ``jq``, etc.) for a long time without ever
triggering ``PostToolUse Edit|Write|MultiEdit`` — which means
``session_checkpoint`` never fires, ``session-state.md`` is never
refreshed, and the subagent's in-memory context drifts arbitrarily
from the persisted session state. A crash at that point loses the
drift. A destructive Bash call at that point acts on a stale
mental model.

Mechanism: the hook reads ``session-checkpoint.state.json``. If
``last_write_ts`` is present and non-zero, it compares ``now`` to
``last_write_ts`` against ``CHECKPOINT_STALENESS_THRESHOLD_SECONDS``
(30 min by default — two missed ``CHECKPOINT_INTERVAL_SECONDS``
cycles). Over the threshold and the subagent Bash call is blocked
with a message telling the caller to force a checkpoint (any
Edit/Write from the main thread flushes it) or to escalate via
``AskUserQuestion`` / ``/handoff``.

Fail-open on:
- No ``agent_type`` in payload → main-thread Bash, not our business.
- No state file → no checkpoint has ever fired (fresh session).
- ``last_write_ts`` missing or ``<= 0`` → checkpoint counter is
  accumulating but has not flushed yet; nothing stale to measure.
- Malformed JSON in state file → consistent with
  ``session_checkpoint``'s defaults-on-fault contract.

Event: PreToolUse
Matcher: Bash
"""

from __future__ import annotations

import json
import sys
import time

from hooks._hook_shared import (
    CHECKPOINT_STALENESS_THRESHOLD_SECONDS,
    get_project_dir,
    read_hook_input,
)
from hooks._session_state_common import get_memory_dir

_STATE_FILENAME: str = "session-checkpoint.state.json"


def _load_last_write_ts() -> float:
    """Return the ``last_write_ts`` recorded by ``session_checkpoint``.

    Returns ``0.0`` for every fail-open case: missing file, unreadable
    file, malformed JSON, non-dict root, missing or non-numeric
    ``last_write_ts`` field. Callers treat ``0.0`` as "no checkpoint
    to measure against" and pass through.
    """
    state_path = get_memory_dir(get_project_dir()) / _STATE_FILENAME
    try:
        raw = state_path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return 0.0

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return 0.0

    if not isinstance(parsed, dict):
        return 0.0

    ts = parsed.get("last_write_ts", 0.0)
    if isinstance(ts, (int, float)):
        return float(ts)
    return 0.0


def main() -> int:
    data = read_hook_input()

    tool_name = str(data.get("tool_name", ""))
    if tool_name != "Bash":
        return 0

    agent_type = data.get("agent_type")
    if not isinstance(agent_type, str) or not agent_type:
        # Main-thread Bash. The framework does not police user tool calls.
        return 0

    last_write_ts = _load_last_write_ts()
    if last_write_ts <= 0:
        # No checkpoint has flushed yet — nothing to measure.
        return 0

    elapsed = time.time() - last_write_ts
    if elapsed < CHECKPOINT_STALENESS_THRESHOLD_SECONDS:
        return 0

    print(
        f"[checkpoint_gate] refusing Bash — subagent '{agent_type}' is "
        f"attempting a Bash call, but the session has not checkpointed "
        f"session-state in {int(elapsed)}s (threshold: "
        f"{CHECKPOINT_STALENESS_THRESHOLD_SECONDS}s). Bash-only workflows "
        f"do not trigger PostToolUse Edit/Write, so session-state.md "
        f"is stale and at-risk. Force a checkpoint by running an "
        f"Edit/Write from the main thread, or escalate via "
        f"`AskUserQuestion` / `/handoff` if continued work is unsafe.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
