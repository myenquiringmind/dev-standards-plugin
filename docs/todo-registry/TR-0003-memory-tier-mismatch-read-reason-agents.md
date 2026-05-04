# TR-0003: memory-tier-mismatch on read/reason-tier agents using memory: project

- **Discovered:** 2026-05-04, commit 02b585e (surfaced during /validate of feat/phase-3-db-migration-planner)
- **Tier:** 3 (non-trivial, cross-cutting — affects 7+ merged agents; requires semantic clarification before mass-fix)
- **Description:** `meta-agent-arch-doc-reviewer` rule states that `memory: project` with `tier: reason` or `tier: read` is a `memory-tier-mismatch` — because read-only agents cannot write their own memory and should persist learnings via `hooks/write_agent_memory.py` instead. However, seven agents already merged to master carry this pattern: `codebase-inventory-scanner`, `codebase-dependency-grapher`, `codebase-dead-code-detector`, `codebase-convention-profiler`, `codebase-architecture-reconstructor`, `api-contract-extractor`, and (newly) `db-migration-planner`. The pattern was not flagged during PR #87's validation (bootstrap_smoke / pytest / schema gates; the agent-arch-doc-reviewer runs at /validate time, not in the PR CI stack). In the Claude Code plugin context, `memory: project` may mean "inject project memory on startup (read)" rather than "this agent writes memory" — if so, the `meta-agent-arch-doc-reviewer` rule is overconstrained and needs refinement before the mass-fix.
- **Remediation plan:**
  1. Clarify with the framework owner whether `memory: project` on a read/reason tier agent is legitimate (read-inject semantics) or forbidden (write-access semantics).
  2. If forbidden: update all 7+ affected agents to `memory: none` in a dedicated sidecar commit or PR. Update `meta-agent-arch-doc-reviewer` rule to document the rationale.
  3. If permitted (read-inject is the intent): update `meta-agent-arch-doc-reviewer` to narrow the `memory-tier-mismatch` rule to only fire when the agent body contains a `write_agent_memory` Bash call without a matching `isolation: worktree`. Document the distinction.
  4. Add a test in `tests/` or a schema-level conditional to enforce whichever interpretation is canonical.
- **Blocks:** none (advisory — the affected agents are functional; this is a schema-rule consistency gap)
- **Status:** OPEN
