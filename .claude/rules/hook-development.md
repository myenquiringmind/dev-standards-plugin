# Hook Development

Conventions for writing Python hooks in this framework. Read `hooks/CLAUDE.md` for the full reference — this rule covers the non-negotiable constraints.

## Exit codes are the contract

- `0` — success (hook passes, tool use proceeds)
- `2` — block (invariant violated, tool use is rejected)
- Any other non-zero — non-blocking error (logged, tool use proceeds)

Exit 2 is how hooks enforce rules. If your hook detects a violation, `sys.exit(2)`. Never print a warning and exit 0 when the invariant is broken.

## Use `_os_safe` for all file I/O

Never `open(path, "w")` directly. Use:
- `_os_safe.atomic_write()` for writing files
- `_os_safe.locked_open()` for read-modify-write cycles
- `_os_safe.safe_join()` for constructing paths (prevents traversal)
- `_os_safe.temp_file()` / `_os_safe.temp_directory()` for temporary files

On Windows, `os.replace()` fails on locked files and transiently under antivirus contention. `_os_safe` handles both via sidecar lock files and retry-with-backoff. Don't reimplement these patterns.

## Read stdin as JSON

Hook input arrives as JSON on stdin. Use `_hook_shared.read_hook_input()` to parse it. Never parse manually. The function handles malformed input and returns a typed dict.

## One hook per file

A hook that does X and also Y is two hooks. Keep each file focused on a single lifecycle event and a single concern. The hook filename should match the concern: `branch_protection.py`, `pre_write_secret_scan.py`.

## Timeout budgets

Claude Code kills hooks that exceed their timeout. Stay within:
- Pre-tool hooks: <3 seconds
- Post-tool hooks: <10 seconds
- Session hooks: <15 seconds

If your hook needs to run an external tool (ruff, mypy), that's a post-tool hook with up to 10 seconds. If the tool might be slow, consider whether the hook should be advisory (exit 0 with message) rather than blocking (exit 2).

## Module docstring declares event and matcher

Every hook file starts with a module docstring that includes the CC event and matcher:

```python
"""Branch protection — block edits on protected branches.

Event: PreToolUse
Matcher: Edit|Write
"""
```

The graph registry validator reads these docstrings. Missing or incorrect event/matcher declarations are a build error from Phase 2 onwards.

## Never network

Hooks are local. No HTTP requests, no API calls, no DNS lookups. If you need external data, the hook reads a cached file that an MCP server or CLI tool populated earlier.

## Testing

Every hook gets `hooks/tests/test_<name>.py`. Shared modules get `hooks/tests/test__<name>.py`. Tests assert:
1. Exit 0 for the happy path
2. Exit 2 for the block path
3. Stdout/stderr content matches the contract
4. File writes use `_os_safe` (no raw `open()` in the call chain)
