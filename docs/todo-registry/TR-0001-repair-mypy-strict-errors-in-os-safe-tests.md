# TR-0001: Repair mypy --strict errors in `hooks/tests/test__os_safe.py`

- **Discovered:** 2026-04-14, commit `2de260e` (B3 validation sweep — `mypy --strict hooks/` surfaced pre-existing errors from commit `94449c0` / B1)
- **Tier:** 2 (scope-adjacent, same-session sidecar — type-only fixes in a test file)
- **Description:** Three errors in `hooks/tests/test__os_safe.py`:
  - `L102`: `fh.write("world")` — `locked_open` yields `IO[str] | IO[bytes]`; mypy couldn't narrow to `IO[str]` even though the test opened in text mode.
  - `L118`: `fh.write(label)` — same root cause as L102.
  - `L176`: `os.replace = real_replace  # type: ignore[assignment]` — the ignore was flagged as unused by current mypy (the assignment type-checks because we're restoring a compatible function).
- **Remediation plan:** In each `locked_open` call site, cast the yielded handle to `IO[str]` via `typing.cast`. Remove the unused `# type: ignore[assignment]` on L176 (the earlier L171 assignment keeps its ignore because `fake_replace` genuinely doesn't match `os.replace`'s signature). Land as a sidecar `fix(hooks):` commit on `feat/phase-0b-shared-modules` before the PR opens.
- **Blocks:** `feat/phase-0b-shared-modules` PR opening (per stewardship contract — branch must be mypy-clean at the module level, not just file level, before PR).
- **Status:** CLOSED by commit `cd58b86` on `feat/phase-0b-shared-modules` (2026-04-14).

## Resolution summary

The fix introduced `typing.cast("IO[str]", raw_fh)` at the two test call sites (inside `TestLockedOpen.test_read_write_cycle` and `TestLockedOpen.test_lock_blocks_concurrent_access`) and removed the L176 `type: ignore`. No runtime behavior changed. Full validation after the fix: ruff check ✅, ruff format ✅, mypy --strict (9/9 files) ✅, pytest 87/87 ✅.

## Why this is a permanent entry

Closed entries are retained as an audit trail of the Competence Ratchet in action — this is the first entry, and it documents both the failure mode (B3 initially deferred the errors, then the user rejected that frame) and the corrective behavior (in-session sidecar fix before PR). Future agents reading the registry see how the principle is applied in practice.
