# Phase 4 — Telemetry + Memory Infrastructure

**Duration:** 2 weeks (canonical estimate; actual cadence follows Phase 3's small-PR rhythm).
**Prerequisite:** Phase 3 exit. `bootstrap_smoke` 28/28 on master; six R-tier scanners + three reason-tier analysts shipped; report-schema pattern established.
**Exit gate:** every Phase 4 deliverable below has its file (shared module / agent / schema / hook update), tests, and a structural assertion in `bootstrap_smoke`. `bootstrap_smoke` grows from 28 to ~33.

Phase 4 builds the **closed-loop observability foundation**: the framework writes its own telemetry, owns its own memory, and ships its first consumer of those records (the quality scorer). Without Phase 4, every Phase 5+ agent that wants to learn from prior runs has to invent its own storage; with Phase 4, there is a single canonical layout under `${CLAUDE_PLUGIN_DATA}/framework-memory/` and a single canonical contract for reading it.

The full closed-loop loop (retrospective analyst, knowledge compactor, MCP servers) is **out of scope for Phase 4** — those land in Phase 10. Phase 4 ships the substrate they need.

## Phase 4 pre-work (already shipped)

Landing ahead of formal Phase 4 kickoff:

- **`hooks/_telemetry.py`** (Phase 2, PR #49) — JSONL emitter with concurrent-write safety. Phase 4 ships the consumer.
- **`hooks/_incident.py`** (Phase 2, PR #50) — ULID-keyed incident writer. Phase 4 ships the structural read-side helper + schema.
- **`stop_failure.py` / `permission_denied.py`** (Phase 2, PRs #56, #61) — produce incident records. Phase 4 ships the schema that defines what those records contain.
- **`closed-loop-context-rolling-summarizer`** (Phase 1) — already shipped; pulled into bootstrap from the original Phase 4 plan. Not a Phase 4 deliverable.

## Scope contract — ~7 deliverables

### Memory infrastructure (2)

- **`hooks/_memory.py`** — shared module. Resolves `${CLAUDE_PLUGIN_DATA}/framework-memory/` paths via `_os_safe.safe_join`; provides `framework_memory_dir()`, `incident_dir()`, `telemetry_dir()`, `graph_history_dir()`, `quality_scores_path()` helpers. Mirrors `_session_state_common.get_memory_dir()` for the project/session tiers; new module covers the framework tier.
- **`session_start_framework_memory.py`** — SessionStart hook. Ensures the framework-memory directory tree exists (idempotent `mkdir -p`); creates a `.gitignore` inside the framework-memory root that excludes everything (the directory is local plugin state, never committed). Advisory exit 0; warns on stderr if the path is unwritable.

### Closed-loop quality scorer (2)

- **`agents/closed-loop/closed-loop-quality-scorer.md`** — background agent. `model: haiku`, `tier: write` (writes the scores file), `pack: codebase-scanners` (or new `closed-loop` pack — to be decided in stream 2 PR). Reads `framework-memory/telemetry/<agent>.jsonl`, aggregates per-agent precision (verdicts not overturned by user / total verdicts), recall (left for Phase 6+ when reviewer-coverage data lands), p95 latency, p95 cost, run-count. Writes `framework-memory/quality-scores.json`.
- **`schemas/reports/quality-scores.schema.json`** — output contract. Per-agent record with `precision`, `latency_ms_p95`, `cost_usd_p95`, `run_count`, `last_updated`. Aggregate summary at the top.

### Graph history (1)

- **Extend `hooks/file_changed.py`** — add `config/graph-registry.json` to the matcher set. On match, snapshot the file to `framework-memory/graph-history/<ISO-timestamp>.json` via `_os_safe.atomic_write`. Pruning (keep last N snapshots) deferred to Phase 10's `closed-loop-knowledge-compactor`.

### Schemas for cross-tool consumption (2)

- **`schemas/contracts/incident.schema.json`** — formal contract for incident records produced by `_incident.py` and consumed by Phase 10's retrospective analyst. Pins the shape that has been informal since Phase 2.
- **`schemas/contracts/telemetry-record.schema.json`** — formal contract for telemetry JSONL lines produced by `_telemetry.py` and consumed by `closed-loop-quality-scorer`. Same rationale.

These schemas live under `schemas/contracts/` (the path Phase 0 reserved for interface contracts; first real users land in Phase 4) — distinct from `schemas/reports/` which is for agent report outputs.

## Branches (parallel work, 4 streams)

1. `feat/phase-4-spec` — this document.
2. `feat/phase-4-memory-infrastructure` — `_memory.py` + `session_start_framework_memory.py`. Single PR; depends only on `_os_safe`.
3. `feat/phase-4-contract-schemas` — `incident.schema.json` + `telemetry-record.schema.json`. Single PR; independent of stream 2.
4. `feat/phase-4-graph-history` — extend `file_changed.py`; storage layout. Depends on stream 2 (uses `_memory.graph_history_dir()`).
5. `feat/phase-4-quality-scorer` — `closed-loop-quality-scorer.md` + `quality-scores.schema.json`. Depends on streams 2 (memory paths) and 3 (telemetry contract).

Each branch lands as a small PR per the established cadence. Streams 2 and 3 can run in parallel; 4 and 5 serialize after them.

## Phase 4 exit gate — extended smoke test

`scripts/bootstrap_smoke.py` grows from 28 to ~33 assertions:

- **`_memory.py` resolves the canonical paths** — `framework_memory_dir()` returns a `${CLAUDE_PLUGIN_DATA}`-rooted path; `safe_join` rejects traversal attempts.
- **`session_start_framework_memory.py` initializes the tree** — invoking the hook in a fixture creates `incidents/`, `telemetry/`, `graph-history/` subdirectories and the `.gitignore`.
- **Incident schema validates a `_incident.py`-produced record** — write a synthetic incident via the existing module, assert the JSON validates against `incident.schema.json`.
- **Telemetry schema validates a `_telemetry.py`-produced record** — same pattern.
- **`closed-loop-quality-scorer` agent file present** — frontmatter validates, `tier: write`, `model: haiku`. Plus `quality-scores.schema.json` self-validates and accepts a minimal positive example.

Full-suite targets: pytest still 100% green; `bootstrap_smoke` 33/33; ruff / mypy-strict clean. The full pytest invocation discipline (`uv run pytest`, not `uv run pytest hooks/tests/`) carries forward — the discipline gap surfaced in Phase 3's exit-gate PR is now durable in `feedback_full_pytest_for_footer.md`.

## What is explicitly NOT in Phase 4

Deferred to later phases. Rejected as scope creep if raised in Phase 4:

- **`closed-loop-incident-retrospective-analyst`** (#138) — Phase 10. Weekly opus-max agent that clusters incidents and proposes PRs.
- **`closed-loop-knowledge-compactor`** (#139) — Phase 10. Monthly sonnet agent that promotes patterns to principles.
- **MCP servers** (incident-log, telemetry-export, memory-search, graph-query) — Phase 10. Phase 4's consumers read files directly via Bash + Read.
- **`bin/dsp-telemetry`** — Phase 10. The CLI exporter for telemetry data.
- **Recall metric in quality-scorer** — depends on reviewer-coverage data that arrives Phase 6+ when stack reviewers land. Phase 4 ships precision-only; recall fields may exist in the schema but are populated `null` for now.
- **Per-phase context budget enforcement table from canonical plan §5.2** — already partially shipped via `context_budget.py` (Phase 1); the per-phase tables wait for Phase 5/7 when phase-aware commands land.
- **Selective rule loading** (`InstructionsLoaded`-driven scope/phase filtering) — canonical plan §5.4. Deferred to Phase 5/7.
- **Cross-project agent memory** beyond `write_agent_memory.py` (Phase 1) — already structurally in place; no new work.
- **Telemetry analysis dashboards / visualizations** — never in scope for the framework itself; users build their own with the JSONL exports.

## Phase 4 → Phase 5 handover

Phase 5 picks up the substrate Phase 4 produces and refactors the existing 13 agents into the new taxonomy with R/R/W tier consistency. The `validation-objective-verifier` and `validation-completion-verifier` already exist (Phase 1); Phase 5's job is to make every other agent comparably structured. Phase 4's `closed-loop-quality-scorer` will then have data to score against from day one of Phase 5.

## References

- Canonical plan archive — `docs/decision-records/v2-architecture-planning-session.md` §§ 5 (Memory tiers), 6 (Closed-loop architecture), A.20 (Closed-loop agents 138-141)
- Phase 2 exit report — `docs/phases/phase-2-exit-report.md` (telemetry + incident emit shipped)
- Phase 3 exit report — `docs/phases/phase-3-exit-report.md` (scanner pipeline shipped)
- `_telemetry.py` (emit side) — Phase 2 deliverable
- `_incident.py` (emit side) — Phase 2 deliverable
- `closed-loop-context-rolling-summarizer.md` — Phase 1 deliverable (closed-loop agent already shipped)
- Memory tier model — canonical plan §5.1 (the four tiers: session / project / agent / framework)
- Tier model — `docs/architecture/principles/rrw-tiering.md`
- Validation discipline — `feedback_full_pytest_for_footer.md`
