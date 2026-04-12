# Maintain Phase

**"Keep the lights on. Dependencies, deprecations, flakes."**

The maintain phase handles long-term codebase health: dependency updates, deprecated API migration, and test reliability.

## Trigger

`/maintain` or scheduled.

## Flow

### Step 1: Dependency updates

`maintain-dependency-updater` (write/auto-fixer, sonnet, worktree isolation):

- Reads `uv.lock` / `package-lock.json` for pinned versions
- Checks for available updates against registries
- Applies updates **in a worktree** (isolated from the main branch)
- Runs the full test suite against the updated dependencies
- Reports breakages with root-cause analysis
- Produces a PR-ready diff if all tests pass

### Step 2: Deprecation scanning

`maintain-deprecation-scanner` (read/background, sonnet):

- Scans code for deprecated API usage (Python `DeprecationWarning`, TypeScript `@deprecated` JSDoc, language-specific patterns)
- Produces a migration plan: what to replace, with what, estimated effort
- Files are not modified — the output is a report

### Step 3: Flake detection

`maintain-flake-detector` (read/background, sonnet):

- Long-horizon flake analysis (different from `testing-flake-detector` which is CI-scoped and per-run)
- Tracks test results across sessions: which tests pass sometimes and fail others
- Reports with statistical confidence: "test_X has failed 3 of the last 20 runs (15% flake rate)"

### Step 4: Security audit

`security-dep-vuln-scanner` runs alongside (if Phase 2+ is live):

- Checks `uv.lock` and `package-lock.json` against CVE databases
- Reports vulnerabilities with severity, affected versions, available patches

## Exit

Dependency PRs ready for review, deprecation report generated, flake report updated, security audit clean (or flagged issues documented).

## Interactions

- **Consumes:** current codebase state (dependencies, code, test results)
- **Produces:** PRs (via worktree), reports (via project memory)
- **Triggers:** validate phase (updated dependencies must pass `/validate` before merge)
- **Background agents:** deprecation scanner and flake detector run asynchronously without blocking foreground work
