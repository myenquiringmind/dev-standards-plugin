# Phase 4 — Exit Report

Phase 4 built the framework's **closed-loop observability substrate**: a single canonical memory tier under `${CLAUDE_PLUGIN_DATA}/framework-memory/`, formal contracts for the records that already flowed through it, graph-registry history snapshots, and the first consumer of any of it — `closed-loop-quality-scorer`. Where Phase 2 shipped the *emit* side (`_telemetry.py`, `_incident.py`) and Phase 3 shipped structured scanner outputs, Phase 4 unified storage and shipped the *read* side. `bootstrap_smoke` grew from 28 → 33 assertions. Every Phase 5+ agent that wants to learn from prior runs now has a single layout to read and a single contract to validate against, instead of inventing its own.

## What shipped

| Group | Deliverables | PRs |
|---|---|---|
| Phase 4 spec | `docs/phases/phase-4-telemetry-and-memory.md` | #91 |
| Stream 1 — Memory infrastructure | `hooks/_memory.py` (canonical path resolvers) + `session_start_framework_memory.py` (idempotent tree init + defensive `.gitignore`) | #92 |
| Stream 2 — Contract schemas | `schemas/contracts/incident.schema.json` + `telemetry-record.schema.json`; round-trip tests pinning `_incident`/`_telemetry` output | #93 |
| Stream 3 — Graph history | `file_changed.py` extended to snapshot `config/graph-registry.json` to `framework-memory/graph-history/<ISO>.json` | #94 |
| Stream 5 — Quality scorer | `agents/closed-loop/closed-loop-quality-scorer.md` (haiku, write-tier, background) + `schemas/reports/quality-scores.schema.json` + schema tests | #98 |
| Exit gate | `bootstrap_smoke` 28 → 33 assertions; this report | this PR |

Five PRs landed across the phase (#91–#94, #98, with this PR closing). All ~7 spec deliverables landed. The pre-work modules the spec relied on (`_telemetry.py`, `_incident.py`, `stop_failure.py`, `permission_denied.py`, `closed-loop-context-rolling-summarizer`) had already shipped in Phases 1–2; Phase 4 added their schemas and first consumer.

## Mechanical gate results

`scripts/bootstrap_smoke.py` final run, against master at the merge of this PR:

```
[bootstrap-smoke] 28/33 [PASS] phase-3-analyst-schemas - 3 schemas
[bootstrap-smoke] 29/33 [PASS] phase-4-memory-paths
[bootstrap-smoke] 30/33 [PASS] phase-4-framework-memory-init
[bootstrap-smoke] 31/33 [PASS] phase-4-incident-schema
[bootstrap-smoke] 32/33 [PASS] phase-4-telemetry-schema
[bootstrap-smoke] 33/33 [PASS] phase-4-quality-scorer - 1 schemas
[bootstrap-smoke] 33/33 passed - Phase 1+2+3+4 exit gate OK
```

Exit gate: **33/33**. Full Python test suite at exit: **908/908**. ruff, ruff-format, mypy-strict, pytest all clean.

The five Phase 4 assertions map one-to-one onto the spec's exit-gate bullets:

| # | Assertion | What it proves |
|---|---|---|
| 29 | `phase-4-memory-paths` | `framework_memory_dir()` roots under `$CLAUDE_PLUGIN_DATA`; `safe_join` rejects `../../etc/passwd` |
| 30 | `phase-4-framework-memory-init` | invoking `session_start_framework_memory` in a fixture creates `incidents/`, `telemetry/`, `graph-history/` + a `.gitignore` that excludes all |
| 31 | `phase-4-incident-schema` | a record from `_incident.write_incident` validates against `incident.schema.json` |
| 32 | `phase-4-telemetry-schema` | a record from `_telemetry.emit` validates against `telemetry-record.schema.json` |
| 33 | `phase-4-quality-scorer` | the agent file is present (`tier: write`, `model: haiku`) and `quality-scores.schema.json` self-validates + accepts a minimal empty-tree example |

**Note on structural checks.** Assertions 29–33 are exercised structurally and via in-process round-trips (path resolution, hook invocation, module-produced-record validation, file-presence + frontmatter + schema-meta-validation). Live invocation of the scorer against accumulated telemetry is out of scope for the smoke; that coverage arrives Phase 5 when the scorer has real run data to aggregate, and in `scripts/live_integration_smoke.py`.

## Design decisions recorded in-phase

| Decision | Why | PR |
|---|---|---|
| `closed-loop-quality-scorer` uses `pack: core`, not a new `closed-loop` pack | The two sibling closed-loop agents already use `core`; adding a `closed-loop` enum value would expand `agent-frontmatter.schema.json` plus the inactive-pack disable logic. The scorer is always-on framework infrastructure | #98 |
| `recall` field present but `null`-only in Phase 4 | Recall needs reviewer-coverage ground truth that lands Phase 6+. The field exists now so the schema is stable when that data arrives; the agent prompt and the schema both forbid populating it | #98 |
| `agents` map is sparse, not pre-seeded | An agent with no telemetry in the window is absent, not present with zeroes — `run_count` has `minimum: 1`. Keeps the file proportional to activity | #98 |
| Phase 4 exit gate split from stream 5 | `one objective, one commit` — the scorer agent/schema (#98) shipped first; this PR adds only the smoke assertions + report | this PR |

None of these widened the **exit gate** — the 33 assertions are exactly the five spec bullets appended to Phase 3's 28.

## Carry-forward to Phase 5+

### Deferred from Phase 4 (per spec, not regressions)

- **Recall metric** — depends on reviewer-coverage data; Phase 6+. Schema field is `null`-only until then.
- **`closed-loop-incident-retrospective-analyst`** (#138) and **`closed-loop-knowledge-compactor`** (#139) — Phase 10. Phase 4 reserved `principles/` and `retrospectives/` directory names so the layout is stable.
- **MCP servers** (incident-log, telemetry-export, memory-search, graph-query) and **`bin/dsp-telemetry`** — Phase 10. Phase 4 consumers read files directly via Bash + Read.
- **Graph-history pruning** — Phase 10's knowledge-compactor. Phase 4 snapshots unconditionally.

### Tier-3 still open

- **TR-0003** — memory-tier mismatch on read/reason agents. Unchanged by Phase 4; still awaits framework-owner clarification of `memory: project` semantics.
- **TR-0004 step 5** — principle-doc audit pass. Lower urgency; not touched in Phase 4.

### Lessons accreted to auto-memory (durable across sessions)

- **The telemetry consumer pattern is now established.** The scorer reads JSONL via `_memory.telemetry_dir()`, aggregates per-agent, validates against the schema before writing, and overwrites a single snapshot file. Phase 5+ analysts can template from it.
- **In the Bash tool, use a heredoc (`git commit -F - <<'EOF'`), not PowerShell `@'...'@`** — the latter leaks a literal `@` into the commit subject. Surfaced and amended during stream 5.

## Dogfooding summary

Every commit on master from here is subject to Phase 1–3 enforcement plus Phase 4's structural checks: every framework-memory path resolves through `safe_join`; every incident and telemetry record must validate against its pinned contract; the quality-scorer agent must keep valid frontmatter and a self-validating output schema. The 33-assertion smoke still runs under a minute.

Phase 4's value proposition — *the framework writes its own telemetry, owns its own memory, and ships its first consumer of those records* — is realised. Phase 5 picks up the substrate to refactor the existing 13 agents into the R/R/W taxonomy; the quality-scorer will have data to score against from day one.
