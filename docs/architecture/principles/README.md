# Architectural Principles

The ten load-bearing principles `dev-standards-plugin` is built on. Each file is ≤200 lines, scoped to a single concept, and loaded on demand via `@include` from CLAUDE.md files throughout the repo.

## The ten principles

| # | Principle | Purpose |
|---|---|---|
| 1 | [`psf.md`](./psf.md) | **Primitive Selection Framework** — the decision tree for where new logic lives: Rule → Hook → Agent → Skill → Command → MCP. Pick the leftmost primitive that can express the requirement. |
| 2 | [`memory-tiers.md`](./memory-tiers.md) | **Four-tier memory** — session / project / agent / framework. Who writes, who reads, what survives compaction. Critical rule: never cross-write. |
| 3 | [`rrw-tiering.md`](./rrw-tiering.md) | **Read / Reason / Write tiering** — agents specialize on a single tier. Tool allowlists mechanically enforce the split. Fan-out R-tier → fan-in Reason-tier → feed Write-tier. |
| 4 | [`stamps.md`](./stamps.md) | **3+ stamp validation gate model** — five independent stamps (code, frontend, agent, db, api) with 15-minute TTL, branch-specific, enforced by `pre_commit_cli_gate.py`. Only bypasses: `[WIP]` and `.git/MERGE_HEAD`. |
| 5 | [`bootstrap-first.md`](./bootstrap-first.md) | **Bootstrap-first sequencing** — the minimum ~46-file self-hosting lifecycle lands first. From Phase 2 onwards, the framework builds itself through its own gates. |
| 6 | [`dogfooding.md`](./dogfooding.md) | **Dogfooding** — every framework principle is applied to the framework itself. If a rule doesn't hold for the framework's own construction, the rule isn't real. Includes worked examples of past failures. |
| 7 | [`context-awareness.md`](./context-awareness.md) | **Context awareness** — never compact; guideline token budgets inform the session planner; one dynamic hard cut based on the active model's compaction threshold; rolling summarizer protects against lost-in-the-middle. |
| 8 | [`plugin-vs-project.md`](./plugin-vs-project.md) | **Plugin vs project duality** — the plugin ships skills (not rules) to user projects; the plugin's own repo has rules for dogfooded development. Two different contexts with different primitives. |
| 9 | [`documentation-as-code.md`](./documentation-as-code.md) | **Documentation as code** — every doc is ≤200 lines, enforced mechanically. Diataxis taxonomy. Composition via `@include`. The architecture itself obeys the framework's own rules. |
| 10 | [`security.md`](./security.md) | **Security** — public-plugin posture: opt-in telemetry by default, regex secret scanning in the bootstrap, gitignore audit, SECURITY.md policy. The plugin is exemplary because users will read the code. |

## Reading order for new contributors

If you are new to the project, read in this order (each file is a few minutes):

1. `dogfooding.md` — the meta-principle that ties everything together
2. `psf.md` — where things live
3. `bootstrap-first.md` — the sequencing principle
4. `stamps.md` — the mechanical enforcement model
5. `context-awareness.md` — why we care about sessions staying small
6. `rrw-tiering.md` — how agents are specialized
7. `memory-tiers.md` — how knowledge persists across sessions
8. `plugin-vs-project.md` — what ships to users vs what stays in the repo
9. `documentation-as-code.md` — why this folder looks the way it does
10. `security.md` — the public-plugin baseline

Most agents working in this repo will load 3-4 of these via `@include` automatically, not all ten. Reading all ten is for humans getting oriented.

## Adding a new principle

Adding a new principle is a **major architectural change**. It requires an ADR in `docs/decision-records/` explaining why the existing nine are insufficient. Do not add principles lightly — they are the framework's load-bearing concepts.
