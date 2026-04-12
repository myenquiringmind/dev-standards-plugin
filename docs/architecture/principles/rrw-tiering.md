# Read / Reason / Write Tiering

An orthogonal dimension to the agent type taxonomy (blocking / auto-fixer / advisory / background). **R/R/W tiering isolates agent responsibilities by the kind of work they do.** It is declared in agent frontmatter and enforced by schema + hook-level gates.

## The three tiers

| Tier | Role | Tool allowlist (typical) | Tool blocklist (typical) | Isolation | Memory |
|---|---|---|---|---|---|
| **Read** | Scanner / profiler / extractor / inventorier — reads existing state exhaustively, emits a structured report against a known schema. No judgment beyond classification. | `Read`, `Glob`, `Grep`, `Bash` (read-only subprocess only) | `Edit`, `Write`, `NotebookEdit`, `WebFetch` | none | `project` (report cached) |
| **Reason** | Analyst / planner / gap-analyzer — consumes R-tier reports + a target state, produces a plan. High judgment, isolated context. | `Read`, `Bash` (read-only) | `Edit`, `Write`, `NotebookEdit`, `WebFetch` | none | `project` |
| **Write** | Applier / scaffolder / reviewer / auto-fixer — consumes plans (or reviews output), produces code/config/migration/verdict. | `Read`, `Edit`, `Write`, `Bash`, `Glob`, `Grep` | (none beyond defaults) | `worktree` (preferred for auto-fixers) | `project` |

Plus one sanctioned exception:

**`read-reason-write`** — for small pipeline agents where splitting would be over-engineering (e.g., `closed-loop-transcript-todo-extractor`). Requires explicit justification in the agent's description.

## Why tiering matters

1. **Context economy.** A reader runs once per session; its report feeds many downstream agents. Re-reading the database ten times across ten reviewers is ten times more expensive than reading once into a cached report.
2. **Cacheability.** R-tier outputs are facts with provenance (timestamp + watermark). Facts can be cached across sessions: `db-schema-report.json` is valid until a migration runs; all downstream agents read the cached report.
3. **Testability.** Structured reports can be validated against schemas. Plans can be validated against reports. This turns agent pipelines into assertable boundaries — "given this report, this plan is produced" is a testable property.
4. **Parallelism.** R-tier agents have no inter-dependencies; they fan out on a single worktree. Reason agents fan in. Writers fan out again. Sequential reviewer chains become DAGs.
5. **Failure isolation.** Columbia DAPLab's agentic failure modes (sycophancy, premature closure, false confidence) mostly originate in agents that conflate reading with reasoning. A read-tier agent that physically cannot write is immune to "I'm just going to quickly fix this" drift.

## Enforcement — three levels

### Level 1: Schema

`schemas/agent-frontmatter.schema.json` adds a `tier` field with conditional rules: `tier: read` or `tier: reason` requires `tools` to not contain `Edit`/`Write`/`NotebookEdit`. Schema-level declaration errors are caught at agent creation time.

### Level 2: Meta-agent

`meta-agent-arch-doc-reviewer` rejects any agent whose declared tier conflicts with its tools during the agent validation gate.

### Level 3: Runtime hook

`hooks/pre_tool_use_tier_enforcer.py` (Phase 2 addition) checks the active agent's tier against each tool invocation. A read-tier agent attempting `Edit` is blocked at the tool level, even if it somehow slipped past the schema.

This three-level defence is belt-and-braces: the schema catches declaration errors, the meta-agent catches propagation errors, the hook catches runtime mistakes.

## Bash is a sharp knife

Read-tier agents need `Bash` for subprocess queries (psql, curl, git log, find). But Bash allows arbitrary execution — a read-tier agent could technically call `rm -rf`. Mitigations:

- `hooks/dangerous_command_block.py` (bootstrap) catches destructive patterns globally
- `hooks/pre_bash_tier_guard.py` (Phase 2) adds a stricter allowlist when the active agent is `tier: read` or `tier: reason` — only `SELECT`-style SQL, `GET`-only HTTP, read-only filesystem commands. Violations exit 2.
- R-tier agents declare intent in their description; `meta-agent-arch-doc-reviewer` cross-checks that the description is consistent with read-only scope.

## Naming convention

Tier is reflected in the agent name suffix:

- Read tier: `-scanner`, `-profiler`, `-extractor`, `-inventorier`
- Reason tier: `-analyst`, `-planner`, `-gap-analyzer`, `-advisor` (for pattern advisors)
- Write tier: `-reviewer` (blocking), `-checker` (auto-fixer), `-scaffolder`, `-applier`

Example pipeline for brownfield database work:

1. `db-schema-scanner` (read) → outputs structured schema report
2. `db-migration-planner` (reason) → consumes schema report + target design → produces migration plan
3. `db-migration-applier` (write, worktree) → applies migration plan in worktree

## Retrofitting

All existing agents carry a `tier` field in frontmatter from Phase 5's Core Agent Refactor. Agents written before R/R/W was introduced are classified:

- Most reviewers → `write` (they produce verdicts, which are writes)
- Pattern advisors → `reason` (they're advisors, not mechanical checks)
- Auto-fixers → `write` (obvious)
- Scanners and profilers (new in Phase 3) → `read`
- Gap analysts, migration planners, architecture reconstructors → `reason`
