# Phase 3 — Language Profiles + State Inventory Scanners

**Duration:** 2 weeks (canonical estimate; actual cadence follows Phase 2's small-PR rhythm).
**Prerequisite:** Phase 2 exit. `bootstrap_smoke` 21/21 on master; tier-aware hooks live; `_graph` shared module shipped.
**Exit gate:** every scanner and analyst in scope below has an agent file with valid frontmatter, a report schema under `schemas/reports/`, a structural assertion in `bootstrap_smoke`, and the new language profiles validate against `schemas/profile.schema.json`. `bootstrap_smoke` grows from 21 to ~28 assertions.

Phase 3 fills the framework's biggest greenfield bias: **R-tier scanners and reason-tier analysts** that read the existing system as fact and feed structured reports into downstream Design / Reviewer agents. Without these, every reviewer silently re-reads the target state from scratch — expensive in tokens, inconsistent across reviewers, and unable to handle "the running system *is* the specification" (Appendix F of the canonical plan).

## Phase 3 pre-work (already shipped)

- **`discover-project-state-classifier`** (Phase 1, PR #36) — classifies the project as greenfield / growing-green / brownfield. Phase 3 scanners only fire on brownfield.
- **R/R/W tier enforcement** (Phase 2) — `pre_tool_use_tier_enforcer` and `pre_bash_tier_guard` now block read-tier agents from mutating, so Phase 3 scanners can declare `tier: read` and trust the rails.
- **`_graph` shared module** (Phase 2, PR #51) — graph-registry traversal that scanner agents will use to declare cache-validity edges.

## Scope contract — ~14 deliverables

### Language profiles (3 + placeholders)

- `config/profiles/typescript.json` — first-class TypeScript profile (P0). Uses tsc-strict + eslint + vitest, matches the existing `javascript.json` shape.
- `config/profiles/fullstack.json` — composite profile for monorepo projects with both Python + TypeScript. Detection markers cover both stacks.
- Placeholder profiles for `go`, `rust` at priority `P2` — detection markers + pinned validation steps, but tools may be `null`/empty until later phases. Keeps the profile catalog discoverable without forcing full implementations.

### R-tier scanners (6 agents)

**Codebase (4):**

- `codebase-inventory-scanner` — file enumeration, language detection cross-check, LOC counts, module structure. Produces `codebase-inventory.json`.
- `codebase-dependency-grapher` — language-specific import parsing → directed graph of internal modules + external deps. Produces `dependency-graph.json`.
- `codebase-dead-code-detector` — language-specific reachability scan. Produces `dead-code.json`.
- `codebase-convention-profiler` — naming patterns, indent/quote conventions, formatting deviations against the active language profile. Produces `convention-profile.json`.

**Database (1):**

- `db-schema-scanner` — read-only DB introspection (psql `\d`, mongosh `getCollectionInfos`, etc.). Produces `db-schema.json`. Requires live DB access; classifier-gated to brownfield with a `database` marker.

**API (1):**

- `api-contract-extractor` — OpenAPI / tRPC / GraphQL schema discovery from source. Produces `api-contract.json`.

### Reason-tier analysts (3 agents)

- `codebase-architecture-reconstructor` — consumes the four codebase scanner reports + classifies layering, identifies missing tests, surfaces architectural anti-patterns. Output is a plan, not a verdict; downstream Design / Reviewer agents consume it.
- `db-migration-planner` (skeleton) — consumes `db-schema.json` + a target schema; produces a migration plan. Full execution-side support arrives in Phase 4 when migration agents land.
- `api-breaking-change-analyzer` (skeleton) — consumes two `api-contract.json` snapshots; produces a breaking-change report. Full review-side support in Phase 6 when the API stack agents land.

### Report schemas (~6 new under `schemas/reports/`)

One JSON Schema per scanner output. Each schema validates against the meta-schema, has positive + negative test examples in `bootstrap_smoke`, and references a stable `$id`.

## Branches (parallel work, 5 streams)

1. `feat/phase-3-language-profiles` — `typescript.json`, `fullstack.json`, placeholders.
2. `feat/phase-3-codebase-scanners` — 4 scanner agents + 4 schemas.
3. `feat/phase-3-db-scanner` — `db-schema-scanner` + schema.
4. `feat/phase-3-api-scanner` — `api-contract-extractor` + schema.
5. `feat/phase-3-reason-analysts` — 3 analysts (depend on 2/3/4).

Each branch lands as small PRs, same cadence as Phase 1/2. Streams 2/3/4 can run in parallel after stream 1 lands; stream 5 waits on the scanner outputs it consumes.

## Phase 3 exit gate — extended smoke test

`scripts/bootstrap_smoke.py` grows from 21 to ~28 assertions:

- **Language profiles** — `typescript.json` and `fullstack.json` validate against `profile.schema.json`; markers do not collide with `python.json`.
- **Scanner agent files** — each new agent file has valid frontmatter with `tier: read` (codebase + db + api scanners) or `tier: reason` (analysts).
- **Report schemas** — each new schema has positive + negative test examples (`bootstrap_smoke` already does this for `transcript-todo-extraction.schema.json`; same pattern).
- **Tuple growth** — extending the existing tuple-growth assertion to confirm new agent names land in `AGENT_VALIDATION_STEPS` if they sit in the validation gate.

Full-suite targets: pytest still 100% green; `bootstrap_smoke` 28/28; ruff / mypy-strict clean.

`scripts/live_integration_smoke.py` (Phase 2) grows by one or two checks if any new scanner has a low-cost live invocation worth exercising; otherwise it stays at 3.

## What is explicitly NOT in Phase 3

Deferred to later phases. Rejected as scope creep if raised in Phase 3:

- **Stack-reviewer agents** (`py-*`, `fe-*`, `db-*`, `api-*` reviewers) — Phase 6.
- **Frontend-specific scanners** (bundle analyzers, accessibility scanners, browser-API usage profilers) — Phase 6.
- **Pattern / anti-pattern detectors** — Phase 8.
- **Telemetry analysis agents** (`closed-loop-quality-scorer`, `incident-retrospective-analyst`) — Phase 4.
- **Live MCP servers** for DB / API access — Phase 10. Phase 3's `db-schema-scanner` and `api-contract-extractor` use direct subprocess invocations (psql, curl) under the read-only tier guard.
- **Cwd-aware multi-stack detection** — Phase 3 may revisit `detect_language` to scan markers at the new cwd in monorepos. If it does, the change is tracked under the language-profiles branch; if it does not, it stays a Phase 4 carry-forward (already noted in `phase-2-exit-report.md`).

## Phase 3 → Phase 4 handover

Phase 4 picks up the structured reports the scanners produce and feeds them into the closed-loop infrastructure: telemetry, incident retrospective, quality scorer. Phase 3's exit state is what Phase 4 starts from — every scanner output schema is the contract Phase 4 consumes.

## References

- Canonical plan archive — `docs/decision-records/v2-architecture-planning-session.md` Appendix F (Read/Reason/Write Tiering + Brownfield Scanners)
- Tier model — `docs/architecture/principles/rrw-tiering.md`
- Scanner pipeline DAG — Appendix F.4 (the diagram)
- Phase 2 exit report — `docs/phases/phase-2-exit-report.md`
- Profile schema — `schemas/profile.schema.json`
