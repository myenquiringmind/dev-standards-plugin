# Phase 6 — TDD Workflow + Stack Agents

**Duration:** 3 weeks (canonical estimate; actual cadence follows the established small-PR rhythm).
**Prerequisite:** Phase 5 exit. `bootstrap_smoke` 37/37 on master (`8ccc40e`); all 13 legacy agents retrofitted into the v2 taxonomy; `agent-verdict.schema.json` pinning the canonical verdict shape.
**Exit gate:** the full Develop→Validate loop runs end-to-end on a test project — `/scaffold` → `/tdd` → `/validate` → stamped commit — with language routing live and the strict default blocking on a deliberate SOLID violation. Python stack (9), Frontend stack (7), Interface (3), and Database reviewers (3) are discovered by `build_graph_registry` and pass `meta-agent-arch-doc-reviewer`. `bootstrap_smoke` grows 37 → ~45.

Phase 6 is where the framework stops being a *gate* and becomes a *workflow*. Phases 0–5 built the rails: hooks, shared modules, the stamp model, telemetry, and a disciplined agent population. Phase 6 lays the track the developer actually rides — the test-driven Develop process and the per-language reviewer stacks that make `/validate`'s language-routed gates real rather than placeholder.

## What Phase 6 delivers

1. **The Develop process** — `/scaffold <module>` and `/tdd <objective>` commands implementing the RED→GREEN→REFACTOR loop (canonical plan § B.4).
2. **22 profile-scoped stack agents** — Python (9), Frontend (7), Interface (3), Database (3) — that the `/validate` language gates dispatch to.
3. **Language routing** — `detect_language.py` (exists) drives which stack gate runs; each gate writes its own stamp (`.validation_stamp`, `.frontend_validation_stamp`, `.db_validation_stamp`, `.api_validation_stamp`).
4. **The 3-stamp model fully operational** — multiple language gates can be required for one commit; `pre_commit_cli_gate.py` enforces all applicable stamps.

## The stack-agent catalog — 22 agents (canonical plan § A.7–A.9, A.11)

### Python stack (9) — `agents/python/`, `pack: python`, `scope: profile-scoped`

| # | Agent | Tier | Model | Concern |
|---|---|---|---|---|
| 76 | `py-solid-dry-reviewer` | write | opus | SOLID/DRY on modified Python files |
| 77 | `py-security-reviewer` | write | opus | injection, pickle/eval/yaml.load, shell=True |
| 78 | `py-doc-checker` | write | sonnet | Google docstrings + annotations (auto-fixer) |
| 79 | `py-code-simplifier` | write | opus | complexity, dead code, redundancy |
| 80 | `py-tdd-process-reviewer` | reason | opus | tests-first discipline, property-test quality |
| 81 | `py-arch-doc-reviewer` | write | opus | drift vs `docs/architecture/` |
| 82 | `py-migration-reviewer` | write | opus | Alembic/Django migration safety |
| 83 | `py-api-reviewer` | write | opus | FastAPI/Django + Pydantic patterns |
| 84 | `py-logging-reviewer` | write | sonnet | structlog usage, levels, context |

### Frontend stack (7) — `agents/frontend/`, `pack: frontend`, `scope: profile-scoped`

| # | Agent | Tier | Model | Concern |
|---|---|---|---|---|
| 85 | `fe-component-reviewer` | write | opus | hooks rules, prop drilling, RSC boundaries |
| 86 | `fe-security-reviewer` | write | opus | XSS, dangerouslySetInnerHTML, prototype pollution |
| 87 | `fe-doc-checker` | write | sonnet | JSDoc on exports (auto-fixer) |
| 88 | `fe-code-simplifier` | write | opus | frontend complexity reduction |
| 89 | `fe-accessibility-reviewer` | write | sonnet | WCAG 2.2, ARIA, keyboard nav |
| 90 | `fe-state-reviewer` | write | opus | server vs client state, store boundaries |
| 91 | `fe-performance-reviewer` | write | opus | bundle size, re-renders, React Compiler |

### Interface / API boundaries (3) — `agents/interface/`, `pack: interface`

Active when multiple language profiles are detected. Distinct from the Phase 3 `agents/api/` *scanners* (`api-contract-extractor`, `api-breaking-change-analyzer`); these are *reviewers*.

| # | Agent | Tier | Model | Concern |
|---|---|---|---|---|
| 92 | `api-contract-reviewer` | write | opus | OpenAPI/tRPC consistency, breaking changes |
| 93 | `api-type-boundary-reviewer` | write | opus | Zod/Pydantic alignment across FE↔BE |
| 94 | `api-versioning-reviewer` | write | sonnet | versioning strategy compliance |

### Database reviewers (3) — `agents/database/`, `pack: database`

Land alongside the Phase 3 `db-schema-scanner` / `db-migration-planner`; these are the blocking `/validate` reviewers.

| # | Agent | Tier | Model | Concern |
|---|---|---|---|---|
| 96 | `db-schema-reviewer` | write | opus | normalization, indexing, constraints |
| 97 | `db-migration-safety-reviewer` | write | opus | reversibility, lock-awareness, dual-write |
| 98 | `db-query-optimizer-advisor` | reason | opus | N+1, query plans, index recommendations |

All reviewers emit the canonical `AgentVerdict` (`{agent, status, confidence, findings}`) pinned by `schemas/contracts/agent-verdict.schema.json`. Auto-fixers (`py-doc-checker`, `fe-doc-checker`) carry `isolation: worktree`.

## Commands

| Command | State | Phase 6 work |
|---|---|---|
| `/scaffold` | new | stub + RED test skeleton generator; invokes `meta-folder-structure-advisor`, `meta-filename-advisor` |
| `/tdd` | new | RED→GREEN→REFACTOR loop; routes to `py-*`/`fe-*` agents; auto-invokes `/validate` |
| `/debug` | new | hypothesis-driven debug loop; composes `operate-root-cause-analyst` |
| `/fix` | upgrade | existing v1-style command → v2 (meta-session-planner first step, agent composition) |
| `/typecheck` | upgrade | existing v1-style command → v2; routes via `detect_language.py` |

Each new/upgraded command passes `meta-command-composition-reviewer` (one responsibility, no command-calls-command, session-planner first).

## New hooks

- `run_cli_checks.py` — runs the 4 parallel per-language CLI checks (ruff/format/mypy/pytest, or eslint/tsc/vitest) and feeds `stamp_validation.py`. Today only `pre_commit_cli_gate.py` (the consumer) exists.
- `post_scaffold_red_gate.py` (PostToolUse) — asserts scaffolded tests are RED (FAIL, not ERROR) before `/tdd` proceeds.

Each hook ships with `hooks/tests/test_<name>.py` per `.claude/rules/hook-development.md`.

## Successor retirement policy

Phase 6 begins superseding the interim cross-cutting agents marked in Phase 5. Retirement is **coverage-gated, not landing-gated**: an interim agent is retired only when *every active profile* it covers has a successor. Because the stack agents land Python + Frontend first, a cross-cutting interim (e.g. `operate-logging-reviewer`, whose Python successor is `py-logging-reviewer`) is **demoted to fallback** for not-yet-covered languages, not deleted. The registry routes Python/Frontend work to the new stack agents; the interim agent stays registered for the remaining profiles until its last successor lands. Each demotion updates the interim agent's successor annotation and the registry in the same PR.

## Branches (parallel work, streams)

1. `feat/phase-6-spec` — this document.
2. `feat/phase-6-develop-commands` — `/scaffold`, `/tdd`, `/debug` + `run_cli_checks.py`, `post_scaffold_red_gate.py`.
3. `feat/phase-6-python-stack` — the 9 `py-*` agents → `agents/python/`.
4. `feat/phase-6-frontend-stack` — the 7 `fe-*` agents → `agents/frontend/`.
5. `feat/phase-6-interface-database` — 3 `api-*` reviewers + 3 `db-*` reviewers.
6. `feat/phase-6-fix-typecheck-upgrade` — v2 upgrade of `/fix`, `/typecheck`.
7. `feat/phase-6-exit-gate` — smoke assertions + the end-to-end TDD-loop integration test + exit report.

Streams 3–6 are independent (separate worktrees); stream 2 should land before the exit gate so the loop is exercisable; stream 7 serializes last. Each agent lands as its own small PR per the established cadence.

## Phase 6 exit gate — extended smoke test

`scripts/bootstrap_smoke.py` grows from 37 to ~45 assertions:

- **22 stack agents discovered** — `build_graph_registry` node count grows by 22; `--check` passes (registry matches disk).
- **All 22 have schema-valid frontmatter** with a `tier` consistent with their tools and a correct PSF prefix (`py-`, `fe-`, `api-`, `db-`).
- **`agents/python/` and `agents/frontend/` exist and are non-empty**; `agents/interface/` holds the 3 `api-*` reviewers.
- **Each body has the arch-doc-reviewer structure** — H1 + `## Procedure` + `## Output` + `## Do not`.
- **Language routing assertion** — `detect_language.py` over a mixed staging set selects the correct gate set.

End-to-end integration test (`scripts/live_integration_smoke.py` or a dedicated harness): on a throwaway test project, `/scaffold` → `/tdd` produces RED-before-GREEN tests, `/validate` runs the Python gate and writes `.validation_stamp`, and a commit succeeds. A deliberate SOLID violation makes `py-solid-dry-reviewer` block — proving the strict default is live. Uses the existing skip-when-no-`ANTHROPIC_API_KEY` path.

Full-suite targets: pytest 100% green; `bootstrap_smoke` ~45/45; ruff / mypy-strict clean.

## What is explicitly NOT in Phase 6

- **Pattern / anti-pattern / refactor agents** (`/pattern`, `/refactor`) — Phase 8.
- **Security-depth and testing-strategy agent populations** — Phase 9 (the `testing-strategy-reviewer` interim from Phase 5 keeps cross-cutting coverage until then).
- **Deleting any interim agent** — coverage-gated demotion only (see retirement policy).
- **The `interop-contract-reviewer`** (#95, FFI) — Phase 11.
- **Additional language profiles beyond Python/Frontend** activation — Phase 11; Go/Rust profiles exist on disk but their stack agents are not built here.

## Phase 6 → Phase 7 handover

With the Develop and Validate loops live and a real stack-agent population, Phase 7 (Design + Discover + Research) adds the *upstream* of the lifecycle — `/design`, `/plan`, `/discover`, `/research` — feeding objectives into the now-working `/scaffold`→`/tdd` pipeline. The `closed-loop-quality-scorer` (Phase 4) now scores a full reviewer population, so Phase 6 agents carry precision data into Phase 7.

## References

- Canonical plan archive — `docs/decision-records/v2-architecture-planning-session.md` §§ A.7–A.11 (stack catalog), B.4–B.5 (Develop/Validate processes), 1478 (Phase 6 row)
- Tier model — `@docs/architecture/principles/rrw-tiering.md`
- Agent frontmatter rule — `.claude/rules/agent-frontmatter.md`
- Phase 5 spec + exit report — `docs/phases/phase-5-core-agent-refactor.md`, `docs/phases/phase-5-exit-report.md`
</content>
</invoke>
