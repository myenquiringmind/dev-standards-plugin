# Phase 5 — Core Agent Refactor

**Duration:** 2 weeks (canonical estimate; actual cadence follows the established small-PR rhythm).
**Prerequisite:** Phase 4 exit. `bootstrap_smoke` 33/33 on master; framework-memory tier + telemetry consumer shipped.
**Exit gate:** all 13 legacy v1 agents are retrofitted into the v2 taxonomy (frontmatter + `tier` + AgentVerdict body), discovered by `build_graph_registry`, and pass `meta-agent-arch-doc-reviewer`. `bootstrap_smoke` grows 33 → ~37; `live_integration_smoke` gains one live verdict check.

Phase 5 pays down the framework's oldest debt: thirteen v1 agents (`agents/*.md` at the flat root) are pure prompt files with **no frontmatter at all** — `build_graph_registry` silently skips them, no hook governs them, no tier constrains them. Phase 5 brings every one into the v2 taxonomy so the framework's own agent population is as disciplined as the agents it generates.

These 13 do **not** map 1:1 to the v2 catalog — their concerns decompose across the Phase 6–10 stack/testing/doc/pattern populations (e.g. `logging-standards` → `py-logging-reviewer`; `test-standards` → six `testing-*` agents). Phase 5's decision (recorded here) is **retrofit-in-place**: each becomes a valid v2 agent providing **interim cross-cutting coverage**, annotated with its eventual successor and retirement phase. Nothing is deleted; nothing breaks; the command/skill references keep working. Retirement happens organically when each successor lands.

## The retrofit contract — what every refactored agent gains

1. **Frontmatter** matching `schemas/agent-frontmatter.schema.json`: `name` (PSF-prefixed), `description`, `tools`, `model`, `memory`, `maxTurns`, `tier`, `pack`, `scope`.
2. **A declared `tier`** consistent with its tools (read/reason forbid Edit/Write). Reviewers are `tier: write` (verdicts are structured writes); analysts/coordinators are `tier: reason`.
3. **AgentVerdict output** — the body declares the `{ok, reason, confidence, evidence}` shape (per the planning session's `AgentVerdict` contract). `confidence` is the new field; below-threshold verdicts escalate.
4. **Body structure** the arch-doc-reviewer enforces: H1, `## Procedure`, `## Output`, `## Do not`.
5. **Relocation** from `agents/<name>.md` into `agents/<category>/<name>.md`.
6. **A successor annotation** — a one-line note naming the v2 agent(s) that will supersede it and the phase they land.

## Scope contract — the 13 agents

Proposed mapping (final names confirmed per-stream by `meta-agent-scaffolder` + `meta-agent-arch-doc-reviewer`):

| Legacy | v2 name | Category | Tier | Model | Successor (phase) |
|---|---|---|---|---|---|
| code-reviewer | `validation-code-reviewer` | validation | write | sonnet | stack reviewers + `/review` (P6/P8) |
| validation-standards | `validation-standards-reviewer` | validation | reason | sonnet | objective/completion verifiers (exist) |
| lint-standards | `validation-lint-reviewer` | validation | write | haiku | `post_edit_lint` + stack reviewers (P6/P8) |
| type-standards | `validation-type-safety-reviewer` | validation | write | sonnet | `py-doc-checker` + FE type reviewers (P6/P8) |
| doc-writer | `doc-technical-writer` | document | write | sonnet | `doc-adr/runbook/sequence/onboarding-writer` (P9) |
| naming-standards | `meta-naming-standards-reviewer` | meta | write | sonnet | **direct successor** #120 — becomes canonical |
| test-standards | `testing-strategy-reviewer` | testing | write | sonnet | six `testing-*` agents (P9) |
| investigator | `operate-root-cause-analyst` | operate | reason | opus | `operate-incident-responder` #128 (P10) |
| logging-standards | `operate-logging-reviewer` | operate | write | sonnet | `py-logging-reviewer` #84 (P6) |
| error-standards | `operate-error-handling-reviewer` | operate | write | sonnet | stack reviewers + resilience patterns (P6/P8) |
| git-standards | `operate-git-workflow-reviewer` | operate | write | sonnet | `deploy-release-reviewer` + git hooks (P10) |
| housekeeping-standards | `maintain-housekeeping-reviewer` | maintain | write | sonnet | `maintain-*` agents (P10) |
| standards-orchestrator | `meta-standards-orchestrator` | meta | reason | opus | `/orchestrate` + `meta-session-planner` |

The validation pair (`validation-objective-verifier`, `validation-completion-verifier`) already shipped in Phase 1 — Phase 5 only confirms they remain operational; it does not rebuild them.

## Branches (parallel work, 5 streams)

1. `feat/phase-5-spec` — this document.
2. `feat/phase-5-validation-cluster` — `code-reviewer`, `validation-standards`, `lint-standards`, `type-standards` → `agents/validation/`.
3. `feat/phase-5-doc-naming-testing` — `doc-writer`, `naming-standards`, `test-standards`.
4. `feat/phase-5-operate-maintain` — `investigator`, `logging-standards`, `error-standards`, `git-standards`, `housekeeping-standards`, `standards-orchestrator`.
5. `feat/phase-5-exit-gate` — smoke assertions + live verdict check + exit report.

Each agent lands as its own small PR per the established cadence; the streams group them for parallel worktrees. Streams 2–4 are independent; stream 5 serializes after them. Any command/skill that referenced a moved agent by path is updated in the same PR that moves it.

## Phase 5 exit gate — extended smoke test

`scripts/bootstrap_smoke.py` grows from 33 to ~37 assertions:

- **No flat-root agent file without frontmatter remains** — `agents/*.md` (excluding `CLAUDE.md`) is empty; every agent lives in a category subdir.
- **All 13 retrofitted agents have schema-valid frontmatter** with a declared `tier` consistent with their tools (the schema's `allOf` tier rules pass).
- **`build_graph_registry` discovers all 13** — node count grows by 13 and `--check` passes (registry matches disk).
- **Each retrofitted body has the arch-doc-reviewer structure** — H1 + `## Procedure` + `## Output` + `## Do not`, checked structurally.

`scripts/live_integration_smoke.py` gains **one live verdict check**: one retrofitted agent is invoked with a real model call and must return a JSON object matching the AgentVerdict shape (`ok: bool`, `reason: str`, `confidence: float` in `[0,1]`, `evidence: list`). It uses the existing skip-when-no-`ANTHROPIC_API_KEY` path, so unkeyed CI is unaffected.

Full-suite targets: pytest 100% green; `bootstrap_smoke` ~37/37; ruff / mypy-strict clean.

## What is explicitly NOT in Phase 5

- **Building the Phase 6–10 successor agents** (stack, testing, doc, pattern populations) — each lands in its own phase. Phase 5 only marks the interim agents with their successor.
- **Retiring any legacy agent** — retrofit-in-place; deletion happens when a successor ships, not now.
- **A formal `schemas/contracts/agent-verdict.schema.json`** — the verdict shape is asserted structurally (body declaration) and live (inline shape check). A committed contract schema is deferred to whichever phase first needs cross-tool verdict consumption.
- **The `meta-conflict-resolver` / `meta-sycophancy-detector`** (#123/#124) — Phase 5 retrofits existing agents only; new meta-agents are later work.

## Phase 5 → Phase 6 handover

Phase 6 (TDD Workflow + Stack Agents) begins replacing the interim coverage: `py-*` and `fe-*` reviewers supersede the generic `validation-*` / `operate-*` agents for their languages. Each successor PR retires the interim agent it replaces and updates the registry. The `closed-loop-quality-scorer` (Phase 4) now has a full agent population to score, so Phase 6 reviewers carry precision data from their first runs.

## References

- Canonical plan archive — `docs/decision-records/v2-architecture-planning-session.md` §§ A (agent catalog), F.13 (retrofitting existing agents), 1477 (Phase 5 row)
- Tier model — `@docs/architecture/principles/rrw-tiering.md`
- Agent frontmatter rule — `.claude/rules/agent-frontmatter.md`
- Phase 4 exit report — `docs/phases/phase-4-exit-report.md`
