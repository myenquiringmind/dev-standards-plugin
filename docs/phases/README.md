# Implementation Phases

The 11-phase implementation roadmap for `dev-standards-plugin` v2. Each phase is a discrete unit of work with its own exit gate. Phases do not run in parallel — each one validates the output of the previous.

## The 11 phases

| # | Phase | Duration | Exit state |
|---|---|---|---|
| 0 | [Architecture Lockdown](./phase-0-architecture-lockdown.md) | 1 wk | Schemas + principles + Diataxis docs + SECURITY.md committed; foundations in place for Phase 1 to start |
| 0b | [Bootstrap-the-Bootstrap](./phase-0b-exit-report.md) | (landed) | Rules + 3 shared modules + 2 language profiles + 12 Python hooks + `hooks.json` shim; framework dogfoods its own rules and hooks at the mechanical level |
| 1 | [Bootstrap Spike](./phase-1-exit-report.md) | (landed) | 22 PRs; 10 core agents, 3 v2 commands, 17 hooks, `build_graph_registry.py`, `bootstrap_smoke.py` 13/13 passing; framework validates its own commits. Live integration pending CC reload |
| 2 | Hook Completion | 2 wks | Remaining 25 hooks beyond the bootstrap 17 |
| 3 | Language Profiles + State Inventory Scanners | 2 wks | `typescript.json`, `fullstack.json`, placeholder profiles; brownfield scanner pipeline (codebase/database/api scanners + reason-tier analysts) |
| 4 | Telemetry + Memory Infrastructure | 2 wks | 4-tier memory live, incident log, telemetry emit/consume, `closed-loop-quality-scorer`, graph history |
| 5 | Core Agent Refactor | 2 wks | 13 existing agents refactored into the new taxonomy with R/R/W tier; validation-objective-verifier and validation-completion-verifier operational |
| 6 | TDD Workflow + Stack Agents | 3 wks | `/scaffold`, `/tdd`, `/fix`, `/debug`, `/typecheck` commands; Python stack (9) + Frontend stack (7) + Interface (3) + Database (3) agents; 3-stamp model fully operational |
| 7 | Design + Discover + Research | 2 wks | Design (5), Discover (3), Research (2) agents; `/design`, `/plan`, `/discover`, `/research` commands |
| 8 | Patterns + Anti-patterns + Refactoring | 3 wks | 54 pattern advisors + 8 anti-pattern detectors + 3 refactor agents; `/pattern`, `/refactor`, `/pattern-scan` commands |
| 9 | Security + Testing + Documentation | 2 wks | Security (6) + testing (6) + document (4) agents; `/document`, `/security-scan` commands; `doc-*` agents populate `docs/architecture/lifecycle/` and `docs/architecture/components/` |
| 10 | Operate + Maintain + Closed Loop + MCP | 3 wks | Operate (3) + maintain (3) + closed-loop (4) agents; 4 bundled MCP servers; 4 `bin/` tools; retrospective analyst live |
| 11 | Polish + Self-Serve | 1 wk | Additional language profiles activated; `interop-contract-reviewer`; public GitHub repo with install instructions; no marketplace or CLA (self-serve only) |

**Total: ~26 weeks.** First usable framework state: end of Phase 1 (~4 weeks).

## Phase exit discipline

Every phase has an exit gate — a specific, testable set of conditions. No phase exits until its gate passes. Gates are enforced mechanically where possible (smoke tests, validator agents, schema checks) and verified manually where they aren't (e.g., "the PR is reviewed and merged").

Phase 0's exit gate is the schema self-validation + doc size + PR merge to master.

Phase 1's exit gate is `scripts/bootstrap-smoke.py` passing all 13 assertions — see `phase-1-bootstrap.md`.

## Phase dependencies

Phases are largely sequential, with exceptions:

- Phases 0 → 1 → 2 → 3 → 4 → 5 → 6 are strictly sequential (each builds infrastructure the next phase requires)
- Phases 7 / 8 / 9 can overlap once Phase 6 is complete (they add parallel agent categories)
- Phases 10 / 11 are sequential on Phase 9

Within each phase, work is parallelized via git worktrees under `C:\Users\jmarks01\Projects\dsp-worktrees\` (from Phase 2 onwards). Each functional element is its own feature branch.

## Why this is in reference

The phase files in this folder are **reference documentation** — they specify what each phase delivers, its exit conditions, and its dependencies. They are not explanation (that's `docs/architecture/principles/`) and not how-to (that's `docs/guides/`).

## Phase 0 and Phase 1 are the only phases written in detail

At Phase 0, only Phase 0 and Phase 1 have full specs. Phases 2-11 are summarized in the table above and expanded in the canonical plan archive (`docs/decision-records/v2-architecture-planning-session.md`). Each phase's detailed spec is written when that phase is imminent — one week before Phase N begins, Phase N's spec is authored.

This follows the same principle as `docs/architecture/lifecycle/`: hand-writing stubs for phases months away risks drift from the actual work.
