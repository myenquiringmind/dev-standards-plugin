# Decision Records

This folder holds Architecture Decision Records (ADRs) and other historical decision documentation. Each ADR records **what was decided, when, why, and what the consequences are** for a single significant architectural choice.

## Structure

Each ADR is a standalone markdown file following the template:

```markdown
# ADR-NNN: <decision title>

**Status:** Accepted | Proposed | Deprecated | Superseded
**Date:** YYYY-MM-DD
**Deciders:** <names or "planning session">

## Context

What's the situation that forced this decision? What constraints are in play?

## Decision

What we decided, stated as a single clear position.

## Consequences

What becomes true, easier, harder, or different because of this decision?

## Alternatives considered

What other options were on the table and why they were rejected.

## References

Related ADRs, related principles, archived planning material.
```

## Numbering

- **ADR-001 through ADR-006** are the foundational decisions made during the v2 architecture planning session and documented in Phase 0. They are numbered in the order of importance to the architecture, not the order of discussion.
- Subsequent ADRs are numbered **ADR-007, ADR-008, ...** in the order they are recorded (chronological going forward).
- Numbers are never reused. Superseding ADRs get a new number and mark the old one as superseded.

## The six foundational ADRs

| # | Title | Subject |
|---|---|---|
| [001](./adr-001-graph-first-architecture.md) | Graph-first architecture | Every component is a node; every relationship is a typed edge. The graph registry is a derived artifact. |
| [002](./adr-002-strict-default.md) | Strict default enforcement | The stamp gate blocks on every step it declares blocking. `[WIP]` and `.git/MERGE_HEAD` are the only bypasses. |
| [003](./adr-003-bootstrap-first-sequencing.md) | Bootstrap-first sequencing | Phase 1 delivers the minimum viable self-hosting lifecycle; every subsequent phase dogfoods through it. |
| [004](./adr-004-read-reason-write-tiering.md) | Read / Reason / Write tiering | Agents specialize by tier, enforced mechanically via `tools` / `disallowedTools` / schema conditionals. |
| [005](./adr-005-documentation-as-code.md) | Documentation as code | All runtime docs ≤200 lines, enforced by hook. Diataxis taxonomy. Composition via `@include`. |
| [006](./adr-006-context-awareness-absolute-budgets.md) | Context awareness with absolute budgets | One hard constraint (never compact, dynamic cut). Everything else is guidelines. LITM defence via rolling summarizer + session planner. |

## The archived canonical plan

`v2-architecture-planning-session.md` is the full planning session that produced this architecture — approximately 3300 lines including all amendments (Appendices A through H). It is:

- **A decision record.** It captures what was considered, what was decided, and why, in chronological order.
- **Exempt from the ≤200-line documentation size limit.** It's a historical artifact, not runtime context.
- **Not loaded at runtime by working agents.** It's for humans (and future planning sessions) looking at the history, not for agents doing work.
- **Git-tracked.** Unlike the original in the user's plan directory, this copy is version-controlled and cannot be lost.

## Writing a new ADR

When you make a significant architectural decision:

1. Pick the next unused ADR number
2. Copy the template above
3. Fill in Context, Decision, Consequences, Alternatives
4. Add a link from the table above
5. Commit on a feature branch, validated through the framework's own gate (from Phase 1 exit onwards)

If you're replacing an existing decision, the new ADR supersedes the old one. Mark the old ADR's status as `Superseded by ADR-NNN` and reference the new one.

## What counts as a "significant" decision

- Adding or removing an architectural principle
- Changing the scope contract of the bootstrap
- Adding or removing a category of agent, hook, or command
- Changing the sequencing of phases
- Changing the primitives shipped by the plugin vs kept internal
- Changing security posture or default configuration

Minor implementation choices (e.g., "use portalocker over fasteners for file locking") do not need an ADR unless the choice is load-bearing.
