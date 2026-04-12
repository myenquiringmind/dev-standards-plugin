# Discover Phase

**"I have a problem. What am I actually solving? What exists already?"**

The discover phase is the entry point for new work. It elicits requirements, maps stakeholders, and — critically for brownfield projects — **scans existing state** before any design or development begins.

## Trigger

`/discover <problem statement>` or `/scan [target]` (facts only, no analysis).

## Flow

### Step 1: Classify project state

`discover-project-state-classifier` (read-reason, sonnet) examines the repo:

- Commit history depth, LOC count, module count
- Production markers (deployment configs, release tags, migrations)
- Running database, deployed API, shipped frontend

Emits one of: **greenfield** (empty/stub), **growing-green** (code but no production state), **brownfield** (production code with state and consumers). Written to `.claude/discover/project-state.json`.

### Step 2: Branch on state

**Greenfield** → skip scanners, go to requirements interview.

**Growing-green** → run `codebase-inventory-scanner` only, then requirements interview.

**Brownfield** → run the full R-tier scanner pipeline (step 3).

### Step 3: R-tier scanner fan-out (brownfield only)

All scanners run in parallel (background, worktree-safe):

| Scanner | Tier | What it reads |
|---|---|---|
| `codebase-inventory-scanner` | read | Filesystem → modules, entry points, test layout, LOC per dir |
| `codebase-dependency-grapher` | read | Imports → module-to-module DAG, cycle detection |
| `codebase-dead-code-detector` | read (BG) | Unreachable functions, unused exports, orphan files |
| `codebase-convention-profiler` | read | Actual naming/structure conventions from existing code |
| `db-schema-scanner` | read | Live DB or migration history → tables, columns, indexes, FKs, sizes |
| `db-data-profiler` | read (BG) | Sampled data → cardinality, nullability, distribution |
| `db-existing-query-extractor` | read | Code → SQL/ORM usage map ("where each table is accessed") |
| `api-contract-extractor` | read | Route handlers → reverse-engineered OpenAPI spec |
| `api-usage-profiler` | read (BG) | Access logs/traces → endpoint call frequency, error rates |

All outputs written to `.claude/discover/<scanner-name>.json`, content-addressed by `(source_commit, scanner_version)` for cache reuse.

### Step 4: Reason-tier fan-in

| Agent | Tier | Consumes | Produces |
|---|---|---|---|
| `codebase-architecture-reconstructor` | reason | inventory + dependency-graph + convention-profile | Latent architecture diagram (Mermaid) + discrepancy report |
| `db-migration-planner` | reason | schema report + target schema | Alembic/Flyway plan with reversibility analysis (deferred until `/design` identifies target) |
| `api-breaking-change-analyzer` | reason | extracted contract + proposed change | Blast-radius report (deferred until `/design` identifies target) |

### Step 5: Requirements + stakeholders (parallel to steps 3-4)

- `discover-requirements-elicitor` — structured interview: who, what, why, success criteria
- `discover-stakeholder-mapper` — identifies parties, concerns, objections

### Step 6: Gap analysis (final fan-in)

`design-gap-analyst` (reason, opus max) consumes **all** R-tier reports + stated requirements → prioritised gap report at `.claude/discover/gap-report.md`.

## Exit

A structured `.claude/discover/` directory containing: project state classification, all applicable scanner reports, gap analysis, stakeholder/requirements documents. **No code has been touched.** The design phase starts with full factual context.

## Interactions

- **Feeds into:** Design phase (brainstormer, architecture-reviewer, schema-designer all read the discover outputs)
- **Gated by:** `meta-session-planner` (sizes the discover work against session budget)
- **Produces for:** project memory tier (scanner reports cached for future sessions)
