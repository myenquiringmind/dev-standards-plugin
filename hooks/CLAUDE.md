# hooks/ — Python hooks and shared modules

You are working in the hooks directory. Hooks are deterministic code fired on Claude Code lifecycle events. They block work when invariants are violated, emit telemetry, and carry the framework's mechanical enforcement.

## What goes here

- **Python hook files**: `session_start.py`, `pre_commit_cli_gate.py`, `context_budget.py`, etc. Each responds to a single CC lifecycle event.
- **Shared modules** (underscore-prefix): `_hook_shared.py`, `_session_state_common.py`, `_os_safe.py`, `_telemetry.py`, `_incident.py`, `_graph.py`. These are imported by hooks; they are not themselves hooks.
- **`hooks.json`**: thin shim mapping CC events to Python scripts. Plugin-level hook registration.

## Core rules when adding or editing a hook

1. **One hook per file.** No bundling. If you want hook X to also do Y, those are two hooks.
2. **Python 3.13+ only.** Target syntax and stdlib. No f-string debugging (`{var=}`) unless absolutely necessary.
3. **Exit codes are the contract.** `0` = success, `2` = block, anything else = non-blocking error. Non-negotiable.
4. **Read stdin as JSON.** Use `_hook_shared.read_hook_input()`. Never parse manually.
5. **Use `_os_safe` for every file write.** Atomic writes, portalocker locks, safe_join, normalize_path. Never `open(path, "w")` directly.
6. **Timeout budget is tight.** Default CC hook timeout is ~30s. Pre-tool hooks should be <3s. Post-tool hooks <10s. Session hooks <15s.
7. **Declare your event and matcher in the module docstring.** The graph registry validator reads docstrings.
8. **Never network.** Hooks are local. If you need network, promote to an MCP server.

## Read these first

- `@docs/architecture/principles/psf.md` — Hooks sit at the second rung of the Primitive Selection Framework. Prefer rules first, hooks when determinism is required.
- `@docs/architecture/principles/stamps.md` — The 3+ stamp model. `pre_commit_cli_gate.py` is its enforcement point.
- `@docs/architecture/principles/context-awareness.md` — `statusline.py`, `context_budget.py`, `session_checkpoint.py` work together to keep sessions under the dynamic hard cut.

## Shared module discipline

- `_hook_shared.py` — single source of truth for validation step tuples, `compute_hard_cut()`, `read_hook_input()`, cache intervals, budget dictionaries. If you're about to hardcode a value that another hook will also need, it belongs here.
- `_session_state_common.py` — `write_session_state()`, `extract_from_transcript()`, memory dir resolver. Ported from the Modelling project pattern.
- `_os_safe.py` — Windows-first cross-platform safety. Mandatory for all disk writes.

## Naming

- `session_*.py` — SessionStart/SessionEnd handlers
- `pre_*.py` — PreToolUse handlers
- `post_*.py` — PostToolUse handlers
- `stop_*.py` — Stop handlers
- `subagent_*.py` — SubagentStart/SubagentStop handlers
- `_*.py` — shared modules (not hooks)
- Hooks on less common events use the descriptive event name: `instructions_loaded.py`, `permission_denied.py`, etc.

## Testing

Every hook gets a pytest test file in `hooks/tests/test_<name>.py`. Shared modules get `tests/test__<name>.py`. Tests assert:

1. Exit code for happy path
2. Exit code for the block path (exit 2 when invariants are violated)
3. Stdout/stderr content matches the contract
4. Side effects (file writes, stamp creation) use `_os_safe`

Run from the project root:

```
uv run pytest hooks/tests/
```

## Never do this

- Import from `lib/` (that's JavaScript; hooks are pure Python)
- Write to files outside `${CLAUDE_PROJECT_DIR}` without going through `_os_safe.safe_join`
- Print to stdout outside of the exit-2 block message (CC captures stdout as noise)
- Skip the hook input schema — every hook validates its input before acting
