# ADR-004: Read / Reason / Write Tiering

**Status:** Accepted
**Date:** 2026-04-11
**Deciders:** Planning session (Appendix F amendment)

## Context

The original plan had agents that read, reasoned, and wrote verdicts in a single invocation. Most reviewers conflated scanning existing state with judging it. This works for greenfield review but fails for brownfield work — a reviewer cannot also perform discovery. It also means every reviewer independently re-reads the target state, burning context tokens N times across N agents for the same facts.

The concern was raised: "we will have different agentic roles that 'read' first, and 'reason' and 'write'... we need to ensure that our agents are assessing what exists thoroughly as a sub-agent, then the design agents can be better informed about the gap analysis."

## Decision

**Read / Reason / Write is an orthogonal dimension of agent specialization, declared in frontmatter (`tier` field) and enforced mechanically.** Every agent belongs to one of three tiers (plus one sanctioned exception for trivial pipelines):

- **Read**: scanners, profilers, extractors. No Edit/Write allowed. Emit structured reports against known schemas.
- **Reason**: analysts, planners, gap-analyzers. No Edit/Write. Consume R-tier reports + target state → produce plans.
- **Write**: scaffolders, reviewers, auto-fixers, appliers. Full tool access, typically worktree isolation.
- **Read-reason-write**: sanctioned exception only (e.g., `closed-loop-transcript-todo-extractor`). Requires justification.

Enforcement is three-level: schema conditional (declaration-time), `meta-agent-arch-doc-reviewer` (validation-time), `pre_tool_use_tier_enforcer.py` (runtime).

## Consequences

- **15 new brownfield scanner/analyst agents** added to the plan (codebase: 5, database: 4, API: 3, design: 1, discover: 1, closed-loop: 1). Total agents 141 → 156.
- **Context economy**: R-tier readers run once per session; reports are cached by `(source_commit, scanner_version)`. Multiple downstream agents read the same report.
- **Testable pipelines**: "given this report, this plan is produced" is an assertable property. Reports validate against schemas; plans validate against reports.
- **Parallelism**: R-tier agents fan out (no inter-dependencies); Reason tier fans in; Write tier fans out again. Sequential reviewer chains become DAGs.
- **Bash safety concern**: R-tier agents need Bash for subprocess queries but Bash allows arbitrary execution. Mitigated by `pre_bash_tier_guard.py` (Phase 2) with a read-only command allowlist.
- **Greenfield/brownfield classifier** (`discover-project-state-classifier`) branches the Discover phase based on project state: greenfield skips scanners; brownfield runs the full R-tier pipeline.

## Alternatives considered

- **No tiering; mixed-responsibility agents.** Status quo. Rejected: cannot compose agents into pipelines; every agent re-reads the target state independently; brownfield analysis is impossible without dedicated readers.
- **Two tiers (read + write) without reason.** Rejected: the reason tier's gap-analysis function (consuming multiple R-tier reports → plan) is distinct enough to warrant its own specialization and tool constraints.
- **Tiering as convention only (no enforcement).** Rejected: without schema + hook enforcement, a "read" agent that declares Edit in its tools would compile fine and drift silently.

## References

- Canonical plan Appendix F (Read/Reason/Write Tiering + Brownfield Scanners)
- `@docs/architecture/principles/rrw-tiering.md` — the detailed principle
- `schemas/agent-frontmatter.schema.json` — the `tier` field and conditional rules
