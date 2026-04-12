# ADR-003: Bootstrap-First Sequencing

**Status:** Accepted
**Date:** 2026-04-11
**Deciders:** Planning session (Appendix D amendment)

## Context

The original 11-phase roadmap sequenced work horizontally: all shared modules → all hooks → graph registry → all agents. First usable framework state landed at the end of Phase 6 (~13 weeks). Until then, the framework's own development had no validation gates, no stamps, no mechanical enforcement — every commit was ungated.

This was challenged during planning review: "we want to ensure that we have a deterministic development lifecycle that dogfoods our own principles. We should be developing and implementing the standards we build as we go."

## Decision

**Build the minimum viable self-hosting lifecycle first (Phase 1 Bootstrap Spike, ~46 files). From Phase 2 onwards, every commit to `dev-standards-plugin` passes through the framework's own gate.** First usable state at ~4 weeks instead of ~13.

The bootstrap implements ten interlocking mechanisms from the Modelling project (see `@docs/architecture/principles/bootstrap-first.md` for the full list). Nothing less is self-hosting; nothing more is required for the initial bootstrap.

Each subsequent phase is a vertical slice built *through* the bootstrap — in worktrees, on feature branches, validated by the framework's own agents and stamps. Retrospective data starts accumulating from the first dogfooded commit.

## Consequences

- **Phase 1 is the most important phase.** It must be right — a buggy bootstrap cascades to every subsequent phase. The 13-assertion exit gate (`bootstrap-smoke.py`) is the objective test.
- **Pre-bootstrap commits (Phase 0 and early Phase 1) are exempt.** The gate doesn't exist yet. These are recorded in the incident log as historical once the gate goes live.
- **Worktree discipline** applies from Phase 2: one branch per functional element, parallel worktrees under `dsp-worktrees/`, each closing as a stamped, validated unit of work.
- **The bootstrap scope is a locked contract.** Adding to the bootstrap requires Phase 0 re-scope, not Phase 1 slip.

## Alternatives considered

- **Horizontal sequencing** (original plan): build all infrastructure → all agents → all commands → validate at the end. Rejected: first usable state at 13 weeks; no dogfooding until then; no retrospective data; framework can't enforce its own rules on its own construction.
- **Partial bootstrap** (only hooks, no agents): rejected because without `validation-objective-verifier`, commits could drift from objectives silently. The minimum bootstrap needs both hooks (mechanical enforcement) and agents (judgment enforcement).

## References

- Canonical plan Appendix D (Bootstrap-First Sequencing + Worktree Discipline)
- `@docs/architecture/principles/bootstrap-first.md` — the ten mechanisms
- `@docs/phases/phase-1-bootstrap.md` — the contract
