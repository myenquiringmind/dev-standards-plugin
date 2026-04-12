# Agent Catalog

156 agents across 21 categories. Each agent is a subprocess LLM invocation with a typed `AgentVerdict` return. Agents are the judgment layer — use them when the decision exceeds what a regex or AST check can do (see PSF at `@principles/psf.md`).

## By category

| Category | Count | Tier mix | Phase | Purpose |
|---|---|---|---|---|
| design | 6 | 5 reason, 1 write | 7 | Brainstorm, requirements, architecture review, API/schema design, gap analysis |
| discover | 3 | 2 read-reason, 1 reason | 7 | Requirements elicitation, stakeholder mapping, project-state classification |
| research | 2 | 1 BG read, 1 reason | 7 | Prior-art scan, spike planning (gated by complexity classifier) |
| document | 4 | 4 write | 9 | ADR writer, runbook writer, sequence diagrammer, onboarding writer |
| patterns | 54 | 53 reason, 1 write | 8 | GoF + architectural + concurrency + cloud + integration + resilience + DDD + API + testing patterns |
| antipatterns | 8 | 8 BG read | 8 | God class, shotgun surgery, feature envy, primitive obsession, long params, speculative generality, middle man, data clumps |
| python | 9 | 5 write, 2 reason, 2 write(fix) | 6 | SOLID/DRY, security, docs, simplifier, TDD, arch-doc, migration, API, logging |
| frontend | 7 | 4 reason, 2 write, 1 write(fix) | 6 | Component, security, docs, simplifier, accessibility, state, performance |
| interface | 6 | 3 write, 3 read/reason | 6+3 | Contract review, type boundary, versioning + contract extractor, usage profiler, breaking-change analyzer |
| interop | 1 | 1 write | 11 | FFI boundary validation (cbindgen, pyo3, wasm-bindgen) |
| database | 7 | 3 write, 3 read, 1 reason | 6+3 | Schema review, migration safety, query optimizer + schema scanner, data profiler, query extractor, migration planner |
| codebase | 5 | 4 read, 1 reason | 3 | Inventory scanner, dependency grapher, dead-code detector, convention profiler, architecture reconstructor |
| security | 6 | 3 write, 2 BG read, 1 reason | 9 | SAST, SBOM, secret scanner, dep vuln, license compliance, threat modeler |
| testing | 6 | 3 write, 2 BG read, 1 reason | 9 | Pyramid enforcer, coverage-per-layer, regression generator, flake detector, impact analyzer, mutation runner |
| validation | 2 | 2 reason | 4 | Objective verifier (blocks scope drift), completion verifier (blocks unverified claims) |
| meta | 12 | 5 write, 5 reason, 1 BG read, 1 reason | 3 | Scaffolders (agent/command/hook), reviewers (arch-doc, composition, naming, graph-registry, primitive-selection), conflict resolver, sycophancy detector |
| refactor | 3 | 1 read, 1 reason, 1 write | 8 | Detector → planner → applier (worktree) pipeline |
| operate | 3 | 2 reason, 1 reason | 10 | Incident responder, SLO monitor, runbook executor |
| maintain | 3 | 1 write, 2 BG read | 10 | Dependency updater (worktree), deprecation scanner, flake detector |
| deploy | 4 | 3 write, 1 reason | 10 | Release reviewer, migration-sequence reviewer, smoke runner, canary advisor |
| closed-loop | 5 | 2 BG reason, 2 BG read, 1 read-reason-write | 5+10 | Retrospective analyst, knowledge compactor, rolling summarizer, quality scorer, transcript-todo extractor |

## R/R/W tier distribution

| Tier | Count | Tools allowed |
|---|---|---|
| Read | ~25 | Read, Glob, Grep, Bash (read-only subset) |
| Reason | ~65 | Read, Bash (read-only) |
| Write | ~63 | Read, Edit, Write, Bash, Glob, Grep |
| Read-reason-write | 1 | Full (sanctioned exception: transcript-todo-extractor) |

See `@principles/rrw-tiering.md` for enforcement.

## Model allocation

| Model | Count | Used for |
|---|---|---|
| Opus max effort | ~8 | Architecture reviewer, brainstormer, debug advisor, retrospective analyst, research scanner, gap analyst, migration planner, threat modeler |
| Opus normal | ~60 | All blocking reviewers, pattern advisors, refactor planner, conflict resolver |
| Sonnet | ~65 | Auto-fixers, scaffolders, scanners, profilers, setup wizard |
| Haiku | ~23 | Handoff, status, logs, telemetry, quality scorer, rolling summarizer, transcript extractor |

## How agents interact with other components

```
Commands ──compose──> Agents ──return──> AgentVerdict
                         │
                         ├── Read hooks/_hook_shared.py (validation step tuples)
                         ├── Write via hooks/write_agent_memory.py (persistent memory)
                         ├── Produce stamps via hooks/stamp_validation.py
                         └── Scoped by config/profiles/*.json (language detection)
```

Agents never call commands. Commands compose agents. Hooks gate agents. Profiles scope agents. The graph registry (`config/graph-registry.json`) records all these edges.

## Naming convention

`<scope>-<domain>-<role>.md` where:
- Scope: `py`, `fe`, `db`, `api`, `pattern`, `meta`, `design`, `codebase`, `closed-loop`, etc.
- Domain: what it works on (solid-dry, schema, migration, strategy, ...)
- Role: `-reviewer` (blocking write), `-checker` (auto-fixer write), `-advisor` (reason), `-scaffolder` (write), `-scanner` (read), `-profiler` (read), `-analyst` (reason), `-planner` (reason)

Enforced by `schemas/agent-frontmatter.schema.json` name regex.

## Full agent list

For the complete 156-agent inventory with per-agent descriptions, see the archived plan at `../decision-records/v2-architecture-planning-session.md` Appendix A. That catalog will be maintained here once agents are built and `doc-component-catalog-writer` (Phase 9) keeps it in sync with the source files.
