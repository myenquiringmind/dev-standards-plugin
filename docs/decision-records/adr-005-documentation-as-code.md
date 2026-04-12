# ADR-005: Documentation as Code

**Status:** Accepted
**Date:** 2026-04-11
**Deciders:** Planning session (Appendix G amendment)

## Context

During Phase 0, the architecture plan was written as a single 3300-line file in the user's Claude Code plan directory, referenced by a 120-line `docs/architecture/README.md` as "the canonical plan." An agent asking "what does the stamp model say?" would have loaded the entire 3300-line file — roughly 25-30K tokens, consuming 25-50% of the smaller per-phase context budgets.

The user challenged: "If the README.md is the only canonical plan for the architecture. This is absolute craziness. This means that we need to load the entire document into context for EVERY agent."

A re-read of Claude Code's official documentation confirmed:
- CLAUDE.md files should be <200 lines (official best practice)
- Skill files should be <500 lines
- Plugins ship skills, not rules or CLAUDE.md
- Post-compaction, skills share a 25K token budget (5K per skill)
- CLAUDE.md survives compaction fully (most durable primitive)

## Decision

**All runtime documentation files are ≤200 lines, enforced mechanically by `hooks/post_edit_doc_size.py`.** Documentation follows the Diataxis taxonomy: explanation (principles), reference (components), how-to (guides), and tutorials (deferred). Composition uses Claude Code's `@path` include mechanism for lazy loading.

The canonical plan file is archived at `docs/decision-records/v2-architecture-planning-session.md` — git-tracked, preserved, but **never loaded at runtime** by working agents. Runtime references use `docs/architecture/principles/*.md` via `@include` from CLAUDE.md files.

## Consequences

- **Phase 0 went from 6 files to ~43 files.** Each is <200 lines. Total prose volume is comparable but **maximum context load for any single agent is dramatically smaller** — typically ~800 lines instead of 3300.
- **The hook `post_edit_doc_size.py`** (Phase 1 bootstrap) mechanically blocks markdown files >200 lines. No "just this once."
- **Generated documentation** (component catalogs, lifecycle walkthroughs) is produced by `doc-*` agents from the source of truth, not hand-written. Hand-editing generated files is an anti-pattern.
- **The Diataxis taxonomy** organises docs by user intent, not by implementation order — making it navigable by both humans and agents.
- **Plugin-vs-project duality** is explicit: the plugin ships skills to users (not rules or CLAUDE.md); the plugin's own repo has rules and CLAUDE.md for dogfooded development.

## Alternatives considered

- **Keep the monolithic plan as the canonical reference.** Rejected: violates four of the plan's own principles; agents can't efficiently consume it; it's a context bomb.
- **Split into medium-sized files (~500 lines each).** Rejected: still too large for <200-line best practice; still requires agents to load more than they need.
- **Don't enforce mechanically; rely on convention.** Rejected: the dogfooding principle demands mechanical enforcement. Without the hook, we drift.

## References

- Canonical plan Appendix G (Documentation-As-Code + Context-Aware Loading)
- `@docs/architecture/principles/documentation-as-code.md` — the detailed principle
- `@docs/architecture/principles/dogfooding.md` §"Worked example" — the failure that motivated this ADR
