# Architecture Plan v2: Comprehensive Agentic Lifecycle Framework

**Status:** Proposed. Supersedes `mossy-beaming-penguin.md` where sections conflict; inherits baseline where silent.
**Target version:** `dev-standards-plugin` v2.0.0
**Host platform:** Windows (primary), Unix (supported)
**Strictness default:** Strict (Modelling-project stance)

---

## 1. Context

`dev-standards-plugin` v1.4.0 is a code-quality enforcement plugin: 13 flat agents, 20 inline-JS hooks, no graph registry, no persistent memory, no validation stamps, no language profiles. A prior architecture plan (`mossy-beaming-penguin.md`, 945 lines) proposed a graph-structured redesign to 62 agents, 18 commands, 25 hooks — synthesising `dev-standards-plugin`, the Modelling project, and Superpowers.

Three things the baseline plan missed, surfaced during a planning-mode deep review:

1. **Claude Code's plugin surface is larger than the baseline knows.** CC supports ~26 hook events (baseline uses 17), agent `isolation: "worktree"` / `background: true` / `effort`, plugin-level `userConfig` / `channels` / `bin/` / `lspServers` / `mcpServers` / `outputStyles`, `${CLAUDE_PLUGIN_DATA}` durable storage, and four hook types (command/http/prompt/agent). The framework can ship far more than agents+commands+hooks.
2. **Observability must precede agent population.** The baseline grows to 62 agents before any telemetry, incident log, or quality scoring exists. A framework that cannot measure whether its agents work is a static linter in disguise. Closed-loop infrastructure has to land before the agent fleet does.
3. **Windows is the host.** Baseline is silent on cross-platform concerns. Atomic writes, file locking, path-traversal safety, and symlink handling are not polish items — they are preconditions for everything that writes state.

This plan is the delta + new architectural sections. It takes strong positions on eight hard trade-offs (§11). The goal is a framework that covers the **entire software lifecycle** (discover → research → design → develop → test → validate → deploy → operate → maintain, with document cross-cutting), ships **~130 agents** phased over 11 implementation phases, enforces strict-by-default validation via a 3+ stamp model, and **learns from its own failures** via incident logs, telemetry, and knowledge compaction.

---

## 2. Guiding Principles (refined from baseline §1)

1. **Graph-first.** Every component is a node; every relationship is a typed edge. Non-negotiable.
2. **Mechanical enforcement > behavioural instruction.** Hooks that block beat markdown that asks. Rules are read; hooks execute.
3. **Observability before scale.** Telemetry, incident log, and quality scoring land in Phase 5 — before the large agent populations of Phases 6-10.
4. **Closed-loop improvement.** The framework learns: agent failures → incidents → retrospectives → rule/prompt updates → principles → rules. Monthly knowledge compaction.
5. **Language-extensible.** Core is language-agnostic; stack-specific behaviour lives in profile-scoped agents and profile step tuples.
6. **Dogfooding.** The framework uses its own agents, commands, validation gates, and telemetry to build itself. Meta-agents are not optional.
7. **Windows-first portability.** `_os_safe.py` is mandatory. Every path operation, every file write, every lock goes through it.
8. **Strict by default.** Block on every step the stamp model declares blocking. `[WIP]` and merge-in-progress remain the only bypasses. Adoption pain is preferable to silent drift.
9. **DRY single source of truth.** Validation step tuples live in `_hook_shared.py`. Graph registry is a derived artifact built from distributed component manifests.
10. **Closed-loop verification.** Every claim is verified; every auto-fix triggers re-validation (max 1 cycle per gate).

---

## 3. Primitive Selection Framework (PSF)

The single decision reference: **when a new constraint or capability enters the framework, where does it live?**

**Selection order (pick leftmost that can express the requirement):**

```
Rule → Hook → Agent → Skill → Command → MCP tool
```

| Primitive | When to use | Lifetime | Fail mode |
|---|---|---|---|
| **Rule** | Immutable behavioural guidance the model should know when editing specific paths. Cheap to load (<1KB). Path- and phase-scoped via frontmatter. | Loaded on `InstructionsLoaded`; scoped by path/phase | Fails open (advisory) |
| **Hook** | Deterministic code on a lifecycle event. Must execute regardless of model attention. Blocks or emits telemetry. <30s. | Per-event | Fails closed (blocks) |
| **Agent** | Judgment that exceeds regex/AST. Produces typed `AgentVerdict`. Isolated context. Optional worktree isolation. | Per-invocation; persistent memory tier | Verdict `{ok, reason, confidence}` |
| **Skill** | Auto-triggered capability bundle. Multi-turn workflows. Activates without explicit invocation via `paths` + `description` match. | Loaded on trigger; stays for session | Fails open |
| **Command** | User-invoked multi-agent orchestration with a single named responsibility. Commands compose agents; never the reverse. | Per-invocation | Explicit exit code |
| **MCP tool** | Reusable capability across sessions/CI/other clients. Durable state. Network/auth complexity. | Framework lifetime | Protocol-defined |

**Principle:** If in doubt, use the *lowest-privilege* primitive. A regex check belongs in a hook, not an agent. A cross-session query belongs in MCP, not a hook. PSF is enforced by `meta-primitive-selection-reviewer` during `/new-agent`, `/new-hook`, `/new-rule`, etc.

---

## 4. Graph Architecture (revised)

### 4.1 Node types (unchanged from baseline §1.1)

Agent, Command, Hook, Skill, Rule, Gate, Profile, Template — plus three new types:

| Node type | Description | Location |
|---|---|---|
| **MCPServer** | Bundled MCP server exposing framework capabilities | `mcp-servers/<name>/` |
| **BinTool** | Standalone CLI executable | `bin/<name>` |
| **OutputStyle** | Claude response rendering style | `output-styles/<name>.md` |

### 4.2 Edge types (add to baseline §1.2)

Baseline: `triggers`, `validates`, `depends-on`, `produces`, `consumes`, `gates`, `composes`, `scoped-by`.

**Add:**
- `escalates-to` — Agent A escalates to agent/human B on low confidence or conflict
- `observed-by` — Component A emits telemetry consumed by B (usually the telemetry hook)
- `derives-principle-from` — Rule R was promoted from agent memory M via knowledge compactor
- `overridden-by` — Project-local overlay supersedes plugin-canonical component

### 4.3 Graph registry is a derived artifact

**Decision:** `config/graph-registry.json` is not hand-edited. It is **built** from per-component frontmatter by `scripts/build-graph-registry.py`, run as a pre-commit hook via `meta-graph-registry-validator`. Developers edit their component's frontmatter; the aggregator rebuilds the registry atomically.

**Rationale:** Monolithic registry = single source of query. Distributed manifests = single source of truth per component. Pre-commit aggregation gives both with no drift risk.

### 4.4 Interface contracts (extended from baseline §1.3)

```
AgentVerdict     = { ok: bool, reason: str, confidence: float, evidence: list[Evidence] }
Evidence         = { kind: "file"|"diff"|"log"|"test", locator: str, excerpt: str }
ValidationStamp  = { timestamp: ISO8601, branch: str, steps: str[], ttl_seconds: int, version: str }
HookInput        = { session_id, transcript_path, cwd, permission_mode, hook_event_name, ... }
HookOutput       = { continue: bool, decision: "allow"|"block"|"ask"|"defer", updatedInput?: dict, systemMessage?: str }
SessionState     = { timestamp, active_request, todos, files_modified, git_state, errors, context }
LanguageProfile  = { name, detection, tools, packageManager, agents, validationSteps, conventions }
ObjectiveDoc     = { objectives: str[], scope: str[], complexity: "S"|"M"|"L"|"XL", phase: str }
GraphNode        = { id, type, category, metadata, scope, owner }
GraphEdge        = { from, to, type, contract, weight?, confidence? }
Incident         = { id, timestamp, trigger, agent, phase, verdict, root_cause, resolution, rule_emerged?, tokens, wall_ms }
TelemetryRecord  = { ts, agent, phase, input_tokens, output_tokens, wall_ms, verdict, confidence, user_overturned? }
Principle        = { id, title, body, source_memories: str[], emerged_date, version }
```

All contracts formalised as JSON Schema in `schemas/contracts/<name>.schema.json`.

---

## 5. Four-Tier Memory + Context Budget

### 5.1 Memory tiers

| Tier | Location | Scope | Lifetime | Written by | Read by |
|---|---|---|---|---|---|
| **Session** | `~/.claude/projects/<slug>/memory/` (Claude Auto Memory) | Current session | Until compact/SessionEnd | Claude harness + `session_end.py` | `session_start.py` |
| **Project** | `<repo>/.claude/memory/` | All sessions in this repo | Repo lifetime, git-tracked | `/handoff`, agents with `memory: project` | `session_start.py`, agents |
| **Agent** | `${CLAUDE_PLUGIN_DATA}/agent-memory/<agent>/MEMORY.md` | Per-agent, cross-project | Framework lifetime | `write_agent_memory.py` | Agent on invocation |
| **Framework** | `${CLAUDE_PLUGIN_DATA}/framework-memory/` | Global principles, incidents, telemetry, graph history | Permanent, append-only | Incident/telemetry hooks, knowledge compactor | MCP servers, retrospectives |

**Critical rule:** Claude Auto Memory (session tier) is owned by the harness. Framework memory is owned by the plugin. They never cross-write. `session_start.py` *reads* Auto Memory to seed context but never writes to it.

### 5.2 Per-phase context budget

Enforced by `context_budget.py` reading `.current_phase` written by `phase_transition.py`.

| Phase | Budget (tokens) | Warn % | Critical % |
|---|---|---|---|
| Discover | 40K | 80 | 95 |
| Research | 120K | 80 | 95 |
| Design | 100K | 80 | 95 |
| Develop (scaffold) | 30K | 85 | 95 |
| Develop (tdd) | 60K | 80 | 95 |
| Validate | 50K | 85 | 95 |
| Test | 40K | 85 | 95 |
| Deploy | 30K | 90 | 95 |
| Operate | 80K | 80 | 95 |
| Maintain | 40K | 85 | 95 |

**Cache-aware pacing:** `_hook_shared.py` exposes `CACHE_SAFE_INTERVALS = {"warm": 270, "cold": 1200}`. Any `ScheduleWakeup` or background agent must pick from this set. 5-minute intervals are forbidden (worst-of-both: cache miss without amortization).

### 5.3 Rolling summary

`context-rolling-summarizer` background agent fires when budget hits 70%. Compresses older turns into a structured summary in the session tier; keeps the last 3 `AgentVerdict` records verbatim (they carry evidence).

### 5.4 Selective rule loading

Rules gain frontmatter:
```yaml
scope: ["src/**/*.py", "!tests/**"]
phase: ["develop", "validate"]
version: "1.0"
```
`InstructionsLoaded` hook only materializes rules where scope matches the current file set and phase matches `.current_phase`.

---

## 6. Closed-Loop Improvement Architecture

### 6.1 Components

| Component | Primitive | Location | Purpose |
|---|---|---|---|
| Incident log write | Hook (multiple) | `${CLAUDE_PLUGIN_DATA}/framework-memory/incidents/<YYYY-MM>/<ulid>.json` | Append-only failure record |
| Incident log query | MCP server `incident-log` | `mcp-servers/incident-log/` | Cross-session retrieval |
| Telemetry emit | Hooks `subagent_start.py`, `subagent_summary.py` | `${CLAUDE_PLUGIN_DATA}/framework-memory/telemetry/<agent>.jsonl` | Per-agent metrics |
| Telemetry export | MCP server `telemetry-export` + `bin/dsp-telemetry` | `mcp-servers/telemetry-export/` | CI/dashboard consumption |
| Quality scoring | Background agent `quality-scorer` (haiku, nightly) | `${CLAUDE_PLUGIN_DATA}/framework-memory/quality-scores.json` | Precision, recall, p95 latency, cost |
| Retrospective analysis | Foreground agent `incident-retrospective-analyst` (opus, effort: max, weekly) | `${CLAUDE_PLUGIN_DATA}/framework-memory/retrospectives/` | Clusters incidents; proposes prompt/rule diffs as plugin PRs |
| Knowledge compaction | Background agent `knowledge-compactor` (sonnet, monthly) | `${CLAUDE_PLUGIN_DATA}/framework-memory/principles/` | Promotes recurring memories to principles |
| Principle → rule | Command `/new-rule` | user-gated | Promotes principles to rules in the plugin repo |
| Feedback capture | Command `/feedback` + `permission_denied.py` | Incident log | Explicit + implicit signal |
| Graph history | `file_changed.py` matched on `graph-registry.json` | `${CLAUDE_PLUGIN_DATA}/framework-memory/graph-history/` | Snapshot on every change |

### 6.2 The loop, end-to-end

1. Agent fires → `subagent_summary.py` emits telemetry JSONL
2. User overturns verdict OR `permission_denied` OR `stop_failure` → incident record appended
3. Nightly `quality-scorer` updates per-agent scores from telemetry + incidents
4. Weekly `incident-retrospective-analyst` (opus max) clusters incidents → proposes agent-prompt/rule diffs as PR
5. Monthly `knowledge-compactor` promotes agent memories → principles → candidate rules
6. User reviews PRs; accepted changes flow into next plugin release
7. Next session starts with updated rules, updated agent prompts, refreshed profile

### 6.3 Dogfooding implication

The framework's retrospective analyst proposes PRs against the framework's own repo. The framework validates those PRs with its own gates. This is the closed loop at the framework level.

---

## 7. Lifecycle Phases (9 phases + 1 cross-cutting)

Baseline: Design → Develop → Test → Validate → Deploy (5).

**Revised:**

```
DISCOVER → RESEARCH → DESIGN → DEVELOP → TEST → VALIDATE → DEPLOY → OPERATE → MAINTAIN
                                                                         ↑_______↓
                                                              DOCUMENT (cross-cutting)
```

| Phase | New commands | New agent categories | Notes |
|---|---|---|---|
| Discover | `/discover` | `discover/` (2 agents) | Requirements elicitation, stakeholder mapping |
| Research | `/research` | `research/` (2 agents) | Only invoked for novel problems; gated by complexity classifier |
| Design | `/design`, `/plan`, `/debug` | `design/` (5 agents) | As baseline §4 |
| Develop | `/scaffold`, `/tdd`, `/fix`, `/pattern`, `/refactor` | `python/`, `frontend/`, `patterns/`, `antipatterns/`, `refactor/` | Refactor pipeline is new |
| Test | `/typecheck` | `testing/` (6 agents) | Pyramid, coverage-per-layer, regression, flake, impact, mutation |
| Validate | `/validate`, `/validate-agents` | `validation/`, `security/` (6 agents) | Security depth added |
| Deploy | (new) `/release` | `deploy/` (4 agents) | Canary + smoke added to baseline 2 |
| Operate | (new) `/incident` | `operate/` (3 agents) | Incident responder, SLO monitor, runbook executor |
| Maintain | (new) `/maintain` | `maintain/` (3 agents) | Dep updater, deprecation scanner, flake detector |
| **Document** (cross-cutting) | `/document` | `document/` (4 agents) | ADR writer, runbook writer, sequence diagrammer, onboarding writer |

---

## 8. Complete Component Taxonomy

### 8.1 Agents — ~130 total, phased

| Category | Count | Examples | Phase |
|---|---|---|---|
| design | 5 | brainstormer, requirements-analyst, architecture-reviewer, api-contract-designer, schema-designer | 7 |
| discover | 2 | requirements-elicitor, stakeholder-mapper | 7 |
| research | 2 | prior-art-scanner (background), spike-planner | 7 |
| document | 4 | adr-writer, runbook-writer, sequence-diagrammer, onboarding-writer | 9 |
| patterns | 59 | creational (4), structural (5), behavioural (9), architectural (5), concurrency (5), cloud/distributed (7), integration (5), resilience (4), DDD (4), API (3), testing (3) + 5 baseline architectural | 8 |
| antipatterns | 8 | god-class, shotgun-surgery, feature-envy, primitive-obsession, long-parameter-list, speculative-generality, middle-man, data-clumps (all background) | 8 |
| python | 9 | solid-dry, security, doc, code-simplifier, tdd-process, arch-doc, migration, api, logging | 6 |
| frontend | 7 | component, security, doc, code-simplifier, accessibility, state, performance | 6 |
| interface | 3 | api-contract, type-boundary, versioning | 6 |
| interop | 1 | interop-contract-reviewer (FFI, cbindgen, pyo3, wasm-bindgen) | 11 |
| database | 3 | schema, migration-safety, query-optimizer | 6 |
| security | 6 | sast-runner, sbom-generator, secret-scanner, dep-vuln-scanner, license-compliance, threat-modeler | 9 |
| testing | 6 | pyramid-enforcer, coverage-per-layer, regression-generator, flake-detector, impact-analyzer, mutation-runner | 9 |
| validation | 2 | objective-verifier, completion-verifier | 4 |
| meta | 12 | agent-arch-doc-reviewer, command-composition-reviewer, agent-scaffolder, command-scaffolder, hook-scaffolder, folder-structure-advisor, filename-advisor, naming-standards-reviewer, graph-registry-validator, primitive-selection-reviewer, conflict-resolver, sycophancy-detector | 3 |
| refactor | 3 | detector, planner, applier (worktree) | 8 |
| operate | 3 | incident-responder, slo-monitor, runbook-executor | 10 |
| maintain | 3 | dependency-updater (worktree), deprecation-scanner (background), flake-detector | 10 |
| deploy | 4 | release-reviewer, migration-sequence-reviewer, smoke-runner, canary-advisor | 10 |
| background-scanners | 6 | codebase-pattern-sweep, anti-pattern-full-scan, sbom-refresh, dependency-audit, telemetry-roll-up, quality-scorer | 5, 10 |
| closed-loop | 4 | incident-retrospective-analyst, knowledge-compactor, context-rolling-summarizer, prompt-refiner | 5, 10 |
| **Total** | **~132** | | |

**Confidence + escalation:** Every `AgentVerdict` carries `confidence: 0.0-1.0`. Below-threshold verdicts (default 0.7) trigger `meta-conflict-resolver` or escalate via `/escalate`.

**Worktree isolation:** All auto-fixers (`py-doc-checker`, `fe-doc-checker`, all `meta-*-scaffolder`, `refactor-applier`, `maintain-dependency-updater`) run with `isolation: "worktree"`.

**Background mode:** `antipattern-*`, `research-prior-art-scanner`, `security-sbom-generator`, `security-dep-vuln-scanner`, `testing-mutation-runner`, `maintain-deprecation-scanner`, `codebase-pattern-sweep`, `quality-scorer`, `knowledge-compactor`, `context-rolling-summarizer`.

### 8.2 Commands — 27 total

Baseline 18 + new: `/discover`, `/research`, `/document`, `/refactor`, `/incident`, `/maintain`, `/escalate`, `/feedback`, `/new-rule`. All with frontmatter (`context`, `model`, `allowed-tools`, `argument-hint`). Commands compose agents; commands never call commands.

### 8.3 Hooks — 36 total

Baseline 25 + new: `post_compact.py`, `stop_failure.py`, `post_tool_failure.py`, `subagent_start.py`, `task_created.py`, `task_completed.py`, `file_changed.py`, `worktree_lifecycle.py`, `config_change.py`, `cwd_changed.py`, `instructions_loaded.py`, `permission_denied.py`, `phase_transition.py`.

**Shared modules** (prefix `_`):
- `_hook_shared.py` — validation step tuples, cache intervals, budget dicts, utility re-exports
- `_session_state_common.py` — session state capture, transcript parsing (from Modelling)
- `_os_safe.py` — **mandatory** atomic writes, file locking (portalocker), safe path join, normalize, temp lifecycle
- `_telemetry.py` — JSONL emission, batching, rotation
- `_incident.py` — ULID generation, incident schema, append-only writer
- `_graph.py` — graph registry loader, query helpers, topological sort

**Pre-commit gate split:**
- `pre_commit_cli_gate.py` (fast, CLI-only stamp checks, <500ms)
- `pre_commit_agent_gate.py` (hook type `agent`, invokes `validation-completion-verifier`)

### 8.4 Skills — 12 total

Baseline 6 + new: `discover-process`, `research-process`, `document-process`, `operate-process`, `maintain-process`, `refactor-pipeline`. Each with `paths` frontmatter for selective auto-triggering and `context: fork` for long procedures.

### 8.5 Rules — 22 total

Baseline 11 + new: `naming-database.md`, `naming-api.md`, `naming-env-vars.md`, `naming-git.md`, `naming-observability.md`, `naming-cicd.md`, `naming-containers.md`, `os-safety.md`, `agent-coordination.md`, `telemetry.md`, `agentic-failure-modes.md`.

All rules get frontmatter: `scope`, `phase`, `version`.

### 8.6 Language profiles — 7

`python.json` (P0), `typescript.json` (P0), `javascript.json` (P1), `fullstack.json` (composite), `rust.json` (P2 placeholder), `go.json` (P2 placeholder), `kotlin.json` (P3 placeholder).

### 8.7 Templates — 9

`CLAUDE.md.template`, `agent.md.template`, `command.md.template`, `hook.py.template`, `profile.json.template`, `rule.md.template`, `mcp-server.template`, `skill.template`, `bin-tool.template`.

### 8.8 Schemas — 8

`config.schema.json`, `hooks.schema.json`, `profile.schema.json`, `graph-registry.schema.json`, `agent-frontmatter.schema.json`, `command-frontmatter.schema.json`, `rule-frontmatter.schema.json`, `contracts/*.schema.json` (one per interface contract from §4.4).

### 8.9 MCP servers — 4 bundled

| Server | Purpose | Tools exposed |
|---|---|---|
| `graph-query` | Query the graph registry | `find_validators_for`, `impact_analysis`, `topological_order`, `export_mermaid` |
| `memory-search` | Search agent + framework memory | `search_memories`, `find_similar_incidents`, `get_principle` |
| `telemetry-export` | Export telemetry for CI/dashboards | `get_agent_metrics`, `get_phase_metrics`, `get_quality_scores` |
| `incident-log` | Query incident history | `list_incidents`, `get_incident`, `find_by_rule`, `cluster_by_root_cause` |

All MCP servers written in Python, invoked via `stdio` transport. Config in `plugin.json` `mcpServers` field.

### 8.10 Bin tools — 4 standalone CLIs

| Tool | Purpose |
|---|---|
| `dsp-validate` | Run validation gates from CI without a Claude session |
| `dsp-graph` | Query graph registry (same MCP endpoints, CLI wrapper) |
| `dsp-incident` | Query/export incident log |
| `dsp-telemetry` | Export telemetry metrics |

Added to `PATH` by Claude Code via plugin `bin/` directory.

### 8.11 Output styles — 2

`dsp-strict` (terse, evidence-first, no hedging), `dsp-advisory` (explanatory, teaching mode).

### 8.12 userConfig (plugin install prompts)

```json
{
  "userConfig": {
    "telemetryOptIn": { "type": "boolean", "default": true },
    "preferredModel": { "type": "string", "enum": ["opus", "sonnet", "haiku"], "default": "sonnet" },
    "networkMode": { "type": "string", "enum": ["online", "offline"], "default": "online" },
    "teamMode": { "type": "string", "enum": ["solo", "team"], "default": "solo" },
    "teamId": { "type": "string", "optional": true },
    "slackWebhook": { "type": "string", "sensitive": true, "optional": true },
    "strictnessOverride": { "type": "string", "enum": ["strict", "balanced", "advisory"], "default": "strict" }
  }
}
```

Note: `strictness` default is `strict` (user decision). Override exists for teams that cannot adopt strict immediately, but default stays strict.

---

## 9. Target Folder Structure (delta from baseline §13)

Baseline folder tree stands, with these additions:

```
dev-standards-plugin/
├── .claude-plugin/
│   ├── plugin.json                                    # Extended: userConfig, channels, mcpServers, bin, outputStyles
│   └── marketplace.json
├── agents/
│   ├── discover/                                      # NEW
│   ├── research/                                      # NEW
│   ├── document/                                      # NEW
│   ├── antipatterns/                                  # NEW
│   ├── security/                                      # NEW
│   ├── testing/                                       # NEW (testing strategy, not test-standards)
│   ├── interop/                                       # NEW
│   ├── operate/                                       # NEW
│   ├── maintain/                                      # NEW
│   ├── refactor/                                      # NEW
│   ├── background-scanners/                           # NEW
│   ├── closed-loop/                                   # NEW
│   └── ... (baseline categories: design, patterns, python, frontend, interface, database, validation, meta, deploy)
├── hooks/
│   ├── _os_safe.py                                    # NEW (mandatory)
│   ├── _telemetry.py                                  # NEW
│   ├── _incident.py                                   # NEW
│   ├── _graph.py                                      # NEW
│   ├── post_compact.py                                # NEW
│   ├── stop_failure.py                                # NEW
│   ├── post_tool_failure.py                           # NEW
│   ├── subagent_start.py                              # NEW
│   ├── task_created.py                                # NEW
│   ├── task_completed.py                              # NEW
│   ├── file_changed.py                                # NEW
│   ├── worktree_lifecycle.py                          # NEW
│   ├── config_change.py                               # NEW
│   ├── cwd_changed.py                                 # NEW
│   ├── instructions_loaded.py                         # NEW
│   ├── permission_denied.py                           # NEW
│   ├── phase_transition.py                            # NEW
│   ├── pre_commit_cli_gate.py                         # SPLIT from baseline pre_commit_gate
│   ├── pre_commit_agent_gate.py                       # NEW (hook type agent)
│   └── ... (baseline hooks)
├── mcp-servers/                                       # NEW top-level
│   ├── graph-query/
│   ├── memory-search/
│   ├── telemetry-export/
│   └── incident-log/
├── bin/                                               # NEW top-level
│   ├── dsp-validate
│   ├── dsp-graph
│   ├── dsp-incident
│   └── dsp-telemetry
├── output-styles/                                     # NEW top-level
│   ├── dsp-strict.md
│   └── dsp-advisory.md
├── templates/
│   ├── rule.md.template                               # NEW
│   ├── mcp-server.template                            # NEW
│   ├── skill.template                                 # NEW
│   └── bin-tool.template                              # NEW
├── schemas/
│   ├── agent-frontmatter.schema.json                  # NEW
│   ├── command-frontmatter.schema.json                # NEW
│   ├── rule-frontmatter.schema.json                   # NEW
│   └── contracts/                                     # NEW
│       ├── agent-verdict.schema.json
│       ├── validation-stamp.schema.json
│       ├── incident.schema.json
│       ├── telemetry-record.schema.json
│       └── principle.schema.json
├── scripts/
│   └── build-graph-registry.py                        # NEW (derived artifact aggregator)
├── docs/
│   └── architecture/
│       ├── README.md
│       ├── primitive-selection-framework.md           # NEW — the PSF decision reference
│       ├── graph-architecture.md
│       ├── interface-contracts.md
│       ├── lifecycle-phases.md
│       ├── language-profiles.md
│       ├── agent-inventory.md
│       ├── naming-conventions.md
│       ├── memory-tiers.md                            # NEW
│       ├── closed-loop-improvement.md                 # NEW
│       ├── context-budget.md                          # NEW
│       └── os-safety.md                               # NEW
└── ... (baseline: lib, config, rules, skills, tests)
```

**Note on `${CLAUDE_PLUGIN_DATA}`:** Not a folder in the repo. Durable framework state lives at runtime in `~/.claude/plugins/data/dev-standards-plugin/`:
```
${CLAUDE_PLUGIN_DATA}/
├── agent-memory/<agent-name>/MEMORY.md
├── framework-memory/
│   ├── incidents/<YYYY-MM>/<ulid>.json
│   ├── telemetry/<agent>.jsonl
│   ├── quality-scores.json
│   ├── retrospectives/
│   ├── principles/
│   └── graph-history/
└── cache/
```

---

## 10. Implementation Roadmap (11 phases)

Sequencing is designed so each phase validates the architecture of the previous phase. The highest-risk dependency is the **graph registry schema + distributed manifest aggregator** — pulled to Phase 3 (earlier than baseline) because everything downstream composes via it.

### Phase 0 — Architecture & Schema Lockdown (1-2 weeks)
- Merge this plan with baseline into a consolidated architecture doc set under `docs/architecture/`
- Lock graph registry schema and interface contracts (JSON Schema files in `schemas/`)
- Write PSF reference doc
- Lock memory-tier design and context budget tables
- **Exit:** all schemas pass `meta-graph-registry-validator` stub; PSF reference doc reviewed

### Phase 1 — OS Safety + Shared Modules (1-2 weeks) ⚠ Windows-critical
- `_os_safe.py` with atomic writes, file locking (portalocker), safe_join, normalize_path, temp lifecycle
- `_hook_shared.py`, `_session_state_common.py`, `_telemetry.py`, `_incident.py`, `_graph.py`
- `${CLAUDE_PLUGIN_DATA}` scaffolding + path helpers
- Cross-platform test suite (`tests/os-safety/`) — **must pass on Windows before proceeding**
- **Exit:** Windows + Unix CI green on `_os_safe.py` test suite

### Phase 2 — Hooks Foundation (2 weeks)
- Migrate all 20 baseline hooks from inline JS → Python files
- Add the 16 new hooks from §8.3
- `hooks/hooks.json` becomes thin shim calling Python files
- Language detection + profile loader (`detect_language.py`)
- Initial `config/profiles/python.json`, `typescript.json`, `fullstack.json`
- `plugin.json` extended with `userConfig`, `outputStyles`
- **Exit:** all 36 hooks unit-tested; language detection produces correct profile on Modelling repo + a React+Python fullstack test repo

### Phase 3 — Graph Registry + Meta-Agents (2 weeks) ⚠ Critical path
- `scripts/build-graph-registry.py` — distributed manifest aggregator
- Pre-commit hook wires `meta-graph-registry-validator`
- Meta-agents: `agent-scaffolder`, `command-scaffolder`, `hook-scaffolder`, `graph-registry-validator`, `primitive-selection-reviewer`, `naming-standards-reviewer`
- `/new-agent`, `/new-command`, `/new-hook`, `/new-rule` commands
- All templates (agent.md.template, etc.)
- **Exit:** meta-agents can scaffold themselves. `/new-agent foo` produces a valid agent file, updates the registry, and passes validation. Dogfooding loop closed.

### Phase 4 — Core Agents Refactor + Validation Pair (1-2 weeks)
- Refactor existing 13 agents into new taxonomy with YAML frontmatter, confidence field, worktree isolation where applicable
- Implement `validation-objective-verifier`, `validation-completion-verifier`
- Port Modelling project's `write_agent_memory.py` pattern
- **Exit:** existing 13 agents produce valid `AgentVerdict`s; validation pair operational

### Phase 5 — Memory + Telemetry Infrastructure (2 weeks) ⚠ Must precede large agent populations
- Implement 4-tier memory (session / project / agent / framework)
- Telemetry emission via `subagent_start.py` / `subagent_summary.py`
- Incident log writes via `stop_failure.py`, `post_tool_failure.py`, `permission_denied.py`
- `${CLAUDE_PLUGIN_DATA}/framework-memory/` fully wired
- `quality-scorer` background agent (haiku, nightly)
- `context-rolling-summarizer` background agent
- Graph history snapshots on `file_changed.py` for registry
- **Exit:** every agent invocation produces telemetry; every failure produces incident; quality scores visible via `bin/dsp-telemetry`

### Phase 6 — TDD Workflow + Stack Agents (3 weeks)
- Commands: `/scaffold`, `/tdd`, `/handoff`, `/status`, `/validate`, `/validate-agents`, `/fix`, `/debug`, `/typecheck`, `/logs`, `/setup`
- Python stack (9 agents) + Frontend stack (7 agents) + Interface (3) + Database (3)
- 3-stamp validation model fully operational
- WIP/merge bypass logic
- Re-validation cycles (max 1 per gate)
- Strict default active
- **Exit:** full TDD loop works end-to-end on a test project; all stamps enforced

### Phase 7 — Design + Discover + Research (2 weeks)
- Commands: `/discover`, `/research`, `/design`, `/plan`
- Design phase agents (5), discover (2), research (2)
- Complexity classifier gates `/research`
- Anti-rationalization rules
- **Exit:** full design phase pipeline operational; research phase only fires on novel problems

### Phase 8 — Patterns + Anti-patterns + Refactoring (3 weeks)
- 59 pattern agents (phased: architectural → creational → structural → behavioural → concurrency → cloud → integration → resilience → DDD → API → testing)
- 8 anti-pattern detection agents (all background)
- 3 refactor agents (detector, planner, applier)
- Commands: `/pattern`, `/refactor`, `/pattern-scan`
- **Exit:** `/pattern strategy` scaffolds a valid Strategy implementation; `/refactor` pipeline runs end-to-end in worktree

### Phase 9 — Security + Testing + Documentation (2 weeks)
- 6 security agents, 6 testing-strategy agents, 4 document agents
- Commands: `/document`, `/security-scan`
- SAST + SBOM + secret-scanner integrations
- Test pyramid + coverage-per-layer enforcement
- **Exit:** security scan blocks on real secrets; test pyramid enforcement catches pyramid violations

### Phase 10 — Operate + Maintain + Closed Loop + MCP (3 weeks)
- 3 operate agents, 3 maintain agents, 4 closed-loop agents
- 4 bundled MCP servers (graph-query, memory-search, telemetry-export, incident-log)
- 4 bin tools (dsp-validate, dsp-graph, dsp-incident, dsp-telemetry)
- Retrospective analyst + knowledge compactor active
- Commands: `/incident`, `/maintain`, `/escalate`, `/feedback`, `/new-rule`
- **Exit:** MCP servers queryable from external clients; retrospective analyst produces a real PR against the plugin repo

### Phase 11 — Polish, Marketplace, Multi-language (2 weeks)
- Additional language profiles (Rust, Go, Kotlin, Julia placeholders activated)
- `interop-contract-reviewer` agent
- Channels integration (Slack, Telegram optional)
- Offline bundle via `bin/dsp-offline-bundle`
- Team mode
- Marketplace listing + plugin.json polish
- Architecture diagrams generated from graph registry
- **Exit:** plugin publishable to marketplace; full audit report green

**Total: ~24-28 weeks** (6-7 months) at a steady cadence. First usable framework state (end of Phase 6, ~11-13 weeks) is when TDD workflow + strict gates are live.

---

## 11. Hard Trade-offs (Positions)

1. **Python hooks with JSON shim.** Baseline is right. Modelling runs Python hooks successfully; plugin already requires Python for ruff/mypy; Python has pytest/mypy for testing hooks themselves; JS-inline hooks in `hooks.json` are untestable.

2. **JSON + JSON Schema for graph registry.** TypeScript adds a build step and non-LLM tooling. YAML has whitespace footguns and no canonical diff. JSON + JSON Schema is parseable by every agent, diff-friendly, `jq`/MCP-native.

3. **Monolithic registry built from distributed manifests.** Each component declares its node in frontmatter; `scripts/build-graph-registry.py` aggregates pre-commit. Single source of truth (per-component) + single source of query (aggregated). No drift.

4. **Sync validation gates; async background scanners.** Blocking gates (pre-commit) are sync. Anti-pattern scans, SBOM, mutation tests, quality scoring are `background: true` + `ScheduleWakeup`. Rule: *if it blocks a commit, it's sync; if it informs next session, it's async.*

5. **Plugin-canonical agents with overlay.** Projects overlay in `.claude/agents/` with `overlay: true` frontmatter; loader merges overlay over base. Never fork-and-edit.

6. **Framework state in `${CLAUDE_PLUGIN_DATA}`, keyed by `(repo_origin_url, branch)`.** Per-user global. Incidents and memory never leak between repos. Worktree-safe.

7. **Strict default.** Block on everything the stamp model says blocks. `[WIP]` + merge-in-progress are the only bypasses. `userConfig.strictnessOverride` exists but default stays strict. Matches Modelling.

8. **Opus/Sonnet/Haiku allocation:**
   - **Opus `effort: max`:** `design-brainstormer`, `design-architecture-reviewer`, `debug-phase-advisor`, `incident-retrospective-analyst`, `research-prior-art-scanner`
   - **Opus normal:** all blocking reviewers, pattern advisors, refactor-planner, conflict-resolver
   - **Sonnet:** auto-fixers, scaffolders, `knowledge-compactor`, `filename-advisor`, `folder-structure-advisor`
   - **Haiku:** `/handoff`, `/status`, `/logs`, telemetry emitters, `quality-scorer` (arithmetic over JSONL), `context-rolling-summarizer`
   - Principle: *judgment → opus; rote → sonnet; summarization → haiku.*

---

## 12. Critical Files (new, existing, and reused)

### New files to create in Phase 0-3 (foundational, everything depends on these)

- `C:\Users\jmarks01\Projects\dev-standards-plugin\hooks\_os_safe.py` — **Phase 1, Windows-critical**
- `C:\Users\jmarks01\Projects\dev-standards-plugin\hooks\_hook_shared.py` — **Phase 1** (cache intervals, validation tuples, budgets)
- `C:\Users\jmarks01\Projects\dev-standards-plugin\hooks\_session_state_common.py` — **Phase 1** (port from Modelling)
- `C:\Users\jmarks01\Projects\dev-standards-plugin\hooks\_telemetry.py` — Phase 1
- `C:\Users\jmarks01\Projects\dev-standards-plugin\hooks\_incident.py` — Phase 1
- `C:\Users\jmarks01\Projects\dev-standards-plugin\hooks\_graph.py` — Phase 1
- `C:\Users\jmarks01\Projects\dev-standards-plugin\schemas\graph-registry.schema.json` — **Phase 0**
- `C:\Users\jmarks01\Projects\dev-standards-plugin\schemas\contracts\agent-verdict.schema.json` — Phase 0
- `C:\Users\jmarks01\Projects\dev-standards-plugin\schemas\contracts\validation-stamp.schema.json` — Phase 0
- `C:\Users\jmarks01\Projects\dev-standards-plugin\schemas\contracts\incident.schema.json` — Phase 0
- `C:\Users\jmarks01\Projects\dev-standards-plugin\config\graph-registry.json` — **Phase 3** (derived artifact; never hand-edited)
- `C:\Users\jmarks01\Projects\dev-standards-plugin\scripts\build-graph-registry.py` — **Phase 3**
- `C:\Users\jmarks01\Projects\dev-standards-plugin\.claude-plugin\plugin.json` — **Phase 2** (update: add userConfig, outputStyles, mcpServers, bin)
- `C:\Users\jmarks01\Projects\dev-standards-plugin\docs\architecture\primitive-selection-framework.md` — Phase 0
- `C:\Users\jmarks01\Projects\dev-standards-plugin\docs\architecture\memory-tiers.md` — Phase 0
- `C:\Users\jmarks01\Projects\dev-standards-plugin\docs\architecture\closed-loop-improvement.md` — Phase 0
- `C:\Users\jmarks01\Projects\dev-standards-plugin\docs\architecture\context-budget.md` — Phase 0
- `C:\Users\jmarks01\Projects\dev-standards-plugin\docs\architecture\os-safety.md` — Phase 0

### Reuse from existing repo (per current-state audit)

- `C:\Users\jmarks01\Projects\dev-standards-plugin\lib\venv\` — **100% reusable** (venv discovery, uv/pip, auto-create)
- `C:\Users\jmarks01\Projects\dev-standards-plugin\lib\git\index.js` — **95% reusable** (branch protection, commits, rollback points)
- `C:\Users\jmarks01\Projects\dev-standards-plugin\lib\core\platform.js` — cross-platform detection helpers (feeds `_os_safe.py`)
- `C:\Users\jmarks01\Projects\dev-standards-plugin\lib\core\config.js:530-538` — `DOMAIN_EXECUTION_ORDER` becomes the initial node topological sort input to `_graph.py`
- `C:\Users\jmarks01\Projects\dev-standards-plugin\lib\orchestrator\index.js:26-36` — `DOMAINS` mapping becomes the initial graph edge set
- `C:\Users\jmarks01\Projects\dev-standards-plugin\lib\validation\` — sanitization patterns feed `_os_safe.py` safe_join
- `C:\Users\jmarks01\Projects\dev-standards-plugin\lib\logging\` — session logging infrastructure
- `C:\Users\jmarks01\Projects\dev-standards-plugin\tests\` — test framework stays; new test suites added per phase

### Port from Modelling project

- `C:\Users\jmarks01\Projects\Modelling\.claude\hooks\_hook_shared.py` — validation step tuples, cache thresholds
- `C:\Users\jmarks01\Projects\Modelling\.claude\hooks\_session_state_common.py` — transcript parsing logic
- `C:\Users\jmarks01\Projects\Modelling\.claude\hooks\write_agent_memory.py` — path-safe memory writer
- `C:\Users\jmarks01\Projects\Modelling\.claude\hooks\stamp_validation.py` — 3-stamp writer
- `C:\Users\jmarks01\Projects\Modelling\.claude\hooks\run_cli_checks.py` — parallel CLI runner pattern
- `C:\Users\jmarks01\Projects\Modelling\.claude\hooks\pre_commit_gate.py` — stamp enforcement, WIP/merge bypass logic
- `C:\Users\jmarks01\Projects\Modelling\.claude\agents\*` — all 13 agents as templates for new stack agents

---

## 13. Verification

End-to-end verification per phase:

| Phase | How to verify |
|---|---|
| 0 | All JSON schemas validate against themselves; PSF doc reviewed; interface contracts typechecked |
| 1 | `_os_safe.py` test suite passes on Windows AND Unix CI; atomic write test with concurrent writers produces no corruption |
| 2 | All 36 hooks fire on a synthetic session; language detection correctly identifies Python-only / React-only / fullstack projects |
| 3 | `/new-agent foo --category python` produces a valid agent file, updates graph registry, and passes `meta-graph-registry-validator`. The meta-agents can scaffold themselves — true dogfooding exit. |
| 4 | Existing 13 agents each return a valid `AgentVerdict`; `validation-objective-verifier` detects a deliberate scope mismatch |
| 5 | Every agent invocation writes a telemetry record; an induced failure produces an incident record; `bin/dsp-telemetry` shows per-agent latency and verdict counts |
| 6 | Full TDD loop on a test project: `/scaffold` → `/tdd` → `/validate` → `git commit` gated by stamps. Strict default blocks on a deliberate SOLID violation. |
| 7 | `/discover` produces requirements doc; `/research` only fires on novel problems (complexity classifier); `/design` produces architecture doc with trade-offs |
| 8 | `/pattern strategy` scaffolds a valid Strategy implementation; `/refactor` pipeline detects, plans, applies in worktree; background anti-pattern scanner reports god-class detection |
| 9 | `security-secret-scanner` blocks on a deliberate API key commit; `testing-pyramid-enforcer` blocks on e2e-heavy test distribution; `/document` generates ADR from a design decision |
| 10 | MCP server `graph-query` returns valid results from an external MCP client; retrospective analyst produces a PR against the plugin repo; `/incident` full flow |
| 11 | Plugin installs cleanly on a fresh machine; `userConfig` prompts work; offline bundle produces a self-contained tarball; marketplace listing passes validation |

**Framework-level verification** (continuous after Phase 5):
- Telemetry shows per-agent precision ≥ 0.85 after 2 weeks of dogfooding
- Quality scores improve month-over-month (knowledge compactor working)
- Incident count trends down (retrospectives working)
- No context-budget violations in normal operation

---

## 14. Risks & Mitigations (delta from baseline §13 Risks)

| Risk | Mitigation |
|---|---|
| **Plugin size** (~132 agents, 36 hooks, 4 MCP servers, 4 bin tools) | Language profiles activate only relevant agents; lazy loading via graph registry; background agents deferred to idle |
| **Hook performance on Windows** (Python startup ~50ms × 36 hooks) | Cache language profile; batch hooks where possible; profile cold-start on Windows CI |
| **Agent count overwhelms validation** | `/validate` only spawns agents scoped to changed file types via graph traversal from changed-files → profile → agents |
| **Auto-fixer conflicts** | Execution ordering defined in validation step tuples; re-validation after fixes (max 1 cycle) |
| **Graph registry drift** | `meta-graph-registry-validator` runs on pre-commit; registry is derived artifact so hand-edits are caught immediately |
| **Context exhaustion during `/validate`** | Subagents run with `context: fork`; each has bounded `maxTurns` and `effort`; rolling summarizer fires at 70% |
| **Windows path gotchas** | `_os_safe.py` is mandatory; cross-platform tests block Phase 1 exit |
| **Telemetry storage growth** | JSONL rotation monthly; quality-scorer compacts old telemetry into aggregate |
| **Closed loop producing spurious rule PRs** | Retrospective analyst requires `confidence ≥ 0.8` and minimum incident cluster size (3); user-gated via `/new-rule` |
| **Strict default blocks adoption** | `userConfig.strictnessOverride` exists; escape hatch documented in README; balanced/advisory modes supported but not default |
| **MCP server complexity** | Start with thin wrappers over existing query functions; Phase 10 only after memory infrastructure is solid |
| **Build-graph-registry.py staleness** | Wired to pre-commit via husky; CI check blocks merge if registry out of sync with manifests |
| **24-28 week timeline** | Phases 0-6 are the critical path (~13 weeks) for minimum usable framework; Phases 7-11 are additive value on a working base |

---

## 15. Open Questions (not blocking plan approval)

1. **MCP server hosting strategy.** Are bundled MCP servers invoked as subprocesses of the plugin (`stdio` transport) or as long-running processes? Subprocess is simpler; long-running enables caching. Lean: subprocess for Phase 10, evaluate long-running for Phase 11.
2. **Telemetry privacy.** `telemetryOptIn: true` is the default but telemetry never leaves the user's machine unless explicitly exported. Document this clearly in README.
3. **Rule versioning.** Rules have `version:` frontmatter. Do we enforce SemVer? Lean: yes, bump minor on content change, major on removal/rename.
4. **Principle-to-rule promotion UX.** `/new-rule` is user-gated. Should the knowledge compactor auto-PR candidate rules, or queue them for `/new-rule review`? Lean: queue, not auto-PR.
5. **Monorepo profile selection.** When `.current_phase` and `.language_profile.json` disagree because the user `cd`'d into a subdirectory, which wins? `CwdChanged` re-runs detection. Lean: path-scoped profile wins over session-scoped.

---

## 16. What This Plan Commits To

- **~132 agents** phased across 11 phases (Comprehensive scope, per your decision)
- **Full closed-loop infrastructure in Phase 5** before the large agent population (Full closed loop, per your decision)
- **Windows-first via mandatory `_os_safe.py`** (Windows-first, per your decision)
- **Strict default** matching the Modelling project's stance (Strict default, per your decision)
- **Primitive Selection Framework** as the single decision reference for where new logic lives
- **4-tier memory** with explicit separation from Claude Auto Memory
- **Derived graph registry** built from distributed component manifests
- **Python hooks with JSON shim**, **JSON+JSON Schema registry**, **sync gates / async scanners**, **plugin-canonical agents with overlay**
- **4 bundled MCP servers** and **4 standalone bin tools** as first-class deliverables
- **Windows + Unix cross-platform tests** as a Phase 1 exit gate
- **24-28 week timeline** with first usable framework state at end of Phase 6 (~13 weeks)

This is the target architecture. After approval, Phase 0 begins by materialising `docs/architecture/` and the JSON schemas; those are the only artifacts needed before Phase 1 can start.

---

# Appendix A — Complete Agent Catalog

Legend — **Type**: `B` blocking (halts pipeline), `F` auto-fixer (writes files), `A` advisory (returns suggestions), `BG` background (async). **Model**: `O+` opus max effort, `O` opus, `S` sonnet, `H` haiku. **Scope**: core (always) or profile-scoped (activates only when language/context matches).

## A.1 Design Phase (5 agents) — core

| # | Agent | Type | Model | What it does |
|---|---|---|---|---|
| 1 | `design-brainstormer-advisor` | A | O+ | Socratic design: generates 2-3 alternative approaches, compares trade-offs, recommends one with explicit reasoning |
| 2 | `design-requirements-analyst` | A | O | Extracts functional and non-functional requirements from a user description; produces a structured requirements doc |
| 3 | `design-architecture-reviewer` | B | O+ | Enforces SOLID, Clean Architecture, layer boundaries; blocks designs that violate layering or coupling rules |
| 4 | `design-api-contract-designer` | A | O | Designs OpenAPI/tRPC contracts for interface boundaries before implementation |
| 5 | `design-schema-designer` | A | O | Designs database schemas with normalization, indexing strategy, and migration planning |

## A.2 Discover Phase (2 agents) — core

| # | Agent | Type | Model | What it does |
|---|---|---|---|---|
| 6 | `discover-requirements-elicitor` | A | O | Simulates stakeholder interviews; extracts user stories, acceptance criteria, constraints |
| 7 | `discover-stakeholder-mapper` | A | S | Identifies affected stakeholders, concerns, success criteria, and potential objections |

## A.3 Research Phase (2 agents) — core, gated by complexity

| # | Agent | Type | Model | What it does |
|---|---|---|---|---|
| 8 | `research-prior-art-scanner` | BG | O+ | Background scan of codebase + web for similar problems, existing solutions, reusable components |
| 9 | `research-spike-planner` | A | O | Plans time-boxed exploration spikes with explicit hypotheses, success criteria, and kill-switches |

## A.4 Document Phase (4 agents) — cross-cutting

| # | Agent | Type | Model | What it does |
|---|---|---|---|---|
| 10 | `doc-adr-writer` | F | S | Writes Architecture Decision Records from design sessions; tracks context, decision, consequences |
| 11 | `doc-runbook-writer` | F | S | Generates operational runbooks from code + architecture; includes rollback procedures |
| 12 | `doc-sequence-diagrammer` | F | S | Produces Mermaid sequence diagrams from code traces; keeps them in sync with source |
| 13 | `doc-onboarding-writer` | F | S | Generates onboarding docs for new contributors; explains setup, mental model, first-task guide |

## A.5 Design Patterns (54 agents) — core, language-aware via idiom tables

Each pattern agent has the same structure: **When to apply** / **When NOT to apply** / **Language idioms** / **Scaffold** / **Review checklist**.

### Creational (4)
| # | Agent | Model | Pattern |
|---|---|---|---|
| 14 | `pattern-factory-advisor` | O | Factory Method + Abstract Factory |
| 15 | `pattern-builder-advisor` | O | Builder for complex object construction |
| 16 | `pattern-singleton-advisor` | O | Singleton (with DI warnings) |
| 17 | `pattern-prototype-advisor` | O | Prototype / clone |

### Structural (5)
| # | Agent | Model | Pattern |
|---|---|---|---|
| 18 | `pattern-adapter-advisor` | O | Interface translation between incompatible types |
| 19 | `pattern-decorator-advisor` | O | Cross-cutting concerns layered around objects |
| 20 | `pattern-facade-advisor` | O | Simplified interface over a subsystem |
| 21 | `pattern-composite-advisor` | O | Tree structures with uniform leaf/node treatment |
| 22 | `pattern-proxy-advisor` | O | Lazy loading, access control, remote stand-ins |

### Behavioural (9)
| # | Agent | Model | Pattern |
|---|---|---|---|
| 23 | `pattern-strategy-advisor` | O | Interchangeable algorithms selected at runtime |
| 24 | `pattern-observer-advisor` | O | Event/pub-sub decoupling |
| 25 | `pattern-command-advisor` | O | Undoable operations as first-class objects |
| 26 | `pattern-chain-of-responsibility-advisor` | O | Request pipelines with handler composition |
| 27 | `pattern-state-advisor` | O | State machines with explicit transitions |
| 28 | `pattern-mediator-advisor` | O | Many-to-many interaction reduction |
| 29 | `pattern-template-method-advisor` | O | Algorithm skeletons with hooks for variation |
| 30 | `pattern-visitor-advisor` | O | Operations over heterogeneous collections |
| 31 | `pattern-iterator-advisor` | O | Custom iteration protocols |

### Architectural (5)
| # | Agent | Model | Pattern |
|---|---|---|---|
| 32 | `pattern-repository-advisor` | O | Data access abstraction |
| 33 | `pattern-unit-of-work-advisor` | O | Transactional consistency across repositories |
| 34 | `pattern-cqrs-advisor` | O | Command-Query Responsibility Separation |
| 35 | `pattern-event-sourcing-advisor` | O | Audit-complete state via event log |
| 36 | `pattern-clean-architecture-reviewer` | B | Layer enforcement (blocking) — no outer layer leaks inward |

### Concurrency (5)
| # | Agent | Model | Pattern |
|---|---|---|---|
| 37 | `pattern-actor-advisor` | O | Isolated state + message passing (Erlang/Akka model) |
| 38 | `pattern-producer-consumer-advisor` | O | Bounded buffer between producers and consumers |
| 39 | `pattern-reactor-advisor` | O | Event-loop demultiplexing (Node.js, libuv, asyncio) |
| 40 | `pattern-thread-pool-advisor` | O | Fixed worker pool for bounded concurrency |
| 41 | `pattern-read-write-lock-advisor` | O | Concurrent reads with exclusive writes |

### Cloud / Distributed (7)
| # | Agent | Model | Pattern |
|---|---|---|---|
| 42 | `pattern-saga-advisor` | O | Distributed transactions via compensating actions |
| 43 | `pattern-outbox-advisor` | O | Reliable event publishing with transactional outbox |
| 44 | `pattern-circuit-breaker-advisor` | O | Failure isolation with trip/half-open/close states |
| 45 | `pattern-rate-limiter-advisor` | O | Token bucket, leaky bucket, fixed window |
| 46 | `pattern-leader-election-advisor` | O | Single-leader coordination (Raft, ZK) |
| 47 | `pattern-consistent-hashing-advisor` | O | Minimal-disruption sharding across nodes |
| 48 | `pattern-bulkhead-advisor` | O | Resource isolation to prevent cascade failure |

### Integration (5)
| # | Agent | Model | Pattern |
|---|---|---|---|
| 49 | `pattern-router-advisor` | O | Content-based routing between endpoints |
| 50 | `pattern-aggregator-advisor` | O | Combining responses from multiple services |
| 51 | `pattern-translator-advisor` | O | Message format translation |
| 52 | `pattern-content-enricher-advisor` | O | Adding context to in-flight messages |
| 53 | `pattern-claim-check-advisor` | O | Passing references instead of large payloads |

### Resilience (4)
| # | Agent | Model | Pattern |
|---|---|---|---|
| 54 | `pattern-cache-aside-advisor` | O | Read-through cache with explicit invalidation |
| 55 | `pattern-idempotency-key-advisor` | O | Safe retries via client-provided keys |
| 56 | `pattern-retry-backoff-advisor` | O | Exponential backoff + jitter |
| 57 | `pattern-dead-letter-queue-advisor` | O | Failed message quarantine |

### DDD (4)
| # | Agent | Model | Pattern |
|---|---|---|---|
| 58 | `pattern-aggregate-advisor` | O | Aggregate root with consistency boundary |
| 59 | `pattern-bounded-context-advisor` | O | Model boundaries with explicit integration |
| 60 | `pattern-anti-corruption-layer-advisor` | O | Isolation from legacy or external models |
| 61 | `pattern-domain-event-advisor` | O | Past-tense facts as first-class entities |

### API (3)
| # | Agent | Model | Pattern |
|---|---|---|---|
| 62 | `pattern-bff-advisor` | O | Backend-for-Frontend per client type |
| 63 | `pattern-api-gateway-advisor` | O | Single entry point with cross-cutting concerns |
| 64 | `pattern-back-pressure-advisor` | O | Flow control for overloaded consumers |

### Testing (3)
| # | Agent | Model | Pattern |
|---|---|---|---|
| 65 | `pattern-page-object-advisor` | O | UI abstraction for E2E tests |
| 66 | `pattern-test-data-builder-advisor` | O | Fluent test-data construction |
| 67 | `pattern-contract-test-advisor` | O | Consumer-driven contract testing (Pact) |

## A.6 Anti-Pattern Detectors (8 agents) — BG, core

| # | Agent | Type | Model | What it detects |
|---|---|---|---|---|
| 68 | `antipattern-god-class-detector` | BG | S | Classes doing too much; high LOC + many responsibilities |
| 69 | `antipattern-shotgun-surgery-detector` | BG | S | Changes that require editing many files at once |
| 70 | `antipattern-feature-envy-detector` | BG | S | Methods more interested in another class's data than their own |
| 71 | `antipattern-primitive-obsession-detector` | BG | S | Overuse of primitives where domain types would serve |
| 72 | `antipattern-long-parameter-list-detector` | BG | S | Methods with too many parameters (> 4-5) |
| 73 | `antipattern-speculative-generality-detector` | BG | S | Abstractions built for imagined future needs |
| 74 | `antipattern-middle-man-detector` | BG | S | Classes that only delegate without adding value |
| 75 | `antipattern-data-clumps-detector` | BG | S | Groups of fields that recur together and should be a type |

## A.7 Python Stack (9 agents) — profile-scoped

| # | Agent | Type | Model | What it does |
|---|---|---|---|---|
| 76 | `py-solid-dry-reviewer` | B | O | SOLID/DRY compliance on modified Python files |
| 77 | `py-security-reviewer` | B | O | Secrets, injection (SQL, command), insecure patterns (pickle, eval, yaml.load, shell=True) |
| 78 | `py-doc-checker` | F | S | Google-style docstrings, type annotations; auto-fixes missing docs |
| 79 | `py-code-simplifier` | B | O | Flags unnecessary complexity, dead code, redundancy |
| 80 | `py-tdd-process-reviewer` | A | O | TDD discipline: tests-first, scaffold compliance, property-test invariant quality |
| 81 | `py-arch-doc-reviewer` | B | O | Detects drift between Python code and `docs/architecture/` specs |
| 82 | `py-migration-reviewer` | B | O | Alembic/Django migration safety: reversibility, locking, data preservation |
| 83 | `py-api-reviewer` | B | O | FastAPI/Django patterns: Pydantic schemas, dependency injection, response typing |
| 84 | `py-logging-reviewer` | A | S | structlog usage, log levels, context propagation |

## A.8 Frontend Stack (7 agents) — profile-scoped

| # | Agent | Type | Model | What it does |
|---|---|---|---|---|
| 85 | `fe-component-reviewer` | A | O | React hooks rules, prop drilling, composition, Server Components boundaries |
| 86 | `fe-security-reviewer` | B | O | XSS, dangerouslySetInnerHTML, eval in JS, prototype pollution |
| 87 | `fe-doc-checker` | F | S | JSDoc on exported components/functions; auto-fixes |
| 88 | `fe-code-simplifier` | B | O | Frontend complexity reduction |
| 89 | `fe-accessibility-reviewer` | A | S | WCAG 2.2, ARIA, keyboard navigation |
| 90 | `fe-state-reviewer` | A | O | State management: server state vs client state, store boundaries |
| 91 | `fe-performance-reviewer` | A | O | Bundle size, re-renders, React Compiler awareness |

## A.9 Interface / API Boundaries (3 agents) — active when multiple languages detected

| # | Agent | Type | Model | What it does |
|---|---|---|---|---|
| 92 | `api-contract-reviewer` | B | O | OpenAPI/tRPC contract consistency; detects breaking changes |
| 93 | `api-type-boundary-reviewer` | B | O | Zod/Pydantic schema alignment across FE↔BE |
| 94 | `api-versioning-reviewer` | A | S | Versioning strategy compliance |

## A.10 Interop / FFI (1 agent) — Phase 11

| # | Agent | Type | Model | What it does |
|---|---|---|---|---|
| 95 | `interop-contract-reviewer` | B | O | Validates FFI boundaries (cbindgen, pyo3, wasm-bindgen) between Python↔Rust, JS↔Rust, etc. |

## A.11 Database (3 agents) — scoped by migration/model file presence

| # | Agent | Type | Model | What it does |
|---|---|---|---|---|
| 96 | `db-schema-reviewer` | B | O | Normalization, indexing, naming, constraint discipline |
| 97 | `db-migration-safety-reviewer` | B | O | Reversibility, data-preserving, lock-awareness, dual-write safety |
| 98 | `db-query-optimizer-advisor` | A | O | N+1 detection, query plan review, index recommendations |

## A.12 Security Depth (6 agents) — core

| # | Agent | Type | Model | What it does |
|---|---|---|---|---|
| 99 | `security-sast-runner` | B | S | Runs bandit/semgrep/eslint-security per profile; aggregates findings |
| 100 | `security-sbom-generator` | BG | S | Generates Software Bill of Materials (CycloneDX/SPDX) |
| 101 | `security-secret-scanner` | B | S | Scans diffs for API keys, tokens, credentials; blocks commits |
| 102 | `security-dep-vuln-scanner` | BG | S | Checks dependencies against CVE databases |
| 103 | `security-license-compliance` | B | S | Flags GPL contamination, license conflicts |
| 104 | `security-threat-modeler` | A | O+ | Design-phase STRIDE analysis, attack surface enumeration |

## A.13 Testing Strategy (6 agents) — core

| # | Agent | Type | Model | What it does |
|---|---|---|---|---|
| 105 | `testing-pyramid-enforcer` | B | O | Enforces unit:integration:e2e ratio per profile |
| 106 | `testing-coverage-per-layer-reviewer` | B | O | Coverage thresholds per architectural layer |
| 107 | `testing-regression-generator` | F | O | Generates regression tests from bug fixes |
| 108 | `testing-flake-detector` | BG | S | Identifies flaky tests via statistical analysis |
| 109 | `testing-impact-analyzer` | A | O | Graph traversal from changed files → tests affected |
| 110 | `testing-mutation-runner` | BG | S | Runs mutation testing (mutmut/Stryker) to measure test quality |

## A.14 Validation / Verification (2 agents) — core

| # | Agent | Type | Model | What it does |
|---|---|---|---|---|
| 111 | `validation-objective-verifier` | B | O+ | Compares git diff against stated objectives; blocks scope drift |
| 112 | `validation-completion-verifier` | B | O | No success claims without fresh verification evidence; defeats premature closure |

## A.15 Meta / Dogfooding (12 agents) — core, self-referential

| # | Agent | Type | Model | What it does |
|---|---|---|---|---|
| 113 | `meta-agent-arch-doc-reviewer` | B | O | Detects drift between agent files and `docs/architecture/` |
| 114 | `meta-command-composition-reviewer` | B | O | Walks the graph to verify commands don't duplicate responsibilities |
| 115 | `meta-agent-scaffolder` | F | S | Generates new agent file from template + updates graph registry manifest |
| 116 | `meta-command-scaffolder` | F | S | Generates new command file from template |
| 117 | `meta-hook-scaffolder` | F | S | Generates new Python hook from template with shared imports |
| 118 | `meta-folder-structure-advisor` | A | S | Validates/proposes folder structure for new features |
| 119 | `meta-filename-advisor` | A | S | File naming against active language profile conventions |
| 120 | `meta-naming-standards-reviewer` | B | O | Dispatches to per-category naming checks (db, API, env, git, observability, cicd, containers) |
| 121 | `meta-graph-registry-validator` | B | O | Validates `graph-registry.json` matches disk; runs on every pre-commit |
| 122 | `meta-primitive-selection-reviewer` | B | O | Enforces PSF decision order when new components are added |
| 123 | `meta-conflict-resolver` | A | O | Invoked when two blocking agents disagree on the same file; produces a reconciled verdict |
| 124 | `meta-sycophancy-detector` | BG | S | Scans agent verdicts for hedging-then-agreeing patterns (agentic failure mode) |

## A.16 Refactoring Pipeline (3 agents) — core

| # | Agent | Type | Model | What it does |
|---|---|---|---|---|
| 125 | `refactor-detector` | A | O | Identifies refactoring opportunities from code smells + anti-pattern reports |
| 126 | `refactor-planner` | A | O | Produces a step-by-step refactoring plan with safety checks |
| 127 | `refactor-applier` | F | O | Applies refactoring in a worktree with continuous validation between steps |

## A.17 Operate Phase (3 agents) — core

| # | Agent | Type | Model | What it does |
|---|---|---|---|---|
| 128 | `operate-incident-responder` | A | O+ | Incident triage: symptom → hypothesis → test → fix → postmortem |
| 129 | `operate-slo-monitor` | A | S | Monitors SLO compliance from telemetry; flags burn-rate alerts |
| 130 | `operate-runbook-executor` | A | S | Walks through runbook steps with validation at each stage |

## A.18 Maintain Phase (3 agents) — core

| # | Agent | Type | Model | What it does |
|---|---|---|---|---|
| 131 | `maintain-dependency-updater` | F | S | Updates dependencies in worktree; runs tests; reports breakages |
| 132 | `maintain-deprecation-scanner` | BG | S | Scans for deprecated API usage; produces migration plan |
| 133 | `maintain-flake-detector` | BG | S | Long-horizon flake detection (different from testing-flake-detector which is CI-scoped) |

## A.19 Deploy Phase (4 agents) — core

| # | Agent | Type | Model | What it does |
|---|---|---|---|---|
| 134 | `deploy-release-reviewer` | B | O | Validates changelog, version bump, breaking-change detection |
| 135 | `deploy-migration-sequence-reviewer` | B | O | Validates migration ordering and rollback plans |
| 136 | `deploy-smoke-runner` | B | S | Post-deploy smoke tests with structured pass/fail |
| 137 | `deploy-canary-advisor` | A | O | Canary deployment guidance with rollback triggers |

## A.20 Closed-Loop Improvement (4 agents) — core

| # | Agent | Type | Model | What it does |
|---|---|---|---|---|
| 138 | `closed-loop-incident-retrospective-analyst` | BG | O+ | Weekly: clusters incidents by root cause, proposes agent-prompt/rule diffs as PRs against the plugin repo |
| 139 | `closed-loop-knowledge-compactor` | BG | S | Monthly: promotes recurring patterns in agent memory to principles; principles become candidate rules |
| 140 | `closed-loop-context-rolling-summarizer` | BG | H | Fires at 70% context budget; compresses older turns; keeps last 3 AgentVerdicts verbatim |
| 141 | `closed-loop-quality-scorer` | BG | H | Nightly: computes per-agent precision/recall/p95 latency/cost from telemetry + incident overturns |

**Total agents: 141** (refined from earlier ~132 estimate). Phased rollout ensures no phase adds more than ~30 agents; each is validated by the meta-agents before landing.

---

# Appendix B — Lifecycle Phase Processes (End-to-End Walkthroughs)

This appendix walks through each phase as a process: **what triggers it**, **which agents fire in which order**, **what gets produced**, **what the stamps/gates enforce**. All processes run under the strict-default enforcement: any blocking agent returning `{ok: false}` halts the flow until the issue is resolved.

## B.1 Discover Process — "I have a vague problem, what am I actually solving?"

**Trigger:** `/discover <problem statement>`
**Phase marker:** `.current_phase = discover` written by `phase_transition.py`
**Budget:** 40K tokens

**Flow:**
1. `discover-requirements-elicitor` runs a structured interview: who, what, why, success criteria
2. `discover-stakeholder-mapper` identifies affected parties, concerns, objections
3. Outputs merged into `docs/discover/<topic>/requirements.md` + `docs/discover/<topic>/stakeholders.md`
4. Session memory updated with the discovery summary
5. Complexity classifier (`classify_difficulty.py`) reads outputs → decides whether to proceed to `/research` (novel) or jump to `/design` (familiar)

**Exit:** a written problem statement with stakeholders, constraints, and success criteria. No code touched.

## B.2 Research Process — "Has anyone solved this before?" (gated)

**Trigger:** `/research` (auto-suggested by classifier) OR user invokes when novelty is known
**Phase marker:** `.current_phase = research`
**Budget:** 120K tokens (largest — scanning codebase + external sources)

**Flow:**
1. `research-prior-art-scanner` runs as background agent: scans local codebase, git history, and (if `networkMode: online`) web sources
2. `research-spike-planner` produces a time-boxed spike plan with explicit hypotheses and kill-switches
3. User runs spikes; results written to `docs/research/<topic>/findings.md`
4. Decision gate: proceed to `/design` with prior art, or reject approach and restart `/discover`

**Exit:** prior-art report + spike findings. Still no production code.

## B.3 Design Process — "What's the architecture?"

**Trigger:** `/design <objective>` or `/plan <objective>`
**Phase marker:** `.current_phase = design`
**Budget:** 100K tokens

**Flow:**
1. `design-brainstormer-advisor` (opus max) generates 2-3 alternative approaches with trade-offs
2. User selects one
3. `design-requirements-analyst` formalises functional + non-functional requirements
4. `design-architecture-reviewer` (blocking, opus max) validates against SOLID, Clean Architecture, layer boundaries — **halts if layering violates**
5. `design-api-contract-designer` designs interface boundaries (OpenAPI/tRPC)
6. `design-schema-designer` designs data model + migration strategy
7. `security-threat-modeler` runs STRIDE analysis against the proposed design
8. `doc-adr-writer` captures the decision as an ADR
9. Outputs written to `docs/design/<topic>/architecture.md`, `docs/design/<topic>/adr-NNN.md`

**Exit:** approved architecture doc + ADR + API contracts + threat model. Blocking reviewers must pass.

## B.4 Develop Process — "Write the code (TDD)"

**Trigger:** `/scaffold <module>` → `/tdd <objective>`
**Phase marker:** `.current_phase = develop`
**Budget:** 30K (scaffold) / 60K (tdd)

### B.4.1 Scaffold sub-process
1. `meta-folder-structure-advisor` validates target directory structure
2. `meta-filename-advisor` validates target filenames against profile conventions
3. `/scaffold` reads architecture doc + creates stub file (method bodies `...`) + comprehensive test skeleton
4. Tests must be RED (all FAIL, not ERROR) — enforced
5. Session-state updates with scaffold presence

### B.4.2 TDD sub-process (`/tdd <objective>`)
1. **DETECT SCAFFOLD**: look for existing `tests/unit/test_<module>.py` etc.
2. **RUN TESTS**: classify state — ALL PASS (skip to refactor), ALL FAIL (→ GREEN), MIXED (→ GREEN), ERROR (→ fix)
3. **DESIGN TESTS** (if no scaffold): generate test categories (unit, property, deterministic)
4. **RED**: write tests first; verify every test FAILs (not errors); max 3 attempts
5. **GREEN**: minimal implementation; tests are spec, do not modify
   - After each edit: `post_edit_lint.py` runs ruff/mypy (or eslint/tsc)
   - `post_auto_format.py` applies formatter
   - `track_changed_files.py` updates orchestrator state
6. **REFACTOR**: simplification pass
   - `py-code-simplifier` or `fe-code-simplifier` advises
   - `py-doc-checker` or `fe-doc-checker` auto-fix docs
7. **VALIDATE**: invoke `/validate` sub-process (B.5)
8. **SUMMARY**: structured report

**Background during develop:** `bg-codebase-pattern-sweep`, anti-pattern detectors, `security-sbom-generator` run asynchronously.

**Exit:** code that passes all validation, with tests that are RED before GREEN, and stamps written.

## B.5 Validate Process — "Is this code actually good?"

**Trigger:** `/validate` (auto-invoked at end of `/tdd`, `/refactor`; manually before commit)
**Phase marker:** `.current_phase = validate`
**Budget:** 50K tokens

**Flow (per-language, parallel where possible):**

**Step 0 — Auto-detect:** `detect_language.py` reads staged files → determines which gates to run (python, frontend, agents, database, api).

**Python gate (11 steps — if Python files staged):**
1. `run_cli_checks.py` runs 4 parallel CLI: ruff check, ruff format, mypy --strict, pytest
2. `validation-objective-verifier` (blocking, opus max): git diff vs stated objective
3. `py-solid-dry-reviewer` (blocking)
4. `py-security-reviewer` (blocking)
5. `py-doc-checker` (auto-fixer) — if it edits files, re-run step 1 (max 1 cycle)
6. `py-arch-doc-reviewer` (blocking)
7. `py-code-simplifier` (blocking)
8. `py-tdd-process-reviewer` (advisory — recorded but doesn't block)
9. If all pass: `stamp_validation.py` writes `.validation_stamp` with `{timestamp, branch, steps, ttl=15min}`

**Frontend gate (7 steps — if frontend files staged):**
1. Parallel CLI: eslint, tsc --strict, vitest
2. `fe-code-simplifier` (blocking)
3. `fe-security-reviewer` (blocking)
4. `fe-doc-checker` (auto-fixer)
5. `fe-component-reviewer` (advisory)
6. If all pass: writes `.frontend_validation_stamp`

**Agent gate (2 steps — if `.claude/` files staged):**
1. `meta-agent-arch-doc-reviewer`
2. `meta-command-composition-reviewer`
3. Writes `.agent_validation_stamp`

**Database gate (2 steps — if migration files staged):**
1. `db-schema-reviewer`
2. `db-migration-safety-reviewer`
3. Writes `.db_validation_stamp`

**API gate (2 steps — if API route files staged):**
1. `api-contract-reviewer`
2. `api-type-boundary-reviewer`
3. Writes `.api_validation_stamp`

**Cross-cutting (every validate run):**
- `testing-pyramid-enforcer` (blocking)
- `testing-coverage-per-layer-reviewer` (blocking)
- `testing-impact-analyzer` (advisory)
- `security-secret-scanner` (blocking — runs as PreToolUse hook too)
- `security-sast-runner` (blocking)
- `security-license-compliance` (blocking)
- `validation-completion-verifier` (blocking) — enforces no claims without evidence
- `meta-sycophancy-detector` (BG)

**Telemetry emit:** every agent invocation produces a telemetry record.

**On commit attempt (`git commit`):**
- `pre_commit_cli_gate.py` (fast): checks all required stamps exist, valid, fresh (<15min), branch matches
- `pre_commit_agent_gate.py` (hook type `agent`): invokes `validation-completion-verifier` for final review
- Bypasses: `[WIP]` in message, `.git/MERGE_HEAD` exists
- Otherwise: commit blocked

**Exit:** stamped, committed, telemetry recorded.

## B.6 Test Process — "Beyond gate-passing, is the test strategy sound?"

**Trigger:** `/typecheck`, or test-related CI
**Phase marker:** `.current_phase = test`

**Flow:**
1. `testing-pyramid-enforcer` validates unit:integration:e2e ratio per profile
2. `testing-coverage-per-layer-reviewer` validates per-layer coverage thresholds
3. `testing-impact-analyzer` traces changed files → tests to run (optimization)
4. `testing-regression-generator` generates tests for new bug fixes
5. Background: `testing-flake-detector` and `testing-mutation-runner`

**Exit:** a healthy test pyramid with bounded flakiness and mutation score.

## B.7 Deploy Process — "Ship it safely"

**Trigger:** `/release` or CI trigger
**Phase marker:** `.current_phase = deploy`
**Budget:** 30K tokens

**Flow:**
1. `deploy-release-reviewer` validates changelog, version bump, breaking-change detection
2. `deploy-migration-sequence-reviewer` validates migration ordering + rollback plans
3. `deploy-canary-advisor` proposes canary rollout with rollback triggers
4. Post-deploy: `deploy-smoke-runner` executes smoke tests

**Exit:** tagged release, canary healthy, rollback path proven.

## B.8 Operate Process — "Something's broken in prod"

**Trigger:** `/incident <description>` or SLO alert
**Phase marker:** `.current_phase = operate`
**Budget:** 80K tokens (big — incident context is expensive)

**Flow:**
1. `operate-incident-responder` (opus max) runs the 4-phase debug loop: Observe, Hypothesise, Test, Fix
2. `operate-slo-monitor` provides telemetry context
3. `operate-runbook-executor` walks applicable runbook with validation at each stage
4. Incident record written to `${CLAUDE_PLUGIN_DATA}/framework-memory/incidents/`
5. `doc-runbook-writer` updates runbook from resolution steps
6. Postmortem triggers `closed-loop-incident-retrospective-analyst` in next weekly run

**Exit:** incident closed, runbook updated, lessons captured in framework memory.

## B.9 Maintain Process — "Keep the lights on"

**Trigger:** `/maintain` or scheduled
**Phase marker:** `.current_phase = maintain`

**Flow:**
1. `maintain-dependency-updater` (auto-fixer, worktree) bumps dependencies, runs tests
2. `maintain-deprecation-scanner` (background) detects deprecated API usage
3. `maintain-flake-detector` (background) long-horizon flake analysis
4. `security-dep-vuln-scanner` runs alongside
5. Produced PRs validated through normal Validate process (B.5)

**Exit:** healthy dependency graph, no deprecated usage, low flake rate.

## B.10 Document Process (cross-cutting)

**Trigger:** `/document <mode>` where mode is `adr|runbook|sequence|onboarding`
**Phase marker:** inherits current phase

**Flow:**
- ADR: `doc-adr-writer` from design context
- Runbook: `doc-runbook-writer` from code + operational history
- Sequence: `doc-sequence-diagrammer` from code traces
- Onboarding: `doc-onboarding-writer` from current architecture

All outputs validated by `py-arch-doc-reviewer` or equivalent language reviewer.

## B.11 Closed-Loop Process (background, continuous)

**Trigger:** Scheduled via `ScheduleWakeup` at cache-safe intervals

**Flow:**
1. **Every agent invocation** → `subagent_summary.py` emits telemetry JSONL
2. **Every failure** → `stop_failure.py` / `post_tool_failure.py` / `permission_denied.py` write incident records
3. **Every 70% context budget** → `closed-loop-context-rolling-summarizer` compresses old turns
4. **Nightly** → `closed-loop-quality-scorer` updates per-agent precision/recall/latency/cost
5. **Weekly** → `closed-loop-incident-retrospective-analyst` clusters incidents → proposes prompt/rule diffs as PRs
6. **Monthly** → `closed-loop-knowledge-compactor` promotes agent memories → principles → candidate rules
7. User reviews PRs via `/new-rule`; accepted changes flow into next plugin release

**Exit:** framework improves over time without manual intervention.

---

# Appendix C — Command → Agent Orchestration Map

Each of the 27 commands below composes a specific set of agents. Commands own the orchestration; agents own the judgment.

| Command | Phase | Agents composed | Output |
|---|---|---|---|
| `/discover` | Discover | `discover-requirements-elicitor`, `discover-stakeholder-mapper` | `docs/discover/<topic>/` |
| `/research` | Research | `research-prior-art-scanner`, `research-spike-planner` | `docs/research/<topic>/` |
| `/design` | Design | `design-brainstormer`, `design-requirements-analyst`, `design-architecture-reviewer`, `design-api-contract-designer`, `design-schema-designer`, `security-threat-modeler`, `doc-adr-writer` | `docs/design/<topic>/` + ADR |
| `/plan` | Design | `design-requirements-analyst`, `design-architecture-reviewer` | Implementation plan with tasks |
| `/scaffold` | Develop | `meta-folder-structure-advisor`, `meta-filename-advisor`, stub + test skeleton generator | Scaffolded module (RED state) |
| `/tdd` | Develop | `py-*` or `fe-*` stack agents, CLI runners, `validation-objective-verifier` | Working code, stamps written |
| `/fix` | Develop | `operate-incident-responder` (for debugging), stack reviewers | Bug fix + regression test |
| `/debug` | Develop | 4-phase debug loop with `operate-incident-responder` | Root cause + fix |
| `/pattern [<name>]` | Develop | Relevant `pattern-*-advisor` | Pattern scaffold in target language |
| `/pattern-scan` | Develop | All `antipattern-*-detector` (BG) | Anti-pattern report |
| `/refactor` | Develop | `refactor-detector`, `refactor-planner`, `refactor-applier` (worktree) | Refactored code in worktree |
| `/typecheck` | Test | CLI runners per profile, `testing-pyramid-enforcer` | Type error report + pyramid status |
| `/validate` | Validate | Full validate gate per profile (see B.5) | Stamps written |
| `/validate-agents` | Validate | `meta-agent-arch-doc-reviewer`, `meta-command-composition-reviewer`, `meta-graph-registry-validator` | `.agent_validation_stamp` |
| `/security-scan` | Validate | `security-sast-runner`, `security-secret-scanner`, `security-dep-vuln-scanner`, `security-license-compliance`, `security-sbom-generator` | Security report |
| `/review` | Validate | Delegates to domain agents based on file types | Code review |
| `/document [mode]` | Document | `doc-adr-writer`, `doc-runbook-writer`, `doc-sequence-diagrammer`, or `doc-onboarding-writer` | Documentation artifact |
| `/release` | Deploy | `deploy-release-reviewer`, `deploy-migration-sequence-reviewer`, `deploy-canary-advisor` | Tagged release |
| `/incident` | Operate | `operate-incident-responder`, `operate-slo-monitor`, `operate-runbook-executor` | Incident record + runbook update |
| `/maintain` | Maintain | `maintain-dependency-updater`, `maintain-deprecation-scanner`, `maintain-flake-detector` | Dependency PR, deprecation report |
| `/handoff` | Lifecycle | Session state writer (haiku) | `MEMORY.md` + `session-state.md` |
| `/status` | Lifecycle | Session state reader (haiku) | Current state report |
| `/logs` | Lifecycle | Session activity viewer (haiku) | Log dump |
| `/setup` | Lifecycle | `detect_language.py`, profile initializer | `.language_profile.json` |
| `/escalate` | Meta | `meta-conflict-resolver` or human handoff | Resolved verdict or human briefing |
| `/feedback` | Meta | Incident log writer (explicit user signal) | Feedback record |
| `/new-agent` | Meta | `meta-agent-scaffolder`, `meta-agent-arch-doc-reviewer`, `meta-graph-registry-validator`, `meta-primitive-selection-reviewer` | New agent file + registry update |
| `/new-command` | Meta | `meta-command-scaffolder`, `meta-command-composition-reviewer` | New command file |
| `/new-hook` | Meta | `meta-hook-scaffolder` + hook test suite | New Python hook + tests |
| `/new-rule` | Meta | Rule review + placement | New rule file with frontmatter |
| `/telemetry` | Meta | `bin/dsp-telemetry` wrapper | Telemetry export |

---

## What This Appendix Lets You Verify

You should now be able to answer, for any scenario:

1. **"If I want to add a new feature to my monorepo, which agents fire?"** — Walk through B.1 Discover → B.3 Design → B.4 Develop → B.5 Validate.
2. **"What catches a SQL injection vulnerability before commit?"** — `security-secret-scanner` (in diff), `py-security-reviewer` (in code review), `security-sast-runner` (in validate gate). Three-layer defence.
3. **"What prevents me from merging a schema change without a rollback plan?"** — `db-migration-safety-reviewer` blocks in the database gate; `deploy-migration-sequence-reviewer` blocks at release.
4. **"How does the framework learn from its mistakes?"** — B.11 Closed-Loop Process: telemetry + incidents → nightly scoring → weekly retrospective PRs → monthly principle extraction → new rules.
5. **"What happens if an agent times out in the middle of validation?"** — `post_tool_failure.py` records incident; `meta-conflict-resolver` is not invoked (single failure); gate fails; user must re-run. Recovery is explicit, not silent.
6. **"What does the framework not cover?"** — Deliberately out-of-scope: project management (Jira/Linear integration), contract negotiation (legal), human performance review. The framework covers *code lifecycle*, not *team lifecycle*.

If any answer above surprises you, that's the place to push back before approving the plan.

---

# Appendix D — Bootstrap-First Sequencing + Worktree Discipline

**Amendment status:** approved 2026-04-11, after reflection on the Modelling session lifecycle. Does not change component definitions, taxonomy, PSF, memory tiers, closed-loop architecture, or strict-default. **Only changes Phase 0-11 sequencing and introduces the worktree workflow.**

## D.1 Why This Amendment Exists

The main body of this plan sequences phases *horizontally* — all shared modules, then all hooks, then graph registry, then agents. First usable framework state lands at the end of Phase 6 (~13 weeks in). That's backwards for a framework whose entire purpose is dogfooding. A framework that cannot enforce its own rules on its own construction is a static linter in disguise.

The revised shape is: **build the minimum viable self-hosting lifecycle FIRST (Phase 1 Bootstrap Spike), then use it to build everything else, in worktrees, on feature branches, through the framework's own gate.** Every commit to `dev-standards-plugin` from Phase 2 onwards passes through `dev-standards-plugin`'s own hooks, agents, and stamp gate. Every new component is a validated, stamped, closed unit of work. Retrospective data accumulates from the first dogfooded commit.

## D.2 The Ten Mechanisms (Modelling's Essence)

The bootstrap implements these ten interlocking mechanisms — nothing less is self-hosting, nothing more is required:

1. **Session state round-trip** — `pre_compact` + `session_end` write `session-state.md`; `session_start` reads it, extracts `- [ ]` / `- [~]` todos, instructs Claude to restore via TodoWrite. Archives to `.injected` (rename, not delete).
2. **Transcript parsing** — `extract_from_transcript()` recovers modified_files, errors, recent reasoning from the JSONL transcript.
3. **Auto-feature-branch** — first edit on protected branch triggers `create_feature_branch.py` to cut `feat/<category>-<slug>`.
4. **Branch protection** — Edit/Write on protected branches blocked by `branch_protection.py` before the tool runs.
5. **Independent validation stamps** with 15-minute TTL, branch-specific. Switching branch or letting time pass invalidates.
6. **Stamp-enforced commit gate** — `pre_commit_cli_gate.py` exits 2 on missing/stale/wrong-branch/wrong-steps stamp. Only bypasses: `[WIP]` prefix, `.git/MERGE_HEAD`.
7. **Language-aware multi-gate** — which stamps are required is determined by *which files are staged*. No explicit routing.
8. **Auto-fixer re-validation cycle** — capped at 1 cycle to prevent runaway loops.
9. **Persistent agent memory via Bash helper** — read-only agents learn across sessions via `write_agent_memory.py`; path-validated.
10. **Single source of truth for validation steps** — `PY_VALIDATION_STEPS`, `FE_VALIDATION_STEPS`, `AGENT_VALIDATION_STEPS` tuples in `_hook_shared.py`, referenced everywhere.

## D.3 Minimum Viable Bootstrap (~31 files)

The smallest self-hosting set. Anything beyond this is Phase 2+, built *via* this.

### D.3.1 Shared modules (5)
| File | Purpose |
|---|---|
| `hooks/_os_safe.py` | Atomic write, portalocker lock, safe_join, normalize_path, temp lifecycle |
| `hooks/_hook_shared.py` | Validation step tuples, cache intervals, budgets, project dir helper, branch reader, `read_hook_input()` |
| `hooks/_session_state_common.py` | `write_session_state()`, `extract_from_transcript()`, memory dir resolver, todo extraction |
| `hooks/stamp_validation.py` | Stamp writer (code/agent/frontend), 15-min TTL, branch-specific, JSON-schema-validated |
| `hooks/write_agent_memory.py` | Path-safe memory writer; stdin content, `--agent <name>`, `--append` |

### D.3.2 Core hooks (12)
| Event | Hook | Role |
|---|---|---|
| SessionStart | `session_start.py` | Reinject state, restore todos |
| SessionEnd | `session_end.py` | Save state |
| PreCompact | `pre_compact.py` | Preserve state before compaction |
| PostCompact | `post_compact.py` | Verify + cleanup stale state |
| UserPromptSubmit | `create_feature_branch.py` | Auto-branch from protected |
| UserPromptSubmit | `context_budget.py` | 80% warn, 95% critical |
| PreToolUse (Edit\|Write) | `branch_protection.py` | Block on protected branches |
| PreToolUse (Bash) | `pre_commit_cli_gate.py` | Stamp enforcement on `git commit` |
| PreToolUse (Bash) | `dangerous_command_block.py` | Block destructive commands |
| PostToolUse (Edit\|Write) | `post_edit_lint.py` | Language-aware lint |
| PostToolUse (Edit\|Write) | `post_auto_format.py` | Language-aware format |
| PostToolUseFailure | `post_tool_failure.py` | Telemetry seed |

### D.3.3 Core commands (3)
| Command | Purpose |
|---|---|
| `/validate` | Run gate: CLI checks → subagent review → stamp write |
| `/handoff` | Write MEMORY.md + session-state.md |
| `/setup` | Detect language, write `.language_profile.json` |

### D.3.4 Core agents (5)
| Agent | Type | Why in bootstrap |
|---|---|---|
| `meta-agent-scaffolder` | F (worktree) | Scaffolds the remaining 136 agents |
| `meta-graph-registry-validator` | B | Registry is derived — needs validation every commit |
| `meta-command-composition-reviewer` | B | Prevents duplication as commands are added |
| `validation-objective-verifier` | B | Blocks scope drift on every framework commit |
| `validation-completion-verifier` | B | Blocks "done" claims without evidence |

### D.3.5 Schemas (4)
`graph-registry.schema.json`, `stamp.schema.json`, `agent-frontmatter.schema.json`, `profile.schema.json`.

### D.3.6 Profiles (2)
`python.json`, `javascript.json` — minimum for linting the plugin's own code.

### D.3.7 Graph registry
Only bootstrap nodes (~27 components). Auto-generated by `scripts/build-graph-registry.py`.

### D.3.8 Tooling (2)
| Script | Purpose |
|---|---|
| `scripts/build-graph-registry.py` | Distributed manifests → monolithic registry |
| `scripts/bootstrap-smoke.py` | End-to-end self-validation test |

**Total: ~31 files.** Phase 1 exit when `bootstrap-smoke.py` passes.

## D.4 Phase 1 Exit Gate — `bootstrap-smoke.py`

Non-negotiable. Phase 2 does not begin until all eight assertions pass:

1. `/validate` runs cleanly against the bootstrap's own code
2. A deliberate scope violation (diff outside stated objective) is blocked by `validation-objective-verifier`
3. A commit *without* a stamp is blocked by `pre_commit_cli_gate.py` (exit 2)
4. A commit *with* a valid, fresh, branch-matched stamp succeeds
5. A stamp older than 15 minutes blocks a commit attempt
6. A `[WIP]` commit bypasses the gate
7. A `.git/MERGE_HEAD` bypass works during conflict resolution
8. `write_agent_memory.py --agent ../../etc/passwd` is rejected (path traversal protection)

Also required before Phase 2:
- `_os_safe.py` unit tests pass on Windows *and* Unix CI
- `build-graph-registry.py` rebuilds registry from manifests and `meta-graph-registry-validator` passes
- `meta-agent-scaffolder` successfully scaffolds a dummy agent (`agents/test/throwaway-scaffold-test.md`), validation passes, and the throwaway is removed in the same branch

## D.5 Worktree Discipline

### D.5.1 Invariants (enforced by bootstrap hooks from Phase 2 onwards)
- Never commit to `master` directly (`branch_protection.py`)
- Every feature gets `feat/<category>-<slug>` (`create_feature_branch.py`)
- Every feature is developed in its own worktree under `C:\Users\jmarks01\Projects\dsp-worktrees\`
- Every commit passes the stamp gate
- Branch merged → worktree removed → retrospective data captured

### D.5.2 Workflow per feature

```
git worktree add C:/Users/jmarks01/Projects/dsp-worktrees/feat-<slug> -b feat/<slug> master
cd C:/Users/jmarks01/Projects/dsp-worktrees/feat-<slug>
# work — the INSTALLED plugin (from master) gates this work
/validate                     # runs against worktree; writes stamp
git add <files>
git commit -m "..."           # pre_commit_cli_gate verifies stamp
git push -u origin feat/<slug>
# open PR → merge to master
cd C:/Users/jmarks01/Projects/dev-standards-plugin
git pull
git worktree remove C:/Users/jmarks01/Projects/dsp-worktrees/feat-<slug>
# if the merge changed the plugin, re-install from master
```

### D.5.3 Key insight

The **installed plugin is always the known-good master copy**. Worktrees are *workspaces* for in-progress features. Validation uses the installed master gate to validate code that will eventually replace it. The framework remains stable while modifying itself.

### D.5.4 Parallel worktrees

Multiple worktrees progress simultaneously without branch-switching overhead. Example parallel set at start of Phase 1:

```
dsp-worktrees/
├── feat-bootstrap-os-safe/              # _os_safe.py + tests
├── feat-bootstrap-hook-shared/          # _hook_shared.py + _session_state_common.py
├── feat-bootstrap-stamp-validation/     # stamp_validation.py + write_agent_memory.py
├── feat-bootstrap-hooks-core/           # 12 core hooks
├── feat-bootstrap-commands-core/        # /validate, /handoff, /setup
└── feat-bootstrap-agents-core/          # 5 meta/validation agents
```

Dependencies (Phase 1 internal topology):
```
_os_safe.py
    ↓
_hook_shared.py ── _session_state_common.py
    ↓                        ↓
stamp_validation.py ── write_agent_memory.py
    ↓
12 core hooks (parallel)
    ↓
/validate, /handoff, /setup (parallel)
    ↓
5 core agents (parallel) + bootstrap-smoke.py (serial, last)
```

### D.5.5 `bin/dsp-wt` helper (added in Phase 1)

Small Python wrapper (~100 lines) encoding the workflow:

```
dsp-wt create <slug>           # git worktree add + branch
dsp-wt list                    # show active worktrees + branch + stamp status
dsp-wt close <slug>            # validate + push + (suggest PR) + local cleanup on merge
dsp-wt cleanup                 # remove merged worktrees
```

Added to plugin `bin/` so it's on PATH while the plugin is enabled.

### D.5.6 Retrospective payoff

- `git log --first-parent master` reads as the development history
- Every merged branch carries its stamps in the commit metadata (or attached incident record)
- `closed-loop-incident-retrospective-analyst` (Phase 10) has real data from day one
- Quality scoring (Phase 4 in the revised sequencing) starts accumulating immediately

## D.6 Revised Phase Sequencing

This amendment replaces the phase sequencing in §10 of the main plan. Component definitions, counts, and architecture are unchanged.

| Phase | Name | Duration | Delivers | How built |
|---|---|---|---|---|
| **0** | Architecture Lockdown (minimal) | 1 wk | Bootstrap spec + 4 foundational schemas (graph-registry, stamp, agent-frontmatter, profile) + `docs/architecture/README.md`. Minimal docs — only what the bootstrap requires. | Branch `feat/architecture-lockdown`; hand-written; pre-bootstrap commits explicitly exempt |
| **1** | **Bootstrap Spike** | 3 wks | The ~31 files in D.3. `dev-standards-plugin` validates its own commits via its own hooks, agents, gate. `bootstrap-smoke.py` passes all 8 assertions. | Multiple parallel `feat/bootstrap-*` worktrees per D.5.4; first pass manually tested with pytest + explicit git commands; self-hosting is the exit gate |
| **2** | Hook Completion | 2 wks | Remaining 24 hooks (the ones beyond the bootstrap 12) | Via bootstrap gate; each hook in its own worktree |
| **3** | Language Profiles | 1 wk | `typescript.json`, `fullstack.json`, Rust/Go/Kotlin placeholders | Via bootstrap gate |
| **4** | Telemetry + Memory Infrastructure | 2 wks | 4-tier memory, `${CLAUDE_PLUGIN_DATA}`, telemetry emit/consume, incident log, `closed-loop-quality-scorer`. **Moved earlier: observability before agent expansion.** | Via bootstrap gate |
| **5** | Core Agent Refactor | 2 wks | Refactor existing 13 agents into new taxonomy with frontmatter, confidence field, worktree isolation where applicable | Via bootstrap gate + `meta-agent-scaffolder` |
| **6** | TDD Workflow + Stack Agents | 3 wks | `/scaffold`, `/tdd`, `/fix`, `/debug`, `/typecheck`; Python stack (9), Frontend stack (7), Interface (3), Database (3). Full 3-stamp model with language routing. | Via bootstrap gate, scaffolded by meta-agents |
| **7** | Design + Discover + Research | 2 wks | Design (5), Discover (2), Research (2). `/design`, `/plan`, `/discover`, `/research`. | Via bootstrap gate |
| **8** | Patterns + Anti-patterns + Refactor | 3 wks | 54 patterns + 8 antipatterns + 3 refactor. `/pattern`, `/refactor`, `/pattern-scan`. | Phased by pattern category; each category in its own worktree |
| **9** | Security + Testing Strategy + Documentation | 2 wks | Security (6), testing (6), document (4). `/document`, `/security-scan`. | Via bootstrap gate |
| **10** | Operate + Maintain + Closed Loop + MCP | 3 wks | Operate (3), maintain (3), closed-loop (4), 4 MCP servers, 4 `bin/` tools (incl. `dsp-wt` enhancements). Retrospective analyst goes live. | Via bootstrap gate; MCP servers in their own worktrees |
| **11** | Polish, Marketplace, Multi-language | 2 wks | Rust/Go/Kotlin activated, interop agent, channels, offline bundle, team mode, marketplace listing | Via bootstrap gate |

**Total:** ~26 weeks. **First usable state:** end of Phase 1 (~4 weeks) — dramatically earlier than the original Phase 6 (~13 weeks).

### D.6.1 Phase exit gates (dogfooding applied to phases)

- **Phase 0 exit:** all 4 foundational schemas validate against themselves; bootstrap spec is one-page scannable; `docs/architecture/README.md` points to this plan.
- **Phase 1 exit:** `bootstrap-smoke.py` passes (D.4).
- **Phase 2+ exit:** the phase's own output passes the framework's own gate. If a phase adds an agent, that agent must be validated by the meta-agents before the phase is marked complete.

### D.6.2 What "pre-bootstrap" means

Phase 0 and the *first pass* of Phase 1 commits are pre-bootstrap — the gate doesn't exist yet. These commits are explicitly recorded as historical in the incident log once the gate goes live, but they are not policy going forward. From Phase 1 exit onwards, every commit is gated.

## D.7 Branching Convention

**Immediate cleanup:** merge `docs/update-readme-v1.4.0` into `master` (user action via existing PR) before Phase 0 begins. That branch is v1.4.0-scoped and should not entangle with v2 work.

**From Phase 0 onwards:**
- `master` = integration branch; all features merge here
- Branches = `feat/<category>-<slug>` (examples: `feat/architecture-lockdown`, `feat/bootstrap-os-safe`, `feat/hook-post-compact`, `feat/agent-py-security-reviewer`, `feat/pattern-strategy`)
- Worktrees under `C:\Users\jmarks01\Projects\dsp-worktrees\`
- One branch per functional element; no "phase branches"
- PRs open per branch, validated by gate, merged to `master`, worktree removed

**First concrete branches:**
1. `feat/architecture-lockdown` (serial, Phase 0) — bootstrap spec + foundational schemas + architecture README
2. `feat/bootstrap-os-safe` (parallel, Phase 1) — `_os_safe.py` + unit tests (Windows + Unix CI)
3. `feat/bootstrap-hook-shared` (parallel, Phase 1) — `_hook_shared.py` + `_session_state_common.py` (depends on `_os_safe`)
4. `feat/bootstrap-stamp-validation` (serial after 3, Phase 1) — `stamp_validation.py` + `write_agent_memory.py`
5. `feat/bootstrap-hooks-core` (parallel after 4, Phase 1) — 12 core hooks
6. `feat/bootstrap-commands-core` (parallel after 4, Phase 1) — `/validate`, `/handoff`, `/setup`
7. `feat/bootstrap-agents-core` (parallel after 4, Phase 1) — 5 meta/validation agents
8. `feat/bootstrap-smoke` (serial, last, Phase 1) — `bootstrap-smoke.py` exit-gate test

## D.8 Risks Specific to the Restructure

| Risk | Mitigation |
|---|---|
| Bootstrap bugs cascade to all subsequent phases | Phase 1 exit gate (D.4) is non-negotiable; `bootstrap-smoke.py` is the objective test |
| Chicken-and-egg (the hook that validates the hook) | First bootstrap pass is manually tested with pytest + explicit git commands. Self-validation is the *exit* gate, not the *development* gate |
| Scope creep in Phase 1 | The ~31-file list is a contract; additions require Phase 0 re-scope, not Phase 1 slip |
| Worktree confusion | `bin/dsp-wt` wrapper added in Phase 1 + `docs/workflows/worktree-discipline.md` |
| Installed-plugin vs worktree drift | `/validate` reads `${CLAUDE_PLUGIN_ROOT}`, asserts it's the installed master version, warns on mismatch |
| Pre-bootstrap commits cannot be gated | Explicitly exempt and recorded in incident log as historical once gate is live |
| Existing `lib/` is JavaScript; bootstrap adds Python | Both languages validated by respective profiles from Phase 2; dogfoods multi-language from day one |
| Approved plan (`cozy-doodling-church.md`) is already approved — is this a rewrite? | No. Appendix D is a *sequencing amendment*; architecture, taxonomy, counts, PSF, memory tiers, and closed-loop design are unchanged |

## D.9 What Appendix D Commits To

- **Bootstrap-first sequencing:** Phase 1 delivers the ~31-file self-hosting lifecycle in 3 weeks; first usable state at ~4 weeks total instead of ~13
- **Phase 1 exit gate:** `bootstrap-smoke.py` with 8 non-negotiable assertions
- **Worktree discipline:** one branch per functional element, parallel worktrees, `bin/dsp-wt` helper
- **Retrospective-ready from day one:** every dogfooded commit produces stamps, incidents, telemetry fodder
- **`master` clean-up first:** `docs/update-readme-v1.4.0` merged before Phase 0 begins
- **No changes** to the approved architecture, component counts, PSF, memory tiers, closed-loop design, or strict default
- **Telemetry moved earlier** (Phase 4 in revised sequencing, vs. Phase 5 in the original) because observability must land before the large agent populations of Phases 6-10

Next action after this appendix: proceed to Phase 0 with `feat/architecture-lockdown`, beginning only once `docs/update-readme-v1.4.0` is merged to `master`.

---

# Appendix E — Phase 0 Execution Specifications

**Status:** ready to execute. PR #7 merged to `master` (`1db361a`). `docs/update-readme-v1.4.0` cleanup complete. This appendix is the per-file specification for Phase 0 deliverables — schema shapes, required fields, validation criteria, acceptance tests. When plan mode exits, execution follows this appendix line-by-line.

## E.1 Branch & Workflow

- **Branch:** `feat/architecture-lockdown` cut off `master` (`1db361a`)
- **Worktree:** not used in Phase 0 (pre-bootstrap, single branch, no parallel work yet)
- **Gate:** no gate yet (bootstrap doesn't exist); Phase 0 commits are explicitly pre-bootstrap and exempt. This will be recorded in the incident log as historical once the gate goes live in Phase 1.
- **Commit style:** conventional commits per existing repo convention. Prefix: `docs(architecture):` or `chore(schemas):`.

## E.2 Deliverable Map

| # | Task | File | Lines (target) | Depends on |
|---|---|---|---|---|
| 14 | graph-registry schema | `schemas/graph-registry.schema.json` | ~200 | none |
| 15 | stamp schema | `schemas/stamp.schema.json` | ~80 | none |
| 16 | agent-frontmatter schema | `schemas/agent-frontmatter.schema.json` | ~150 | none |
| 17 | profile schema | `schemas/profile.schema.json` | ~180 | none |
| 18 | architecture README | `docs/architecture/README.md` | ~120 | none |
| 19 | bootstrap spec | `docs/architecture/bootstrap-spec.md` | ~200 | 14-17 (references schemas) |
| 20 | Phase 0 exit verification | (no new file) | — | 14-19 |

All six can be written in any order; #19 references the schemas by path so #14-17 should exist first but their content isn't strictly required.

## E.3 Schema 1 — `schemas/graph-registry.schema.json`

**Purpose:** JSON Schema (draft-2020-12) that validates the derived `config/graph-registry.json` produced by `scripts/build-graph-registry.py` from distributed component manifests.

**Top-level shape:**
```
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://dev-standards-plugin/schemas/graph-registry.schema.json",
  "title": "Dev Standards Plugin Graph Registry",
  "type": "object",
  "required": ["version", "generated_at", "nodes", "edges"],
  "properties": {
    "version": "string (semver)",
    "generated_at": "string (ISO-8601)",
    "source_commit": "string (git sha)",
    "nodes": "array of GraphNode",
    "edges": "array of GraphEdge"
  }
}
```

**`GraphNode` required fields** (per plan §4.1 + Appendix D additions):
- `id` — string, unique within registry, pattern `^[a-z0-9][a-z0-9-]*$`
- `type` — enum: `Agent | Command | Hook | Skill | Rule | Gate | Profile | Template | MCPServer | BinTool | OutputStyle`
- `category` — string, kebab-case (e.g., `design`, `meta`, `patterns/behavioural`)
- `metadata` — object (type-specific sub-schema via `oneOf`)
- `scope` — optional, one of `core | profile-scoped | conditional`
- `owner` — optional, string (for team mode)

**`GraphEdge` required fields** (per §4.2 + §4.2 additions in main plan):
- `from` — node id
- `to` — node id
- `type` — enum: `triggers | validates | depends-on | produces | consumes | gates | composes | scoped-by | escalates-to | observed-by | derives-principle-from | overridden-by`
- `contract` — string, name of interface contract (e.g., `AgentVerdict`, `HookInput`)
- `weight` — optional, number 0.0-1.0 (for priority ordering)
- `confidence` — optional, number 0.0-1.0

**Constraints (JSON Schema `allOf` rules):**
- Every edge's `from` and `to` must reference existing node ids (soft validation — validator script cross-checks)
- No node can appear twice with the same id
- No two edges can have identical `(from, to, type)` tuple

**Per-type metadata sub-schemas** (use `oneOf` on `type`):
- **Agent:** `{agent_type: blocking|auto-fixer|advisory|background, model: opus|sonnet|haiku, effort?, tools: str[], memory: project|local|none, maxTurns, isolation?, background?}`
- **Hook:** `{event: SessionStart|..., matcher?: str, timeout_ms: int, blocking: bool}`
- **Command:** `{context: fork|none, model, allowed_tools: str[], phase: str}`
- **Profile:** `{detection: {markers: str[], extensions: str[]}, priority: P0|P1|P2|P3}`
- (others minimal for Phase 0; expanded in Phase 3)

**Acceptance:**
- Self-validates (schema validates against itself using any JSON Schema draft-2020-12 validator)
- A minimal example registry with 2 nodes + 1 edge validates successfully
- A registry with an edge referencing a non-existent node id is caught by the accompanying cross-check (documented, not enforced by JSON Schema alone)

## E.4 Schema 2 — `schemas/stamp.schema.json`

**Purpose:** validates the five stamp files (`.validation_stamp`, `.frontend_validation_stamp`, `.agent_validation_stamp`, `.db_validation_stamp`, `.api_validation_stamp`). Written by `stamp_validation.py` in Phase 1; consumed by `pre_commit_cli_gate.py` in Phase 1.

**Shape:**
```
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://dev-standards-plugin/schemas/stamp.schema.json",
  "title": "Validation Stamp",
  "type": "object",
  "required": ["timestamp", "branch", "steps", "ttl_seconds", "version", "gate"],
  "properties": {
    "timestamp": { "type": "string", "format": "date-time" },
    "branch": { "type": "string", "minLength": 1 },
    "steps": { "type": "array", "items": { "type": "string" }, "minItems": 1 },
    "ttl_seconds": { "type": "integer", "const": 900 },
    "version": { "type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$" },
    "gate": { "type": "string", "enum": ["code", "frontend", "agent", "db", "api"] },
    "plugin_commit": { "type": "string" }
  },
  "additionalProperties": false
}
```

**Notes:**
- `ttl_seconds` is fixed at 900 (15 minutes) per Modelling precedent
- `version` is the stamp schema version (not plugin version)
- `gate` discriminates which stamp category this is
- `plugin_commit` is optional but recommended for drift detection between installed plugin and worktree

**Acceptance:**
- Self-validates
- A sample stamp for each of the 5 gates validates successfully
- A stamp with `ttl_seconds != 900` fails validation
- A stamp missing any required field fails validation

## E.5 Schema 3 — `schemas/agent-frontmatter.schema.json`

**Purpose:** validates the YAML frontmatter of agent markdown files. Consumed by `meta-agent-scaffolder` (at creation) and `meta-agent-arch-doc-reviewer` (at validate gate) — both in Phase 1.

**Required fields** (per plan §4.2):
- `name` — kebab-case, pattern `^(py|fe|db|api|pattern|antipattern|design|discover|research|doc|meta|validation|refactor|operate|maintain|deploy|security|testing|interop|bg|closed-loop)-[a-z0-9-]+$`
- `description` — string, 1-500 chars (used for graph registry + skill matching)
- `tools` — array of strings (Claude Code tool names)
- `model` — enum: `opus | sonnet | haiku`
- `memory` — enum: `project | local | none`
- `maxTurns` — integer, 1-50

**Optional fields:**
- `effort` — enum: `low | medium | high | max` (only valid if `model = opus`)
- `skills` — array of skill names to preload
- `disallowedTools` — array of strings (tool blocklist)
- `isolation` — string, only valid value `"worktree"`
- `background` — boolean
- `color` — string (UI hint)
- `scope` — enum: `core | profile-scoped` (tells loader when to activate)
- `overlay` — boolean (if true, merges with a plugin-canonical base of the same name)

**Constraint (via `allOf` conditional):**
- If `effort` is `max`, `model` must be `opus` (JSON Schema `if/then`)
- If `isolation: worktree`, `tools` must include `Edit` or `Write`
- If `background: true`, `model` should be `haiku` or `sonnet` (warning-level, not hard fail)

**Acceptance:**
- Self-validates
- Sample frontmatter for each of the 5 bootstrap agents validates successfully
- Frontmatter with an invalid scope prefix (e.g., `foo-bar`) fails
- Frontmatter with `effort: max` + `model: sonnet` fails

## E.6 Schema 4 — `schemas/profile.schema.json`

**Purpose:** validates language profile files (`config/profiles/python.json`, `config/profiles/javascript.json`, etc.) per plan §3.2 `LanguageProfile` contract.

**Shape:**
```
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://dev-standards-plugin/schemas/profile.schema.json",
  "title": "Language Profile",
  "type": "object",
  "required": ["name", "priority", "detection", "tools", "conventions", "validationSteps"],
  "properties": {
    "name": "string (lowercase, kebab-case)",
    "priority": { "enum": ["P0", "P1", "P2", "P3"] },
    "detection": {
      "required": ["markers", "extensions"],
      "properties": {
        "markers": "string[] (file patterns that indicate this language)",
        "extensions": "string[] (e.g., '.py', '.tsx')"
      }
    },
    "tools": {
      "required": ["formatter", "linter"],
      "properties": {
        "formatter": { "command": "str", "extensions": "str[]" },
        "linter": { "command": "str", "extensions": "str[]" },
        "typeChecker": { "command": "str", "extensions": "str[]" },
        "testRunner": { "command": "str", "extensions": "str[]" }
      }
    },
    "packageManager": {
      "properties": {
        "preferred": "str",
        "fallback": "str",
        "lockfile": "str"
      }
    },
    "agents": "string[] (agent ids scoped to this profile)",
    "validationSteps": "string[] (ordered; mapped to gate step tuples)",
    "conventions": {
      "properties": {
        "fileNaming": { "enum": ["snake_case","kebab-case","PascalCase","camelCase"] },
        "functionNaming": { "enum": [...] },
        "classNaming": { "enum": [...] },
        "constantNaming": { "enum": [...] }
      }
    }
  }
}
```

**Acceptance:**
- Self-validates
- A minimal Python profile (P0, pyproject.toml marker, ruff/mypy/pytest tools, snake_case conventions) validates
- A minimal JS profile (P0, package.json marker, eslint/tsc/vitest tools, camelCase conventions) validates
- A profile missing `detection.markers` fails

## E.7 Doc 1 — `docs/architecture/README.md`

**Purpose:** single-page entry point to the architecture. Minimal — most architecture docs are written later by `doc-*` agents as dogfooded Phase 9 deliverables. This README is enough for a new reader to orient themselves and find the full plan.

**Required sections (each ~1-2 paragraphs):**
1. **What this is** — a plugin that turns Claude Code into an agentic development lifecycle framework
2. **The canonical plan** — link to `C:\Users\jmarks01\.claude\plans\cozy-doodling-church.md` (note: local path since the plan lives in the user memory, not the repo)
3. **The four locked decisions:**
   - ~141 agents across 20 categories
   - Full closed-loop infrastructure from Phase 4
   - Windows-first, Unix supported
   - Strict-by-default enforcement
4. **The Primitive Selection Framework (PSF)** — one paragraph: `Rule → Hook → Agent → Skill → Command → MCP tool`, pick leftmost that satisfies the requirement
5. **Bootstrap-first sequencing** — first usable state at end of Phase 1 (~4 weeks); every commit from Phase 2 onwards gated by the framework's own hooks
6. **Implementation phases** — one-line summary of the 11 phases from Appendix D §D.6
7. **Where to look next** — pointers to `bootstrap-spec.md`, `schemas/`, and (once written) the per-component docs

**Explicitly NOT in this README:**
- The full agent catalog (that's Appendix A, in the plan file)
- The phase process walkthroughs (Appendix B)
- The command orchestration map (Appendix C)
- The four-tier memory, PSF details, closed-loop architecture — these get dedicated docs in Phase 9 via `doc-*` agents

**Acceptance:**
- Scannable in under 5 minutes
- A reader can get to the plan file or schemas within two clicks
- Does NOT duplicate content from the plan file

## E.8 Doc 2 — `docs/architecture/bootstrap-spec.md`

**Purpose:** one-page contract for Phase 1. Defines exactly what goes in the minimum viable bootstrap and what the exit gate looks like. If something isn't in this spec, it doesn't go in the bootstrap. Additions require Phase 0 re-scope, not Phase 1 slip.

**Required sections:**

1. **Scope contract (~30 lines)** — the table from Appendix D §D.3 reproduced: 5 shared modules, 12 hooks, 3 commands, 5 agents, 4 schemas, 2 profiles, 2 scripts. One line per file with the purpose.

2. **Dependency topology (~20 lines)** — the ASCII DAG from §D.5.4:
```
_os_safe.py
    ↓
_hook_shared.py ── _session_state_common.py
    ↓                        ↓
stamp_validation.py ── write_agent_memory.py
    ↓
12 core hooks (parallel)
    ↓
/validate, /handoff, /setup (parallel)
    ↓
5 core agents (parallel)
    ↓
bootstrap-smoke.py (serial, exit gate)
```

3. **Phase 1 branches (~15 lines)** — the eight `feat/bootstrap-*` branches from §D.7 with their dependency order.

4. **The ten mechanisms (~10 lines)** — one-line reference for each of Modelling's ten interlocking mechanisms from §D.2, so the Phase 1 implementer has the invariants in front of them.

5. **Phase 1 exit gate (~25 lines)** — verbatim the 8 assertions from §D.4 + the additional requirements (Windows + Unix CI for `_os_safe.py`; `build-graph-registry.py` succeeds; `meta-agent-scaffolder` scaffolds a throwaway agent successfully).

6. **What is explicitly NOT in the bootstrap (~15 lines):**
   - Telemetry infrastructure (Phase 4)
   - Incident log (Phase 4)
   - 4-tier memory beyond session tier (Phase 4)
   - Language profiles beyond python + javascript (Phase 3)
   - MCP servers (Phase 10)
   - `bin/dsp-wt` worktree helper (added in Phase 1, but deferred to last in Phase 1 because bootstrap must work without it first)
   - All other agents (Phases 2-11)

7. **Pre-bootstrap exemption (~10 lines)** — Phase 0 commits and the first pass of Phase 1 are pre-bootstrap. The gate doesn't exist yet. These commits are recorded in the incident log as historical once the gate goes live. From Phase 1 exit onwards, every commit is gated.

**Acceptance:**
- Scannable in under 5 minutes (the "contract" property)
- References the four schemas by path (#14-17)
- A Phase 1 implementer can use this as the sole reference for scope decisions
- Any proposed addition to Phase 1 can be cross-checked against this spec in under 30 seconds

## E.9 Phase 0 Exit Verification

Task #20 acceptance criteria (no new files):

1. All 4 JSON Schemas (#14-17) self-validate using a JSON Schema draft-2020-12 validator
2. A minimal positive example validates against each schema (one stamp, one agent frontmatter, one profile, one graph registry fragment)
3. A minimal negative example (deliberately broken) fails against each schema
4. `docs/architecture/README.md` renders correctly on GitHub and scans in under 5 minutes
5. `docs/architecture/bootstrap-spec.md` is a one-page contract (target <200 lines, ~4-5 printed pages)
6. `feat/architecture-lockdown` PR opens cleanly against `master` with no merge conflicts
7. Existing CI (if any) still passes on the branch — Phase 0 adds files, doesn't touch code
8. Husky pre-commit hooks (if they run on markdown/JSON) pass

**PR metadata:**
- Title: `docs(architecture): lock bootstrap spec and foundational schemas (Phase 0)`
- Body: summary of what's in scope, reference to the approved plan, reference to Appendix D (bootstrap-first amendment), checklist of the 6 files, explicit statement that Phase 0 is pre-bootstrap and the gate is not yet live
- Labels: `architecture`, `phase-0`, `pre-bootstrap`

**After merge:** Phase 0 is complete. Phase 1 Bootstrap Spike begins via the parallel `feat/bootstrap-*` branches in §D.7.

## E.10 Ground-Truth State at Phase 0 Start

- **Master HEAD:** `1db361a` (merge of PR #7, `docs: update README and CHANGELOG for v1.4.0`)
- **Working tree:** clean, on `master`
- **PR #7 state:** merged
- **Tasks:** #12 complete; #13-20 pending, dependency chain intact
- **Plan file:** this file (`cozy-doodling-church.md`), now with Appendices A-E
- **Memory:** `session_state_2026-04-11.md` reflects the bootstrap-first amendment

Phase 0 is now a deterministic, specifications-first execution. Every deliverable has an acceptance criterion. When plan mode exits, execution begins at task #13 (cut `feat/architecture-lockdown`) and proceeds through #14-19 in parallel.

---

# Appendix F — Read/Reason/Write Tiering + Brownfield Scanners

**Amendment status:** proposed 2026-04-11, supersedes the relevant parts of Appendix B (Discover phase walkthrough), amends Appendix A (agent catalog) with 15 new agents, adds one new sub-category (`codebase/`), and extends `schemas/agent-frontmatter.schema.json` with a `tier` field. The architecture, PSF, memory tiers, and closed-loop design are unchanged; this amendment is about **specialization and pipeline discipline**, not about what the framework does.

## F.1 Context

The approved plan is biased toward **greenfield** work: design agents produce specifications, reviewer agents validate them, scaffolder agents generate code, auto-fixers mutate it. This is complete coverage for starting from zero. It is **not** complete coverage for starting from a running system with state, constraints, and tacit invariants — which is what real projects are.

Two concrete gaps surfaced in planning discussion:

1. **Brownfield read-tier agents are missing entirely.** We have `db-schema-reviewer` (reviews a design) but no `db-schema-scanner` (reads a live database and produces a structured factual report). Same for APIs, codebases, and architecture. Every reviewer today silently assumes it can re-read the target state from scratch every time it runs — expensive in context tokens, prone to inconsistency between reviewers, and incapable of handling the common case where "the existing system is the specification."
2. **Agent responsibilities are conflated.** Most reviewers read, reason, *and* write a verdict in a single invocation. Tools allow it; there's no architectural force separating the three activities. This produces agents that cannot be composed — you cannot have `db-schema-reviewer` produce facts for `design-schema-designer` because the former's output is a verdict, not a fact.

This amendment makes **Read / Reason / Write** an orthogonal dimension of agent specialization, enforced mechanically through Claude Code's `tools` / `disallowedTools` / `isolation` frontmatter fields (which already exist; we weren't using them systematically). It adds 15 brownfield-oriented agents filling the Read and Reason tiers across the domains where the gap is worst.

## F.2 The R/R/W Tier Principle

Every agent belongs to one of three tiers. The tier is encoded in frontmatter and enforced by schema + hook-level gates.

| Tier | Role | Tool allowlist (typical) | Tool blocklist (typical) | Isolation | Memory |
|---|---|---|---|---|---|
| **Read** | Scanner / profiler / extractor / inventorier — reads existing state exhaustively, emits a structured report against a known schema. No judgement beyond classification. | `Read`, `Glob`, `Grep`, `Bash` (read-only subprocess only) | `Edit`, `Write`, `NotebookEdit`, `WebFetch` | none | `project` (report cached) |
| **Reason** | Analyst / planner / gap-analyzer — consumes R-tier reports + a target state, produces a plan. High judgement, isolated context. | `Read`, `Bash` (read-only) | `Edit`, `Write`, `NotebookEdit`, `WebFetch` | none | `project` |
| **Write** | Applier / scaffolder / reviewer / auto-fixer — consumes plans (or reviews output), produces code/config/migration/verdict. | `Read`, `Edit`, `Write`, `Bash`, `Glob`, `Grep` | (none beyond defaults) | `worktree` (preferred for auto-fixers) | `project` |

**Principle:** an agent never spans tiers unless the domain is trivial (the transcript-extractor in §F.5 is the single exception — it reads, classifies, and writes a small structured artifact in one pass because splitting would be over-engineering). For everything else, the tier is singular.

### F.2.1 Why tiering matters (five reasons)

1. **Context economy.** Readers run once per session; their reports feed many downstream agents. Re-reading the database ten times across ten reviewers is ten times more expensive than reading once into a report.
2. **Cacheability.** R-tier outputs are facts with provenance (timestamp + watermark). Facts can be cached across sessions. `db-schema-report.json` is valid until a migration runs; all downstream agents read the cached report.
3. **Testability.** Structured reports can be validated against schemas. Plans can be validated against reports. This turns agent pipelines into assertable boundaries — "given this report, this plan is produced" is a testable property.
4. **Parallelism.** R-tier agents have no inter-dependencies; they fan out on a single worktree. Reason agents fan in. Writers fan out again. Sequential reviewer chains become DAGs.
5. **Failure isolation.** Columbia DAPLab's agentic failure modes (sycophancy, premature closure, false confidence) mostly originate in agents that conflate reading with reasoning. A read-tier agent that physically cannot write is immune to "I'm just going to quickly fix this" drift.

### F.2.2 Tool-scope enforcement

The CC agent frontmatter already supports `tools` (allowlist) and `disallowedTools` (blocklist). The tier is enforced mechanically at three levels:

1. **Schema** — `schemas/agent-frontmatter.schema.json` adds a `tier` field + conditional rules: `tier: read` requires `tools` to not contain `Edit`/`Write`/`NotebookEdit`.
2. **Meta-agent** — `meta-agent-arch-doc-reviewer` rejects any agent whose declared tier conflicts with its tools.
3. **Runtime hook** — a new `pre_tool_use_tier_enforcer.py` hook (Phase 2 addition) checks the active agent's tier against each tool invocation. A read-tier agent attempting `Edit` is blocked at the tool level, even if it somehow slipped past the schema.

This three-level defence is belt-and-braces. The schema catches declaration errors, the meta-agent catches propagation errors, and the hook catches runtime mistakes.

### F.2.3 Bash is a sharp knife

Read-tier agents need `Bash` for subprocess queries (psql, curl, git log, find). But Bash allows arbitrary execution — a read-tier agent could technically call `rm -rf`. Mitigations:

- `dangerous_command_block.py` (bootstrap hook) already catches destructive patterns
- New hook `pre_bash_tier_guard.py` (Phase 2) adds a stricter allowlist when the active agent is `tier: read` — only `SELECT`-style SQL, `GET`-only HTTP, read-only filesystem commands. Violations exit 2.
- R-tier agents declare intent in their description; `meta-agent-arch-doc-reviewer` cross-checks that the description is consistent with read-only scope.

This is enough to make `Bash` safe for read-tier work without giving up its breadth.

## F.3 Greenfield vs Brownfield as a First-Class Concept

The plan currently has no explicit model of project state. Every design agent assumes a blank canvas. Every reviewer assumes a discrete thing to review.

**Amendment:** a new agent classifies every project at the top of the Discover phase.

**`discover-project-state-classifier`** (`tier: read-reason`, model: sonnet) examines:
- Repo age and commit history depth
- Presence of production markers (deployment configs, release tags, migrations run)
- LOC count and module count
- Existence of a running database / deployed API / shipped frontend
- Test coverage and CI state

It emits one of three classifications to `.claude/discover/project-state.json`:

| State | Definition | Scanner pipeline |
|---|---|---|
| **greenfield** | Empty or stub repo, no production state, no meaningful existing code | Skip scanners. Go straight to requirements elicitation. |
| **growing-green** | Code exists but no production state; small codebase; no deployed artifacts | Run `codebase-inventory-scanner` only. Skip domain scanners. |
| **brownfield** | Production code with deployed state, consumers, data, or operational history | Run full R-tier pipeline (§F.4). |

Every subsequent phase reads `project-state.json` to branch its behaviour. This is how "conditional rules" manifest mechanically: the graph registry has `scoped-by: project-state=brownfield` edges on all brownfield-only agents, and they activate only when the classifier's output matches.

## F.4 The Scanner Pipeline

The R-tier scanners run in parallel as a DAG, fan in to Reason-tier analysts, then feed the Design phase. For a fully brownfield project:

```
                    discover-project-state-classifier
                                 ↓
              ┌─────────────────────────────────────┐
              │  R-tier scanners (parallel, worktree-safe)  │
              └─────────────────────────────────────┘
  ┌───────────┬─────────────┬──────────┬──────────┬──────────┐
  │           │             │          │          │          │
  ▼           ▼             ▼          ▼          ▼          ▼
codebase-  codebase-    codebase-   db-schema- api-contract- codebase-
inventory- dependency-  dead-code-  scanner    extractor     convention-
scanner    grapher      detector                              profiler
  │           │             │          │          │          │
  │           │             │          ▼          ▼          │
  │           │             │    db-data-    api-usage-      │
  │           │             │    profiler    profiler        │
  │           │             │          │          │          │
  └───────────┴─────────────┴──────────┴──────────┴──────────┘
                                 ↓
              ┌─────────────────────────────────────┐
              │  Reason-tier analysts (fan-in)       │
              └─────────────────────────────────────┘
                  │              │              │
                  ▼              ▼              ▼
        codebase-          db-migration-  api-breaking-
        architecture-      planner        change-analyzer
        reconstructor
                  │              │              │
                  └──────────────┴──────────────┘
                                 ↓
                          design-gap-analyst
                                 ↓
                              DESIGN phase
                    (now informed by facts, not assumptions)
```

### F.4.1 Parallelism + isolation

All R-tier scanners run in the same ephemeral worktree (not the dev worktree — a throwaway clone). They share read-only filesystem access and never write to the repo. Each emits a single JSON report to `.claude/discover/<scanner-name>.json`.

Scanner outputs are content-addressed by `(source_commit, scanner_version)` — running the same scanner on the same commit produces a byte-identical report. This enables cache reuse across sessions.

### F.4.2 Report freshness

Each report includes:
```json
{
  "scanner": "db-schema-scanner",
  "scanner_version": "1.0.0",
  "generated_at": "2026-04-11T10:00:00Z",
  "source_commit": "1db361a",
  "watermark": {
    "schema_version": "2026_04_01_0001",
    "last_migration": "add_user_email_index"
  },
  "report": { ... }
}
```

Consumers compare the watermark against current state and re-run the scanner if stale. For filesystem-based scanners (inventory, dependency-graph, convention-profiler), the watermark is the git sha. For database scanners, it's the last applied migration. For API scanners, it's a hash of the route files.

### F.4.3 Report schemas

Each scanner emits against a JSON Schema in `schemas/reports/`. New schemas introduced by this amendment:

- `schemas/reports/codebase-inventory.schema.json`
- `schemas/reports/codebase-dependency-graph.schema.json`
- `schemas/reports/codebase-convention-profile.schema.json`
- `schemas/reports/db-schema-report.schema.json`
- `schemas/reports/db-data-profile.schema.json`
- `schemas/reports/api-contract-report.schema.json`
- `schemas/reports/api-usage-profile.schema.json`
- `schemas/reports/project-state.schema.json`
- `schemas/reports/transcript-todo-extraction.schema.json`

Not delivered in Phase 0 (only the four foundational schemas are Phase 0). These land in Phase 3 as part of state-inventory scanner implementation.

## F.5 The Transcript-to-Todos Agent

The specific second example you raised: an agent that watches other agents' output and extracts deferred items before they're forgotten.

**`closed-loop-transcript-todo-extractor`**

- **Tier:** `read-reason-write` (the single exception to single-tier discipline — splitting would be over-engineering for what is effectively a small pipeline)
- **Category:** `closed-loop/` (not `meta/`; it's feedback-capture, same pattern as `context-rolling-summarizer`)
- **Model:** `haiku` (summarization-class work, no deep reasoning)
- **Trigger:** `SubagentStop` hook, using CC's `hook type: agent` primitive — the hook *is* the agent invocation, no glue code
- **Tools:** `Read`, `Edit`, `Bash`, `Glob`, `Grep`
- **maxTurns:** 5
- **Memory:** `project`

**Behaviour:**

1. Read the stopped subagent's transcript from `${transcript_path}` (JSONL)
2. Parse assistant messages for deferral patterns, both explicit and implicit:
   - Explicit: `TODO:`, `FIXME:`, `we should also`, `let's defer`, `skipping for now`, `another time`, `out of scope for now`, `circle back`
   - Implicit: acknowledgments of edge cases that weren't handled, mentions of improvements that were named but not made, partial fixes
3. For each candidate, extract 2-3 sentences of surrounding context + the original speaker's intent (which agent said it, pursuing which objective)
4. Classify each candidate:
   - In-scope deferral (relevant to current objective; re-inject at next `/tdd` run)
   - Out-of-scope deferral (relevant long-term; add to project backlog)
   - False positive (boilerplate language, not a real deferral)
5. Deduplicate against existing items in `session-state.md` under `## Task Progress`
6. Write new items:
   - In-scope → append to `session-state.md` as `- [ ] <todo>` (picked up by `session_start.py` next session)
   - Out-of-scope → append to `TODO.md` at repo root (longer-lived backlog)
7. Emit a telemetry record to `${CLAUDE_PLUGIN_DATA}/framework-memory/telemetry/transcript-extraction.jsonl`:
   - Extraction count, false-positive rate (populated later when humans accept/reject), cost

**Why this specific agent exists:**

The Modelling session lifecycle already tracks todos across sessions via the `## Task Progress` section of `session-state.md`. But todos only get there if someone (user or agent) explicitly wrote them. Deferred items mentioned in passing during an agent's chain-of-thought are *lost at session end*. This agent is the safety net: it watches for those implicit deferrals and promotes them to tracked todos automatically, closing the information leak.

**Scope discipline:**

The agent only reads transcripts and writes to well-defined markdown files. It cannot modify code. It cannot invoke other agents. Its behaviour is fully contained.

**Bootstrap impact:** This agent lands in the **Phase 1 bootstrap** specifically — it's too valuable to defer. Adding it costs 2 files (agent markdown + transcript-todo-extraction report schema) plus one hook registration. Phase 1 bootstrap grows from ~31 → ~33 files.

## F.6 New Agents (15)

Distributed across categories; each slotted into the R/R/W tier explicitly.

### F.6.1 Discover (+1)

| Agent | Tier | Model | Purpose |
|---|---|---|---|
| `discover-project-state-classifier` | read-reason | sonnet | Classifies a project as greenfield / growing-green / brownfield; writes `.claude/discover/project-state.json` for all downstream agents |

### F.6.2 Codebase (NEW category, +5)

| Agent | Tier | Model | Purpose |
|---|---|---|---|
| `codebase-inventory-scanner` | read | sonnet | Walks filesystem, produces `{modules, entry points, test layout, LOC per dir, languages detected}` report |
| `codebase-dependency-grapher` | read | sonnet | Builds module-to-module dependency DAG from imports; detects cycles |
| `codebase-dead-code-detector` | read (BG) | sonnet | Finds unreachable functions, unused exports, orphaned files |
| `codebase-convention-profiler` | read | sonnet | Learns the project's actual naming/structure conventions from existing code; feeds `meta-filename-advisor` and `meta-folder-structure-advisor` so their recommendations match the project instead of framework defaults |
| `codebase-architecture-reconstructor` | reason | opus | Consumes inventory + dependency-graph + convention-profile → produces a latent architecture diagram (Mermaid) and a discrepancy report against any stated architecture |

### F.6.3 Database (+4)

| Agent | Tier | Model | Purpose |
|---|---|---|---|
| `db-schema-scanner` | read | sonnet | Introspects live database (or reads migration history) → structured schema report: tables, columns, indexes, FKs, constraints, sizes, row counts |
| `db-data-profiler` | read (BG) | sonnet | Samples live data → cardinality, nullability, distribution, outlier detection per column |
| `db-existing-query-extractor` | read | sonnet | Scans code for SQL/ORM usage, produces "where each table/column is accessed" map |
| `db-migration-planner` | reason | opus max | Consumes current schema + target schema + data profile → produces Alembic/Flyway/Knex migration plan with reversibility analysis and lock-duration estimates |

### F.6.4 Interface / API (+3)

| Agent | Tier | Model | Purpose |
|---|---|---|---|
| `api-contract-extractor` | read | sonnet | Reverse-engineers OpenAPI spec from FastAPI/Express/NestJS/Django route handlers; handles async, middleware, decorators |
| `api-usage-profiler` | read (BG) | sonnet | Consumes access logs or distributed traces → endpoint call frequency, caller identity, parameter distribution, error rates |
| `api-breaking-change-analyzer` | reason | opus | Consumes extracted contract + proposed change → blast-radius report (which consumers break, which fields become nullable, how to deprecate) |

### F.6.5 Design (+1)

| Agent | Tier | Model | Purpose |
|---|---|---|---|
| `design-gap-analyst` | reason | opus max | The top-level fan-in reason agent. Consumes **all** R-tier reports + stated design objectives → prioritised gap report that feeds `design-brainstormer-advisor` with "here's what exists, here's what's needed, here's the delta" |

### F.6.6 Closed-loop (+1)

| Agent | Tier | Model | Purpose |
|---|---|---|---|
| `closed-loop-transcript-todo-extractor` | read-reason-write | haiku | The deferred-item safety net described in §F.5. Triggered by `SubagentStop` via hook type `agent`. Writes to `session-state.md` + `TODO.md`. |

## F.7 Schema Additions

### F.7.1 Amend `schemas/agent-frontmatter.schema.json`

Add a new optional-but-recommended field:

```json
"tier": {
  "type": "string",
  "enum": ["read", "reason", "write", "read-reason-write"],
  "description": "R/R/W specialization tier. 'read' = readers/profilers (no Edit/Write), 'reason' = analysts/planners (no Edit/Write, read-only Bash), 'write' = scaffolders/reviewers/auto-fixers. 'read-reason-write' is reserved for pipelines where splitting would be over-engineering (e.g. closed-loop-transcript-todo-extractor). All existing agents should be retrofitted with this field in Phase 5."
}
```

Add a conditional rule:

```json
{
  "if": {
    "properties": { "tier": { "const": "read" } },
    "required": ["tier"]
  },
  "then": {
    "properties": {
      "tools": {
        "not": {
          "contains": {
            "enum": ["Edit", "Write", "NotebookEdit"]
          }
        }
      }
    }
  }
}
```

Same conditional for `tier: reason` (readers and reasoners both forbid Edit/Write). This makes schema-level tier enforcement mechanical.

### F.7.2 New schema: `schemas/reports/` subdirectory

Nine new report schemas listed in §F.4.3. All land in Phase 3, not Phase 0. Each follows the shape:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["scanner", "scanner_version", "generated_at", "source_commit", "watermark", "report"],
  "properties": {
    "scanner": { "type": "string" },
    "scanner_version": { "type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$" },
    "generated_at": { "type": "string", "format": "date-time" },
    "source_commit": { "type": "string", "pattern": "^[0-9a-f]{7,40}$" },
    "watermark": { "type": "object" },
    "report": { /* scanner-specific shape */ }
  }
}
```

Only `schemas/reports/transcript-todo-extraction.schema.json` lands in Phase 1 (bootstrap), because it's needed by the bootstrap's transcript extractor.

## F.8 Hook Additions

Two new hooks on top of the bootstrap 12 + Phase 2's 24 additions:

| Event | Hook | Phase | Purpose |
|---|---|---|---|
| PreToolUse | `pre_bash_tier_guard.py` | Phase 2 | When active agent is `tier: read` or `tier: reason`, block Bash commands that don't match a read-only allowlist (SELECT-only SQL, GET-only HTTP, `git log`, `find`, `grep`, `ls`, `cat`, etc.) |
| PreToolUse | `pre_tool_use_tier_enforcer.py` | Phase 2 | When active agent is `tier: read` or `tier: reason`, block `Edit` / `Write` / `NotebookEdit` tool invocations even if they slipped past the schema |

And the existing `SubagentStop` hook gets extended in the bootstrap to declare the transcript extractor as a `hook type: agent`:

```json
{
  "SubagentStop": [
    {
      "type": "agent",
      "agent": "closed-loop-transcript-todo-extractor",
      "matcher": "*",
      "timeout_ms": 30000
    }
  ]
}
```

This is new in the bootstrap — it replaces the generic `subagent_summary.py` placeholder with a tiered agent invocation. One file saved, one concern gained.

## F.9 Discover Phase Expansion

This **supersedes Appendix B §B.1** (the Discover process walkthrough).

**Trigger:** `/discover <problem statement>` or `/scan` (new command, §F.10)

**Phase marker:** `.current_phase = discover`

**Budget:** 40K tokens (base) + per-scanner budgets (bounded individually since scanners run in isolated sub-contexts)

**Flow:**

1. **Classify** — `discover-project-state-classifier` runs first (reason-tier): examines repo, writes `.claude/discover/project-state.json` with state ∈ {greenfield, growing-green, brownfield}.

2. **Branch on state:**

   **If `greenfield`:**
   - Skip all scanners
   - Run `discover-requirements-elicitor` (interview)
   - Run `discover-stakeholder-mapper` (stakeholders)
   - Phase exits to `/design`

   **If `growing-green`:**
   - Run `codebase-inventory-scanner` only (cheap, always useful)
   - Run `discover-requirements-elicitor`
   - Run `discover-stakeholder-mapper`
   - Run `codebase-convention-profiler` → feeds `meta-filename-advisor`
   - Phase exits to `/design`

   **If `brownfield`:**
   - **R-tier fan-out** (parallel, worktree-isolated):
     - `codebase-inventory-scanner`
     - `codebase-dependency-grapher`
     - `codebase-dead-code-detector` (background)
     - `codebase-convention-profiler`
     - `db-schema-scanner` (if database detected)
     - `db-data-profiler` (background, if database detected)
     - `db-existing-query-extractor` (if database detected)
     - `api-contract-extractor` (if API route files detected)
     - `api-usage-profiler` (background, if logs/traces available)
   - **Reason-tier fan-in** (sequential on their inputs):
     - `codebase-architecture-reconstructor` (consumes inventory + dependency-graph + convention-profile)
     - `db-migration-planner` (if database changes planned — deferred until `/design` identifies target)
     - `api-breaking-change-analyzer` (if API changes planned — deferred until `/design` identifies target)
   - **Parallel to the reason tier:**
     - `discover-requirements-elicitor`
     - `discover-stakeholder-mapper`
   - **Final fan-in:**
     - `design-gap-analyst` consumes *every* R-tier report + stated requirements → prioritised gap report at `.claude/discover/gap-report.md`
   - Phase exits to `/design` with `.claude/discover/` populated as the factual substrate for all design decisions

3. **All scanner outputs are content-addressed** by `(source_commit, scanner_version)`. Re-running `/discover` on the same commit reuses cached reports from `${CLAUDE_PLUGIN_DATA}/cache/reports/`. Only stale reports (watermark mismatch) are re-scanned.

4. **Session memory** records which scanners ran, which reports were cached, and how long each took — feeds `closed-loop-quality-scorer` for retrospective cost analysis.

**Exit:** a structured `.claude/discover/` directory containing project state, all applicable scanner reports, a gap-analysis summary, and stakeholder/requirements documents. No code has been touched. The design phase starts with full factual context.

## F.10 New Command: `/scan`

Currently only `/discover` invokes the R-tier pipeline, and only at the start of new work. But the scanners are useful at other moments:

- Before a large refactor, to establish a baseline
- Periodically, to detect drift (the architecture has diverged from the stated design)
- On a fresh clone, for an onboarding report

**`/scan [target]`** runs the R-tier scanner pipeline on demand, without entering the Discover phase. It produces the same `.claude/discover/*` outputs but does not trigger downstream phase logic. Useful as a "show me what's here" command.

`target` is optional and selects a subset: `/scan database`, `/scan api`, `/scan codebase`, `/scan all`.

Command orchestration: `/scan` composes the same R-tier agents as Discover's brownfield branch, but without the Reason-tier fan-in (no gap analysis — that's `/discover`'s job). This is a separation-of-concerns move: `/scan` = facts; `/discover` = facts → plan.

## F.11 Bootstrap (Phase 1) Impact

Two agents land in the bootstrap specifically:

1. **`closed-loop-transcript-todo-extractor`** — deferral safety net, too valuable to defer. Wired via `SubagentStop` hook type `agent`. Adds 2 files (agent markdown + `schemas/reports/transcript-todo-extraction.schema.json`). Hook entry in `hooks/hooks.json` replaces the placeholder `subagent_summary.py` registration.

2. **`discover-project-state-classifier`** — needed the first time `/setup` runs on a new project to decide whether to go straight to bootstrap or scan first. Adds 1 file (agent markdown) + the schema for project-state.json which lives in `schemas/reports/project-state.schema.json`. Second file already counted above.

Bootstrap total: 31 → **33** (+2 files). Still tight. The scope contract in `bootstrap-spec.md` needs to reflect these additions.

All other brownfield scanners (codebase, database, API, + design-gap-analyst) land in **Phase 3**.

## F.12 Sequencing Impact

**Phase 3 in the revised Appendix D sequencing** (was "Language Profiles", 1 week) becomes:

**Phase 3 — Language Profiles + State Inventory Scanners (2 wks)**

Delivers:
- Remaining language profiles: `typescript.json`, `fullstack.json`, Rust/Go/Kotlin placeholders (1 week)
- All 13 brownfield scanner and reason agents (excluding the two in the bootstrap) — 1 week
- New commands: `/scan`
- Two new hooks: `pre_bash_tier_guard.py`, `pre_tool_use_tier_enforcer.py`
- Report schemas in `schemas/reports/` (9 files)

Phase 3 grows from 1 week → **2 weeks**. Total roadmap from 26 → **27 weeks**.

This is cheaper than I initially estimated because: (a) only the R-tier scanners and one Reason-tier fan-in agent are genuinely new work, (b) the infrastructure (schemas, hooks, agent frontmatter) they depend on is small, and (c) they can be built in parallel worktrees once the bootstrap is live.

## F.13 Retrofitting Existing Agents

All 141 agents from Appendix A need a `tier` field added during Phase 5 (Core Agent Refactor). Classification guide:

- **Tier: read** — (none in current Appendix A; this amendment adds the first ones)
- **Tier: reason** — `design-brainstormer-advisor`, `design-architecture-reviewer`, `design-requirements-analyst`, `design-api-contract-designer`, `design-schema-designer`, `security-threat-modeler`, `research-spike-planner`, `operate-incident-responder`, `design-gap-analyst` (new), `research-prior-art-scanner` (background), the pattern advisors, the anti-pattern detectors, `validation-objective-verifier`, `validation-completion-verifier`
- **Tier: write** — all `*-reviewer` agents (they return verdicts, which are structured writes), all `*-checker` auto-fixers, all `*-scaffolder` agents, `refactor-applier`, `maintain-dependency-updater`, `closed-loop-quality-scorer` (writes scores)
- **Tier: read-reason-write** — `closed-loop-transcript-todo-extractor` (new; the only sanctioned case)

Phase 5's exit gate now includes: every agent in Appendix A has a `tier` field; `meta-agent-arch-doc-reviewer` enforces tier-consistency against tools; CI rejects agent markdown without a declared tier.

## F.14 Revised Totals

| Dimension | Original (Appendix A) | After Appendix F | Delta |
|---|---|---|---|
| Agents | 141 | **156** | +15 |
| Agent categories | 20 | **21** | +1 (`codebase/`) |
| Commands | 27 | **28** | +1 (`/scan`) |
| Hooks (full framework) | 36 | **38** | +2 (`pre_bash_tier_guard`, `pre_tool_use_tier_enforcer`) |
| Schemas | 8 | **17** | +9 (report schemas in Phase 3, +1 in bootstrap) |
| Bootstrap file count | 31 | **33** | +2 |
| Phases | 11 | 11 | unchanged |
| Timeline (weeks) | ~26 | **~27** | +1 (Phase 3 absorbed) |

Agent breakdown by category after amendment:

| Category | Count | Change |
|---|---|---|
| design | 6 | +1 (`design-gap-analyst`) |
| discover | 3 | +1 (`discover-project-state-classifier`) |
| research | 2 | — |
| document | 4 | — |
| **codebase** | **5** | **+5 (new category)** |
| patterns | 54 | — |
| antipatterns | 8 | — |
| python | 9 | — |
| frontend | 7 | — |
| interface | 6 | +3 (api-contract-extractor, api-usage-profiler, api-breaking-change-analyzer) |
| interop | 1 | — |
| database | 7 | +4 (db-schema-scanner, db-data-profiler, db-existing-query-extractor, db-migration-planner) |
| security | 6 | — |
| testing | 6 | — |
| validation | 2 | — |
| meta | 12 | — |
| refactor | 3 | — |
| operate | 3 | — |
| maintain | 3 | — |
| deploy | 4 | — |
| closed-loop | 5 | +1 (`closed-loop-transcript-todo-extractor`) |
| **Total** | **156** | **+15** |

## F.15 Phase 0 Impact

Two small changes to Phase 0 deliverables already in progress on `feat/architecture-lockdown`:

1. **`schemas/agent-frontmatter.schema.json`** — add the `tier` field and the two conditional rules. This is a minor edit to a file already written. Must happen before PR #8 merges so the bootstrap has a correct schema.

2. **`docs/architecture/bootstrap-spec.md`** — update the "~31-file" scope contract to "~33-file" and add `closed-loop-transcript-todo-extractor` + `discover-project-state-classifier` + `schemas/reports/transcript-todo-extraction.schema.json` + `schemas/reports/project-state.schema.json` to the core agents and schemas sections. Also add a sentence on R/R/W tiering as a Phase 1 exit gate criterion (the bootstrap's 5 core agents must declare tiers correctly).

Neither change affects the Phase 0 exit verification (the schemas still self-validate, and the bootstrap spec is still a scannable contract — just slightly larger).

## F.16 What Appendix F Commits To

- **R/R/W tiering** as a first-class orthogonal dimension encoded in agent frontmatter and enforced at three levels (schema, meta-agent, runtime hook)
- **Greenfield / growing-green / brownfield classification** as the entry point to Discover, implemented by `discover-project-state-classifier`
- **Brownfield scanner pipeline** — fan-out R-tier → fan-in Reason-tier → feed Design, with content-addressed caching
- **15 new agents** across 6 categories (1 new category `codebase/`)
- **`closed-loop-transcript-todo-extractor`** in the **bootstrap** specifically — the deferred-item safety net, no information leakage between sessions
- **`/scan`** as a new command for fact-gathering without phase transition
- **Two new Phase-2 hooks** enforcing tier safety at the Bash and tool-invocation level
- **Nine new report schemas** in `schemas/reports/` landing in Phase 3
- **Phase 3 grows** from 1 week to 2 weeks; total timeline from ~26 → ~27 weeks
- **Phase 0 bootstrap spec updated** with two additional agents and two additional schemas
- **All 141 existing agents retrofitted** with a `tier` field during Phase 5's Core Agent Refactor
- **Appendix B §B.1 (Discover phase walkthrough) is superseded** by §F.9
- **No changes** to PSF, four-tier memory, closed-loop design, strict default, Windows-first, or the architectural core; this amendment is pure specialization discipline

Next action after approval: continue Phase 0 by updating `schemas/agent-frontmatter.schema.json` with the `tier` field and conditional rules, updating `docs/architecture/bootstrap-spec.md` with the +2 files and the tier-enforcement note, then taking the second Phase 0 commit on `feat/architecture-lockdown`. The current state (commit 1 made, commit 2 staged) is preserved — the staged files need minor edits before they're committed.

---

# Appendix G — Documentation-As-Code + Context-Aware Loading

**Amendment status:** proposed 2026-04-11, supersedes Appendix E §E.7-E.8 (the Phase 0 README and bootstrap-spec deliverables as originally written), corrects Appendix D §8.5 (the 22 rules inventory), and corrects Appendix F §F.7.1 (rule frontmatter assumptions). Does not change PSF, memory tiers, closed-loop design, R/R/W tiering, or the 156-agent catalog. **This amendment is about how documentation is organized, sized, and loaded at runtime so that agents building the framework can actually find what they need without swallowing the entire plan file.**

## G.1 Context — the dogfooding failure

The approved plan is a ~2200-line monolith at `C:\Users\jmarks01\.claude\plans\cozy-doodling-church.md`. To answer any architectural question, an agent would load the entire file: ~25-30K tokens, roughly **25-50% of the smaller per-phase context budgets** the plan itself declares. Any Phase 1 hook implementer asking "what is the stamp model, what's the tier field, what's in the bootstrap?" would pay that full cost every time.

The plan's own principles forbid this:

- **PSF**: rules should be cheap to load and path-scoped — violated by one giant file
- **Four-tier memory**: session/project/agent/framework with explicit separation — violated by a global blob
- **Per-phase context budgets**: 40K-120K depending on phase — violated by a document that consumes 25K before any work begins
- **Closed-loop improvement**: documentation should be generated from code by `doc-*` agents — violated by hand-authored monolith
- **Selective loading**: agents should only load what they need — violated because there's no mechanism to load partial content

This is the exact failure mode the framework is supposed to prevent. We're building context-aware tooling and documenting it with context-hostile artifacts. The dogfooding test failed.

## G.2 Claude Code's Actual Context Mechanisms (authoritative research)

A targeted re-read of `code.claude.com/docs` and the official `claude-plugins-official` repo corrects several assumptions the plan made. Sources cited inline; full survey available on request.

### G.2.1 The four context primitives

| Primitive | Who writes | How it loads | Compaction survival | Size best practice |
|---|---|---|---|---|
| **CLAUDE.md** | Humans (project or user) | Parent CLAUDE.md loads eagerly at session start; subdirectory CLAUDE.md lazy-loads when Claude reads files in that directory | **Fully preserved** — re-read from disk after compaction | **<200 lines per file** |
| **Rules (`.claude/rules/*.md`)** | Humans (project or user) | Unconditional rules load eagerly; rules with `paths:` frontmatter load lazily on file access (READ only, not WRITE — known limitation) | **Undocumented / not explicitly preserved** — assume lost on compaction | **<200 lines per file** |
| **Skills (`skills/<name>/SKILL.md`)** | Humans (plugin, project, or user) | Descriptions (~100 tokens) always loaded so Claude knows availability; full content loaded on invocation (auto or explicit) | **5K tokens preserved per skill**, shared **25K budget** across all skills post-compaction, older skills dropped entirely | **SKILL.md <500 lines**; description **<250 chars (truncated beyond)** |
| **Auto Memory (`~/.claude/projects/<slug>/memory/`)** | Claude writes; humans cannot pre-populate; **plugins cannot ship memory** | First 200 lines or 25KB of `MEMORY.md` load at session start; topic files load on demand | **Not explicitly re-injected** post-compaction; reloads at next session | N/A |

### G.2.2 Critical plugin-vs-project duality

**Plugins do not ship CLAUDE.md or rules files.** This is the single biggest correction to the plan. From the official docs + claude-plugins-official repo survey:

> "Plugin documentation emphasizes structured workflows rather than inline reference docs. [...] No CLAUDE.md files shipped in plugins themselves. Plugins ship skills in `skills/<name>/SKILL.md` format instead."

This creates a fundamental duality the plan completely missed:

1. **dev-standards-plugin's own repo** (the thing we're developing now, at `C:\Users\jmarks01\Projects\dev-standards-plugin\`) — this repo has `.claude/CLAUDE.md`, `.claude/rules/*.md`, `docs/architecture/`, etc. All of these are for **the plugin's own dogfooded development**. They are consumed by agents working on the plugin. They are **not shipped to users**.

2. **The plugin as installed by users** — when a user runs `/plugin install dev-standards-plugin`, what arrives is: `hooks/*.py`, `agents/**/*.md`, `commands/*.md`, `skills/<name>/SKILL.md`, `config/**/*.json`. The user's own `.claude/CLAUDE.md` and `.claude/rules/` are untouched. To influence user behaviour, the plugin ships **skills** that auto-invoke on file patterns.

These are two different contexts with different primitives. Appendix D §8.5 said "22 rules" — but most of those can't be shipped as rules (plugins can't ship rules). They have to be one of:

- **Skills** (shipped to users, auto-invoked by `paths:` globs)
- **Rules in the plugin's own repo** (for dogfooding; not shipped)
- **Rules installed into user projects via `/setup`** (user opt-in; copied during install)

### G.2.3 Rule frontmatter — what actually exists

The plan (Appendix F §F.7.1 and Appendix D §8.5) assumed rules could carry `scope: [glob]`, `phase: [list]`, `version: "1.0"` frontmatter. **None of these exist in Claude Code.** Real rule frontmatter supports:

- `paths:` — glob patterns for scope (documented, but has bugs; the undocumented `globs:` is reportedly more reliable)
- That's the only documented scoping field

There is **no `phase:` field** and **no `version:` field** for rules. Phase scoping is a framework-level concept the plan invented; it has to be implemented on top of CC, not assumed.

Worse: **path-scoped rules load on READ but not on WRITE** ([GitHub issue #23478](https://github.com/anthropics/claude-code/issues/23478)). This is a known limitation — if you need a rule to fire when Claude edits a file (not just when it reads one), directory placement is more reliable than `paths:` frontmatter.

### G.2.4 CLAUDE.md hierarchy and lazy loading

Confirmed mechanics:

- **Parent CLAUDE.md files load eagerly at session start** (root CLAUDE.md, `.claude/CLAUDE.md`, `~/.claude/CLAUDE.md`)
- **Subdirectory CLAUDE.md files lazy-load on file access** — when Claude reads a file in `agents/meta/`, if `agents/meta/CLAUDE.md` exists, it loads then
- **After compaction, CLAUDE.md files are re-read from disk** — fully preserved across compaction
- **No file-extension scoping mechanism exists** in CLAUDE.md itself — use rules with `paths:` for that

### G.2.5 The `@path` include mechanism

Instruction files support `@path` syntax to include other files. This is the composition mechanism for keeping individual files under 200 lines while referencing longer content on demand. `InstructionsLoaded` hook fires with `load_reason: include` when one file triggers loading of another.

### G.2.6 Compaction reality check

When context nears 83.5% of the 200K window, auto-compaction fires. After compaction, what survives:

1. **CLAUDE.md — fully reloaded from disk** (the single most durable primitive)
2. **Most recent 5 file reads**, capped at 50K tokens total
3. **Skills — 5K tokens per skill re-attached, shared 25K budget**, older skills dropped
4. **Rules** — undocumented; assume lost
5. **Auto memory** — not explicitly re-injected; reloads next session
6. **Tool definitions** — re-announced

**Consequence for architecture:** if something must be available across compaction, it goes in CLAUDE.md. Skills are volatile. Rules are effectively ephemeral. This ranks the primitives by durability and forces a design principle: *load-bearing invariants live in CLAUDE.md; specialized knowledge lives in skills; ephemeral details live nowhere (they're re-derived from code).*

## G.3 The Documentation Hierarchy (6 tiers)

Applying the research to the dev-standards-plugin repo, the documentation has six tiers arranged by scope and durability:

| Tier | Location | Loaded when | Size | Example |
|---|---|---|---|---|
| **T1: Project root orientation** | `.claude/CLAUDE.md` at repo root | Always, session start, preserved across compaction | **<100 lines** | "This is dev-standards-plugin. When editing a Python hook, look at `hooks/CLAUDE.md`. When editing an agent, look at `agents/CLAUDE.md`. Core concepts: @docs/architecture/primitives/psf.md @docs/architecture/primitives/stamps.md" |
| **T2: Directory-scoped orientation** | `<subdir>/CLAUDE.md` | Lazy-loaded when Claude reads files in that subdirectory; re-loaded after compaction | **<200 lines per file** | `hooks/CLAUDE.md`, `agents/meta/CLAUDE.md`, `schemas/CLAUDE.md` |
| **T3: Topic rules (plugin's own)** | `.claude/rules/*.md` in the plugin repo | Unconditional rules eagerly; path-scoped via `paths:` on read | **<200 lines per file** | `.claude/rules/hook-development.md`, `.claude/rules/agent-frontmatter.md` |
| **T4: Architecture primitives** | `docs/architecture/primitives/*.md` | Referenced via `@path` from CLAUDE.md/rules; loaded on demand when `@include`d | **<200 lines per file** | `docs/architecture/primitives/psf.md`, `docs/architecture/primitives/four-tier-memory.md`, `docs/architecture/primitives/rrw-tiering.md`, `docs/architecture/primitives/stamp-model.md`, `docs/architecture/primitives/bootstrap-first.md`, `docs/architecture/primitives/dogfooding.md`, `docs/architecture/primitives/context-budget.md` |
| **T5: Phase specifications** | `docs/architecture/phases/*.md` | Referenced when planning specific phase work | **<200 lines per file** | `docs/architecture/phases/phase-0.md`, `docs/architecture/phases/phase-1-bootstrap.md`, ..., `docs/architecture/phases/phase-11.md` |
| **T6: Canonical plan (archived, not runtime)** | `C:\Users\jmarks01\.claude\plans\cozy-doodling-church.md` | **Never auto-loaded at runtime**. Loaded manually only during planning sessions (like now). Serves as historical decision record. | Unlimited (it's a decision record, not runtime context) | This file |

The canonical plan stays as a decision record but never enters an agent's runtime context. All runtime references are to tiers T1-T5, which are all under 200 lines per file.

### G.3.1 Plugin-shipped content (separate from T1-T5)

The plugin additionally ships — for installation into USERS' projects:

| Plugin-shipped | Location | How it reaches users |
|---|---|---|
| **Skills** | `skills/<name>/SKILL.md` in the plugin repo | Loaded automatically into user sessions after `/plugin install`; auto-invoke via `paths:` globs; <500 lines per SKILL.md; <250 char descriptions |
| **Hooks** | `hooks/*.py` in the plugin repo | Registered via `hooks/hooks.json` |
| **Agents** | `agents/**/*.md` in the plugin repo | Registered via plugin manifest |
| **Commands** | `commands/*.md` in the plugin repo | Registered via plugin manifest |
| **Optional rule sets** | `templates/user-rules/*.md` in the plugin repo | Copied into users' `.claude/rules/` by `/setup` command, with user consent |

**The user's own CLAUDE.md and rules are never touched by the plugin directly.** `/setup` can offer to install optional rules, but installation is opt-in.

## G.4 Corrections to Appendix D §8.5 (the "22 Rules" Inventory)

The original 22-rule list conflated three different things. Here's the corrected classification:

| Original name | Corrected classification | Rationale |
|---|---|---|
| session-lifecycle | **Rule (plugin's own `.claude/rules/`)** | Describes how the plugin's own sessions work; needed for dogfooded development |
| context-preservation | **Rule (plugin's own)** | Same reason |
| hooks | **Rule (plugin's own)** | Hook development conventions for the plugin's own hooks |
| testing | **Rule (plugin's own) + Skill (shipped)** | Test conventions for plugin + shipped as skill for users |
| python-standards | **Skill (shipped)** | Target: users' Python code. Auto-invokes on `**/*.py` |
| javascript-standards | **Skill (shipped)** | Target: users' JavaScript. Auto-invokes on `**/*.{js,jsx,ts,tsx}` |
| api-contracts | **Skill (shipped)** | Target: users' API layer |
| database | **Skill (shipped)** | Target: users' data layer |
| security | **Skill (shipped) + Rule (plugin's own)** | Critical enough to have both: skill for users, rule for plugin's own code |
| anti-rationalization | **Rule (plugin's own)** | Agent-behaviour constraint for the plugin's own agents |
| design-patterns | **Skill (shipped)** | Target: users' design decisions |
| naming-database | **Skill (shipped)** | Target: users' database |
| naming-api | **Skill (shipped)** | Target: users' API |
| naming-env-vars | **Skill (shipped)** | Target: users' config |
| naming-git | **Skill (shipped)** | Target: users' git workflow |
| naming-observability | **Skill (shipped)** | Target: users' telemetry |
| naming-cicd | **Skill (shipped)** | Target: users' CI config |
| naming-containers | **Skill (shipped)** | Target: users' Docker/k8s |
| os-safety | **Rule (plugin's own) + Skill (shipped)** | Plugin must be os-safe internally; users should also be |
| agent-coordination | **Rule (plugin's own)** | Agent-coordination rules for the plugin's own agent fleet |
| telemetry | **Rule (plugin's own)** | Plugin's internal telemetry conventions |
| agentic-failure-modes | **Rule (plugin's own)** | Constraints on the plugin's own agents to avoid known failure modes |

**Revised totals:**

- **Rules in the plugin's own repo** (`.claude/rules/`): **11** — session-lifecycle, context-preservation, hooks, testing-plugin, anti-rationalization, os-safety-internal, agent-coordination, telemetry, agentic-failure-modes, security-internal, agent-frontmatter (new — describes how to write plugin agents)
- **Skills shipped by the plugin** (`skills/<name>/SKILL.md`): **14** — python-standards, javascript-standards, api-contracts, database, security-user, design-patterns, testing-user, naming-database, naming-api, naming-env-vars, naming-git, naming-observability, naming-cicd, naming-containers, os-safety-user (15 actually; I listed 15 above; will recount in §G.9)
- **User-project rule templates** (`templates/user-rules/*.md` for opt-in install): same as skills in content, different in delivery — users who want mechanical enforcement (rules fire at session start) rather than contextual hint-loading (skills fire on file access) opt in

The plan previously claimed "22 rules" as a single category. The truth is: 11 rules for the plugin's own dogfooded development + 15 skills for users + optional rule templates. These are not the same thing and should not be counted as one.

## G.5 The `@include` Composition Mechanism

Claude Code supports `@path` syntax in instruction files to include other files. This is the composition primitive that lets the hierarchy work: small top-level files include specific reference files on demand.

Example `.claude/CLAUDE.md` at the plugin repo root (~60 lines):

```markdown
# dev-standards-plugin

This repo IS the framework. We dogfood it on itself.

## Where to look first

- Editing a hook? → `hooks/CLAUDE.md`
- Editing an agent? → `agents/CLAUDE.md` (then category-specific: `agents/meta/CLAUDE.md`, etc.)
- Editing a schema? → `schemas/CLAUDE.md`
- Editing a skill? → `skills/CLAUDE.md`
- Editing documentation? → `docs/CLAUDE.md`

## Core invariants (always-loaded)

@docs/architecture/primitives/psf.md
@docs/architecture/primitives/stamp-model.md
@docs/architecture/primitives/bootstrap-first.md
@docs/architecture/primitives/dogfooding.md

## Current phase

@.current_phase

## What NOT to do

- Never commit to `master` directly (branch protection enforces this)
- Never skip the `/validate` gate (stamp enforcement blocks commits)
- Never add to Phase 1 bootstrap beyond the locked scope contract in `docs/architecture/phases/phase-1-bootstrap.md`
- Never load more than 5 primitives in a single CLAUDE.md file (context budget)
```

This is ~60 lines. The `@include` statements pull in primitives only when Claude reads the file. Each included file is also <200 lines. An agent orienting in the repo gets ~60 + ~600 (3 primitives @ ~200 each) = ~660 lines of always-loaded context, not 2200.

## G.6 Size Limits and Mechanical Enforcement

A new bootstrap hook enforces the size limits:

**`hooks/post_edit_doc_size.py`** (PostToolUse on `Edit`/`Write` matching `**/*.md`)

- **Warn:** file exceeds 150 lines
- **Block:** file exceeds 200 lines (exit 2)
- **Exempt paths:** `C:\Users\jmarks01\.claude\plans\**` (the canonical plan is a decision record, not runtime); `tmp/**`; `node_modules/**`; `CHANGELOG.md`; `README.md` at repo root (user-facing, size requirements differ)
- **Configuration:** `config/doc-size-limits.json` — hard limits per pattern (e.g., `SKILL.md <500`, `CLAUDE.md <200`, `rules/*.md <200`, `docs/architecture/primitives/*.md <200`, `docs/architecture/phases/*.md <200`)

This hook is added to the **bootstrap scope (Phase 1)** — making the size limit mechanically enforced from day one. Otherwise the same dogfooding failure recurs.

## G.7 InstructionsLoaded Hook for Observability

The `InstructionsLoaded` hook (observation-only, cannot block) fires with fields including `file_path`, `memory_type`, `load_reason`, and `trigger_file_path`. We use it in Phase 4 (telemetry) to:

1. **Audit what loaded in each session** — write JSONL to `${CLAUDE_PLUGIN_DATA}/framework-memory/telemetry/instructions-loaded.jsonl`
2. **Detect redundant loads** — same file loaded N times in one session suggests poor organization
3. **Detect missing loads** — agent working in a category whose category CLAUDE.md never fired suggests the path-scoping broke
4. **Feed `closed-loop-quality-scorer`** — per-agent context cost metric

The hook is **informational only**. It cannot enforce loading discipline. Enforcement is via `post_edit_doc_size.py` (hard limits) and via code review of the hierarchy structure.

## G.8 Phase 0 Rework — What Changes

The current Phase 0 branch `feat/architecture-lockdown` has two commits. Commit 1 (Python tooling) is fine. Commit 2 (schemas + docs) has a structural problem: `docs/architecture/README.md` claims the canonical plan is the runtime reference (it can't be), and `docs/architecture/bootstrap-spec.md` is borderline size (~200 lines). The schemas themselves are correct and stay.

### G.8.1 What to undo

`git reset --soft HEAD~1` in the working branch to unstage commit 2. The 4 schemas remain on disk (correct), the 2 doc files remain on disk (to be replaced).

### G.8.2 What to add

New Phase 0 deliverables, replacing the 2 original doc files with ~15 tiny ones. Each file is <200 lines. Size enforced by `post_edit_doc_size.py` once Phase 1 bootstrap lands.

**Root orientation (2 files, ~60 lines each):**
- `.claude/CLAUDE.md` — repo entry point, uses `@include` for primitives
- `CLAUDE.md` at repo root — user-facing project overview (separate from `.claude/CLAUDE.md`; this one is loaded as a marker for the repo, often the first file Claude reads)

**Directory-scoped CLAUDE.md files (6 files, ~100-150 lines each):**
- `hooks/CLAUDE.md` — hook development conventions, `_hook_shared.py` patterns, validation step tuples (for when working in Phase 1+)
- `agents/CLAUDE.md` — agent frontmatter rules, R/R/W tiering, stamp invariants (for when working on agents)
- `schemas/CLAUDE.md` — JSON Schema draft version, naming conventions, self-validation requirement
- `commands/CLAUDE.md` — command composition rules, context fork behaviour, phase assignment
- `skills/CLAUDE.md` — skill authoring conventions, `paths:` frontmatter, size limits (<500 lines, <250 char descriptions)
- `docs/CLAUDE.md` — documentation conventions, size limits, `@include` usage

**Primitive docs (7 files, each <200 lines):**
- `docs/architecture/primitives/README.md` — index of primitives
- `docs/architecture/primitives/psf.md` — Primitive Selection Framework (from plan §3)
- `docs/architecture/primitives/four-tier-memory.md` — memory tiers (from plan §5)
- `docs/architecture/primitives/rrw-tiering.md` — R/R/W tiering (from Appendix F §F.2)
- `docs/architecture/primitives/stamp-model.md` — 3+ stamp model (from plan §6.4)
- `docs/architecture/primitives/bootstrap-first.md` — bootstrap-first sequencing (from Appendix D)
- `docs/architecture/primitives/dogfooding.md` — the dogfooding principle (with this Appendix G failure as a worked example)
- `docs/architecture/primitives/context-budget.md` — per-phase budgets + cache-aware pacing (from plan §5.2-§5.3)
- `docs/architecture/primitives/documentation-as-code.md` — this appendix distilled (from Appendix G)

That's 9 primitive files (I listed 9 above, not 7). Count matters; updating elsewhere.

**Phase specs (12 files, each <200 lines):**
- `docs/architecture/phases/README.md` — index of phases
- `docs/architecture/phases/phase-0.md` — Phase 0 architecture lockdown spec (what this branch is doing)
- `docs/architecture/phases/phase-1-bootstrap.md` — Phase 1 bootstrap (replaces original `docs/architecture/bootstrap-spec.md`)
- `docs/architecture/phases/phase-2.md` through `docs/architecture/phases/phase-11.md` — one file per phase, placeholders for now with the summary + exit criteria

**Architecture index (1 file, <100 lines):**
- `docs/architecture/README.md` — rewritten as a pure pointer; links to primitives/ and phases/; does NOT claim the canonical plan is the runtime reference

**Plugin-vs-project clarification doc (1 file, <200 lines):**
- `docs/architecture/primitives/plugin-vs-project.md` — explains the duality (plugin's own dogfooded dev vs user projects with the plugin installed), clarifies what ships and what doesn't

### G.8.3 Revised Phase 0 file count

| Category | Files | Typical size |
|---|---|---|
| Schemas | 4 | (variable, not prose) |
| Root CLAUDE.md | 2 | ~60 lines each |
| Directory CLAUDE.md | 6 | ~100-150 lines each |
| Primitive docs | 9 | <200 lines each |
| Phase docs | 12 | <200 lines each |
| Architecture index | 1 | <100 lines |
| Plugin-vs-project doc | 1 | <200 lines |
| **Total Phase 0** | **35 files** | all text files together <~5000 lines vs. original ~400 lines of 2 doc files (+ 2200 lines the old README pointed at) |

Phase 0 grew from 6 files to 35 files. Individual files are much smaller and each has a single clear concern. Total words is larger, but the **maximum context any single agent loads** is much smaller because loading is lazy and scoped.

### G.8.4 Retroactive branch cleanup

Current `feat/architecture-lockdown` state:
- Commit 1: `16cdc59 chore(tooling): add uv venv and pyproject.toml for plugin dev env` — **keep**
- Commit 2: `efbace3 docs(architecture): lock bootstrap spec and foundational schemas` — **soft reset** to reclaim the files, replace the 2 doc files with the 35-file structure, re-commit

Proposed sequence after plan approval:

```
git reset --soft HEAD~1                            # unstage commit 2, keep files
rm docs/architecture/README.md                     # replace
rm docs/architecture/bootstrap-spec.md             # replace
# write the 35 new files per §G.8.2
git add schemas/ docs/ .claude/ CLAUDE.md
git commit -m "docs(architecture): lock schemas, hierarchical docs, and directory CLAUDE.md (Phase 0)"
```

Branch still has 2 commits, both under the `feat/architecture-lockdown` name. Nothing pushed. Fully reversible.

## G.9 Phase 1 Bootstrap Impact

The Phase 1 bootstrap grows by two items:

1. **`hooks/post_edit_doc_size.py`** — PostToolUse hook enforcing the <200 line limit on markdown files. New bootstrap file. Adds the 13th core hook (was 12).

2. **`config/doc-size-limits.json`** — configuration for the hook. New bootstrap file.

Bootstrap file count: 33 → **35**. The 200-line limit becomes mechanically enforced from Phase 1 exit.

Phase 1 exit gate gets an 11th assertion:

11. `hooks/post_edit_doc_size.py` correctly blocks a deliberately oversized markdown file (201 lines) and correctly allows a compliant file (150 lines).

## G.10 Revised Totals

| Dimension | After Appendix F | After Appendix G | Delta |
|---|---|---|---|
| Agents | 156 | 156 | unchanged |
| Commands | 28 | 28 | unchanged |
| Hooks (full framework) | 38 | **39** | +1 (`post_edit_doc_size.py`) |
| Schemas | 17 | 17 | unchanged |
| **Rules (plugin's own `.claude/rules/`)** | 22 (mis-counted) | **11** | -11 (rescope) |
| **Skills (shipped to users)** | 6 (original) / 12 (F revised) | **26** (12 from F + 14 user-standards skills from G.4) | +14 net, but half are reclassified rules |
| **User-project rule templates** (opt-in via `/setup`) | (not counted) | **15** templates in `templates/user-rules/` | +15 new concept |
| Bootstrap file count | 33 | **35** | +2 (size-limit hook + config) |
| Phase 0 file count | 6 | **35** | +29 (structural decomposition) |
| Timeline (weeks) | ~27 | **~27** | unchanged |

The structural decomposition of Phase 0 doesn't add weeks because the total volume of prose is comparable — we're slicing the same content into smaller files. The bootstrap size-limit hook is a half-day addition.

## G.11 The Dogfooding Save Worth Recording

The mistake that generated this amendment — writing a 2200-line plan as the canonical reference and pointing a 120-line README at it — is exactly the kind of mistake the framework exists to prevent. Record it in `docs/architecture/primitives/dogfooding.md` as a worked example:

> **Example failure mode: the monolithic plan.** During Phase 0 of dev-standards-plugin v2, the architecture plan was authored as a single 2200-line file and referenced from a top-level README. An agent asking "what does the stamp model say?" would have loaded the entire plan to find the answer. Per-phase context budgets (40K-120K tokens) would have been 25-50% consumed before any work began. This violated four of the plan's own principles (PSF, four-tier memory, per-phase budgets, selective loading) simultaneously. The fix: decompose into <200-line files with path-scoped lazy loading via CLAUDE.md hierarchy, `@include` composition, and a mechanically-enforced `post_edit_doc_size.py` hook. **Lesson: every architectural principle must be applied to the architecture artifact itself. If the documentation structure violates the framework's own rules, those rules aren't yet internalized.**

## G.12 What Appendix G Commits To

- **Documentation is decomposed** into the six-tier hierarchy (T1-T5 runtime + T6 archived plan)
- **Every runtime documentation file is <200 lines**, enforced mechanically by `post_edit_doc_size.py`
- **`.claude/CLAUDE.md` at the plugin repo root** is the entry point, <100 lines, uses `@include` for always-loaded primitives
- **Subdirectory CLAUDE.md files** provide scoped context (hooks/CLAUDE.md, agents/CLAUDE.md, etc.), lazy-loaded on file access
- **Plugin-vs-project duality is explicit**: the plugin ships **skills**; the plugin's own repo has **rules** for dogfooded development; **optional rule templates** in `templates/user-rules/` can be copied into user projects by `/setup`
- **Corrected rule count**: 11 plugin-internal rules (was incorrectly 22), 14 user-facing skills (newly classified from the old rule list), 15 opt-in user rule templates
- **New Phase 1 hook**: `post_edit_doc_size.py` enforces the 200-line limit from the bootstrap onwards
- **Phase 0 rework**: the existing commit 2 on `feat/architecture-lockdown` is soft-reset and replaced with 35 tiny files instead of 2 overlong ones
- **The canonical plan file** (`cozy-doodling-church.md`) stays as a decision record in user memory but is **never loaded at runtime** by agents doing work
- **Bootstrap file count**: 33 → 35
- **InstructionsLoaded hook** used in Phase 4 for observability only (cannot enforce; enforcement is via size-limit hook + code review)
- **The documentation failure itself is recorded** as a worked example in `docs/architecture/primitives/dogfooding.md` — the very amendment becomes a dogfooding artifact

Next action after approval: soft-reset commit 2 on `feat/architecture-lockdown`, replace the two doc files with the 35-file structure per §G.8.2, verify sizes with a script equivalent to the Phase 1 `post_edit_doc_size.py` hook, re-commit on the same branch. The branch still has 2 commits when done (tooling + the corrected docs commit). Nothing pushed, fully reversible. Then complete Phase 0 with a revised exit verification pass that also asserts the size limits.

---

# Appendix H — Context Awareness + Public Plugin Security + Documentation Taxonomy

**Amendment status:** proposed 2026-04-11, combines Appendix G's documentation restructure with answers to ten clarifying questions about context awareness, session chunking, public plugin security posture, and documentation taxonomy. Supersedes the revised Phase 0 deliverables from §G.8.2 with a refined 35-file list anchored in the Diataxis documentation taxonomy. Adds ~8 items to the Phase 1 bootstrap. **Does not change:** PSF, memory tiers, closed-loop architecture, R/R/W tiering, 156-agent catalog, or the 11-phase roadmap.

## H.1 Context Awareness — Absolute, Not Relative

### H.1.1 The lost-in-the-middle reality and the 1M trap

Liu et al. ("Lost in the Middle: How Language Models Use Long Contexts", 2023) showed LLMs have a U-shaped attention curve: strong at the beginning and end of context, weak in the middle. As the context window widens, **the middle widens proportionally**. A 200K session with 150K in the middle is already compromised; a 1M session with 900K in the middle is effectively unreliable for anything placed there.

Anthropic's decision to expand Opus 4.6 to 1M tokens **doesn't help**; it makes some things demonstrably worse. A framework that wants to defend against LITM cannot use **relative** thresholds (70%, 85%, 95% of the active model's max), because those thresholds silently expand when the window does. We need **absolute** thresholds tied to attention quality, not to model capacity.

### H.1.2 Guideline budgets + one dynamic hard constraint

The framework enforces **one** hard constraint: **never enter Claude Code's auto-compaction zone**. Compaction is guaranteed context loss in the middle and is forbidden as a safety mechanism. Everything else is **guideline values** the session planner uses to inform task decomposition — not hard blocks that stop work.

**Why guidelines, not hard absolute limits:** arbitrary absolute cuts (e.g., "100K exit 2") are damned-if-we-do-damned-if-we-don't. Too low and legitimate work gets interrupted; too high and LITM degrades quality silently. The honest answer is "as small as possible, as large as necessary, smaller always preferable" — git-commit-sized chunks where the planner decides based on the work, not a fixed threshold.

**The one hard constraint — dynamic by model:**

CC auto-compacts at ~83.5% of the active model's window (per research in Appendix G §G.2.1). The framework forces `/handoff` at **75% of the compaction threshold** — about **62% of the active model's window** — with a generous buffer so we never trip compaction. This is dynamic; it depends on which model is active at runtime.

| Active model | Window | Compaction fires at | Framework hard cut (75% of compaction) |
|---|---|---|---|
| Sonnet 200K | 200K | ~167K | **~125K** |
| Opus 200K | 200K | ~167K | **~125K** |
| Opus 1M | 1M | ~835K | **~625K** (nominal; LITM makes this unusable — see guidelines) |

`hooks/_hook_shared.py` exposes `compute_hard_cut()` which reads the active model's metadata (via Claude Code's statusline data or environment) and returns the cut in tokens. `hooks/context_budget.py` uses this to decide when to exit 2.

**The guidelines — informational, not enforced:**

Because LITM degrades attention quality well below the model's nominal capacity, the framework also carries **guideline values** the session planner uses when sizing and decomposing work. These are inputs to `meta-session-planner`'s logic, **not hooks that block work**.

| Guideline | Typical tokens | Meaning for the planner |
|---|---|---|
| Comfort | 40K | Preferred task size — attention is strongest, cheap to debug, smallest meaningful commit |
| Soft warn | 60K | Plan a natural handoff point in the next few turns |
| Attention ceiling | 80K | LITM effects noticeable; planner **strongly prefers** decomposition but does not block |
| Dynamic hard cut | see table above | The one real block; forces `/handoff` |

The planner uses guidelines to emit **bite-sized task plans** where each item is ideally comfort-sized, has an explicit `/validate` checkpoint, and ends with a clean git commit + session handoff point. The principle: **one commit per task, one task per session where possible, smaller is always better.**

Per-phase budgets from plan §5.2 are reinterpreted as *suggested* planner targets, not enforced ceilings:

| Phase | Suggested target | Planner behaviour if exceeded |
|---|---|---|
| Discover | 40K | Decompose interview into smaller rounds |
| Research | 80K suggested (was 120K) | Decompose into focused spikes |
| Design | 80K suggested (was 100K) | Decompose into design-document-per-component |
| Develop (scaffold) | 30K | Split by module |
| Develop (tdd) | 60K | Split by test suite |
| Validate | 50K | Split by gate category |
| Test | 40K | Split by test tier |
| Deploy | 30K | Single commit target |
| Operate | 80K | Split by incident scope |
| Maintain | 40K | Single dep update target |

**Git-commit discipline as the corrective:** if a session produces more than one commit's worth of work, it was too big. The planner flags this for retrospective analysis by `closed-loop-incident-retrospective-analyst`.

### H.1.3 Never compact — force handoff at the dynamic cut

**Enforcement:** `hooks/context_budget.py` monitors `.claude/.context_pct` (written by `hooks/statusline.py`). When the session's estimated token count reaches `compute_hard_cut()` for the active model, the hook exits 2 on every subsequent UserPromptSubmit until `/handoff` runs. The user cannot work further until handoff completes. The guidelines below the cut emit warnings but never block.

**`bootstrap-smoke.py` assertion:** setting a synthetic transcript to `compute_hard_cut() + 1` tokens and a subsequent UserPromptSubmit must exit 2 with a message instructing the user to run `/handoff`. Setting it to `compute_hard_cut() - 1` must NOT exit 2 (even if above the 80K guideline). This verifies guidelines don't block and the hard cut does.

### H.1.4 Agent-driven session chunking: `meta-session-planner`

New bootstrap agent **`meta-session-planner`** (blocking, opus, maxTurns 10, tier `reason`) — the planner that sizes every session.

**Invocation:** automatically at the start of any `/tdd`, `/scaffold`, `/fix`, `/debug`, `/refactor`, `/design`, `/research`, `/pattern`, `/document`, `/incident`, `/maintain`. Invoked by the command itself as its first step.

**Process:**
1. Read the stated objective + current session state
2. Estimate token cost of the proposed work (file reads, diffs, subagents, tool calls)
3. Compare against the phase's absolute budget AND the remaining session budget
4. If the work fits comfortably (<60% of remaining): proceed
5. If tight (60-80%): proceed but surface a warning + planned checkpoint
6. If too large (>80% or exceeds absolute 80K): **decompose** into 2-4 sub-tasks, each with its own objective, its own budget, its own handoff checkpoint
7. Emit a session plan to `session-state.md` as the "Task Progress" list with estimated tokens per task
8. Each task has an explicit `/validate` + `/handoff` marker at completion

**Enforcement:** commands that skip `meta-session-planner` are blocked by the exit gate (`meta-command-composition-reviewer` detects missing composition, blocks commit via the agent-validation-stamp).

**Bootstrap impact:** +1 agent. Moves from 7 core agents to 8.

### H.1.5 Rolling summarizer behaviour

`closed-loop-context-rolling-summarizer` **pulled from Phase 4 into Phase 1 bootstrap**. Fires at 60K absolute tokens (the warn threshold). Preserves verbatim:

- **All CLAUDE.md content** (re-read from disk by CC, we don't touch it)
- **The last 5 user messages**
- **The last 5 tool results**
- **Any structured agent verdict** in the last 20 turns (they carry evidence and often catch LITM failures)
- **The current objective** from `session-state.md`

Compresses everything older into a single **structured summary block** placed immediately before the current turn (near the attention hotspot, away from the LITM zone). Summary format:

```markdown
# Session summary (rolling, generated at <timestamp>)
## Decisions made
- ...
## Actions taken
- ...
## Open threads / deferred items
- ...  (fed to closed-loop-transcript-todo-extractor)
## Known errors and resolutions
- ...
## Current state
- ...
```

**Model:** haiku. This is summarization, not reasoning. Fast and cheap.

**Bootstrap impact:** +1 agent. Moves from 8 core agents to 9.

### H.1.6 Automatic session-state checkpoints

**`hooks/session_checkpoint.py`** (PostToolUse matching `Edit|Write`) writes session-state.md every N qualifying events:

- Every **5 Edit/Write operations** (rough proxy for "meaningful work done")
- Or every **15 minutes** (time-based safety net)
- Or **every phase transition** (forced by `hooks/phase_transition.py`)

Avoids the "session crashed mid-work, all state lost" failure mode. Without this, `session-state.md` only updates on SessionEnd + PreCompact + handoff — a crash between those points loses everything.

**Bootstrap impact:** +1 hook. Moves from 12 core hooks to 13.

### H.1.7 The statusline

**`hooks/statusline.py`** — ported from Modelling's existing pattern. Reads current context usage from Claude Code's statusline mechanism, writes `%` + absolute-token estimate + current-phase marker to `.claude/.context_pct` continuously.

Consumed by: `hooks/context_budget.py` (for threshold decisions), `hooks/session_checkpoint.py` (for time-based triggers), humans viewing the status line.

**Bootstrap impact:** +1 hook. Moves from 13 to 14.

## H.2 Setup Agent + Interview Flow

### H.2.1 `discover-setup-wizard`

Users installing the plugin get a **conversational setup wizard** on first `/setup` run. For the plugin's own dogfooded development, it uses defaults — no interview needed.

**New agent `discover-setup-wizard`** (advisory, sonnet, maxTurns 15, tier `read-reason`). Invoked by the bootstrap `/setup` command when `.claude/.dsp-config.json` does not exist in the target project.

**Interview phases:**

1. **Project detection** (read-only): language, framework, monorepo yes/no, existing test layout, database presence, API routes, production deployment markers. Feeds `discover-project-state-classifier` (greenfield / growing-green / brownfield).
2. **Goals and constraints**: user answers "what are you trying to achieve" + "what's off-limits" + "team size" + "preferred strictness level"
3. **Stack preferences**: which profiles to activate, whether to install opt-in user-rule templates
4. **Security posture**: opt-in telemetry yes/no, secret scanning strictness, allowed network egress
5. **Confirmation**: write `.claude/.dsp-config.json` with the answers, show the user what will happen on the next session

**Config persistence:** `.claude/.dsp-config.json` (schema in `schemas/dsp-config.schema.json` — added Phase 2). Read at every session start by `hooks/session_start.py`. Defaults apply for unset fields.

**Bootstrap impact:** +1 agent. Moves from 9 to 10 core agents.

## H.3 Public Plugin Security

### H.3.1 The posture

`dev-standards-plugin` will be a **public open-source repository**, self-serve install (not marketplace). This changes the security calculus:

- Accidentally committing a secret is **public disclosure**, not just a team-internal leak
- The repo's `.gitignore` must be comprehensive from day one
- The plugin's own development must be exemplary — users will read the code
- A visible `SECURITY.md` is table stakes
- Security agents must land **early**, not in Phase 9

### H.3.2 Phase 1 bootstrap security additions

Three new hooks and one new repo file, all in Phase 1:

**`hooks/pre_write_secret_scan.py`** (PreToolUse on `Edit|Write`). Regex-based scanner that blocks on:
- AWS access keys (`AKIA[0-9A-Z]{16}`)
- AWS secret keys (pattern-based + length-based entropy check)
- GitHub tokens (`ghp_`, `gho_`, `ghu_`, `ghs_`, `ghr_` prefixes)
- OpenAI keys (`sk-proj-`, `sk-`)
- Anthropic keys (`sk-ant-`)
- Private keys (`-----BEGIN (RSA|EC|DSA|OPENSSH) PRIVATE KEY-----`)
- Generic patterns: `password\s*=\s*["'][^"']{8,}`, `api[_-]?key\s*=\s*["'][^"']{16,}`, `secret\s*=\s*["'][^"']{16,}`
- `.env` file creation (blocks unless the file is already tracked as a template)
- `*.pem`, `*.key`, `*.p12`, `credentials.json`, `secrets.json` (blocks write if filename matches)

Exit 2 with a pointer to `docs/architecture/principles/security.md` on match.

**`hooks/session_start_gitignore_audit.py`** (SessionStart). Validates `.gitignore` contains all critical patterns. Warns (not blocks) if any are missing:

- `.env`, `.env.*`, `*.pem`, `*.key`, `*.p12`, `credentials.json`, `secrets.json`, `.secrets/`
- `.venv/`, `venv/`, `.uv/`
- `node_modules/`, `dist/`, `build/`
- `.claude/settings.local.json`, `CLAUDE.local.md`
- `__pycache__/`, `*.pyc`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`
- Any OS temp files

Emits a warning on the first SessionStart of the day if any are missing. Does not block — the user might have intentional exclusions.

**`hooks/pre_commit_security_gate.py`** (PreToolUse on Bash matching `git commit`). Runs the same regex scan over the staged diff just before commit. A final belt on top of the PreToolUse braces. Exit 2 on match.

**`SECURITY.md`** at repo root. Public-plugin best practice. Template content:
- Supported versions (just `main` for now)
- Reporting a vulnerability (private email, 48-hour acknowledgment)
- Disclosure policy
- Known security considerations (it's a plugin that runs hooks; users should review before installing)

**Bootstrap impact:** +2 hooks (`pre_write_secret_scan.py`, `session_start_gitignore_audit.py`; `pre_commit_security_gate.py` is a specific matcher on the existing `pre_commit_cli_gate.py`, no new file), +1 repo file (`SECURITY.md`). Moves from 14 to 16 core hooks.

### H.3.3 Phase 2-3 security follow-on

- **Phase 2:** Full `security-secret-scanner` agent replaces the regex hook (adds entropy-based detection, git history scan, reduces false positives). `security-dep-vuln-scanner` agent (checks `uv.lock`, `package-lock.json` against CVE feeds).
- **Phase 3:** `security-license-compliance` agent. Ensures all deps are MIT-compatible (since the plugin is MIT-licensed).
- **Phase 9:** Original Phase 9 security agents (`security-sast-runner`, `security-sbom-generator`, `security-threat-modeler`) — unchanged from plan.

### H.3.4 Telemetry defaults

**Change `userConfig.telemetryOptIn` from `true` to `false`.** Public-plugin best practice: opt-in by default, not opt-out.

Additional constraints (encoded in `docs/architecture/principles/security.md`):

- **Local-only by default.** Telemetry writes to `${CLAUDE_PLUGIN_DATA}/framework-memory/telemetry/`. Never leaves the machine unless the user also opts in to export.
- **Minimum data.** Agent name, invocation timestamp, latency, verdict (pass/fail), token count. **Never:** code content, user prompts, file paths, repo origin URL without explicit export consent.
- **Documented fields.** `docs/architecture/principles/security.md` lists every field telemetry collects, with rationale.
- **User can disable entirely.** `userConfig.telemetryOptIn: false` (default) means no hooks emit telemetry at all.

### H.3.5 Minimal GitHub Actions in Phase 2

A single workflow file added in Phase 2:

```yaml
# .github/workflows/validate.yml (Phase 2 deliverable)
name: Validate
on: [push, pull_request]
jobs:
  validate:
    runs-on: ubuntu-latest  # Unix-supported dogfooding
    steps:
      - checkout
      - setup Python 3.13 + uv
      - uv sync --group dev
      - ruff check && ruff format --check
      - mypy --strict hooks/ scripts/
      - pytest
      - run bootstrap-smoke.py
      - doc-size check (post_edit_doc_size.py equivalent)
      - schema self-validate
```

**Not in Phase 1** because the bootstrap must be self-sufficient locally first. **Not in Phase 11** because we want dogfooding on Unix parallel to Windows development from early days.

### H.3.6 Self-serve distribution (not marketplace)

Per Q7, the plugin is not going to the Claude Code marketplace anytime soon. Phase 11 scope revised:

- **Drop:** marketplace submission, npm publish, CLA, privacy policy, terms of use
- **Keep:** public GitHub repo (required for install), README with install instructions, LICENSE (MIT, already present), SECURITY.md (Phase 1), release tags, CHANGELOG (already present)
- **Add:** `docs/guides/installing-the-plugin.md` (how a user clones and installs from this repo)

Phase 11 shrinks from 2 weeks to 1 week. Total timeline: ~27 → ~26 weeks.

## H.4 Documentation Taxonomy — Diataxis

### H.4.1 The four quadrants

Diataxis ([diataxis.fr](https://diataxis.fr)) is the dominant documentation taxonomy in software engineering. It splits documentation into four quadrants based on **user intent × content type**:

| | Practical (doing) | Theoretical (learning) |
|---|---|---|
| **Study** (acquiring skill) | **Tutorials** — learning-oriented, hand-held walkthroughs | **Explanation** — understanding-oriented, why-focused |
| **Work** (applying skill) | **How-to guides** — task-oriented, goal-focused | **Reference** — information-oriented, lookup-focused |

Each quadrant answers a different question:

- **Tutorials** — "I'm new, teach me"
- **How-to** — "I have a goal, how do I achieve it"
- **Reference** — "I need a fact, what is X"
- **Explanation** — "I want to understand, why is it like this"

Mixing quadrants in a single document is the most common documentation anti-pattern — it confuses all four readerships simultaneously.

### H.4.2 Proposed `docs/` structure

```
docs/
├── README.md                              # top-level orientation (<100 lines)
│
├── architecture/                          # EXPLANATION + REFERENCE
│   ├── README.md                          # index
│   │
│   ├── principles/                        # EXPLANATION — core concepts
│   │   ├── README.md
│   │   ├── psf.md                         # Primitive Selection Framework
│   │   ├── memory-tiers.md                # Four-tier memory
│   │   ├── rrw-tiering.md                 # Read/Reason/Write
│   │   ├── stamps.md                      # 3+ stamp validation model
│   │   ├── bootstrap-first.md             # Bootstrap sequencing
│   │   ├── dogfooding.md                  # Dogfooding principle + worked examples
│   │   ├── context-awareness.md           # LITM + absolute budgets + never compact
│   │   ├── plugin-vs-project.md           # The duality
│   │   ├── documentation-as-code.md       # Size limits + @include
│   │   └── security.md                    # Security posture + opt-in telemetry
│   │
│   ├── lifecycle/                         # EXPLANATION — how work flows
│   │   ├── README.md                      # index of lifecycle phases
│   │   └── (individual lifecycle stages written as each phase materializes)
│   │
│   └── components/                        # REFERENCE — the catalog
│       ├── README.md                      # index
│       └── (individual component catalogs written as components are built)
│
├── phases/                                # REFERENCE — implementation roadmap
│   ├── README.md                          # 11-phase overview
│   ├── phase-0-architecture-lockdown.md   # this phase
│   ├── phase-1-bootstrap.md               # next phase (moves here from bootstrap-spec.md)
│   └── (phase-2.md through phase-11.md as we approach each)
│
├── decision-records/                      # EXPLANATION — why we chose what we chose
│   ├── README.md                          # index + ADR conventions
│   ├── adr-001-graph-first-architecture.md
│   ├── adr-002-strict-default.md
│   ├── adr-003-bootstrap-first-sequencing.md
│   ├── adr-004-read-reason-write-tiering.md
│   ├── adr-005-documentation-as-code.md
│   ├── adr-006-context-awareness-absolute-budgets.md
│   └── v2-architecture-planning-session.md  # archived copy of cozy-doodling-church.md
│
└── guides/                                # HOW-TO — task-oriented
    ├── README.md
    ├── installing-the-plugin.md           # for users
    ├── developing-a-new-agent.md          # for contributors (us)
    ├── developing-a-new-hook.md           # for contributors
    ├── running-validation.md              # for users
    └── troubleshooting.md                 # for users
```

**Notably absent from Phase 0:** `docs/tutorials/`. Tutorials are learning-oriented walkthroughs for newcomers, which don't make sense before the plugin is usable. Defer to Phase 10-11.

**Also absent from Phase 0:** the bulk of `lifecycle/`, `components/`, most `phases/` stubs, most `guides/`. These get written as the relevant components materialize in later phases. Phase 0 ships the skeleton (README indexes) + the load-bearing content (principles, phase-0 and phase-1 specs, foundational ADRs, archived plan, minimal getting-started).

### H.4.3 Why this is human-intuitive

A developer wandering into the repo can find what they need by intent:

- "I want to understand why the framework exists" → `docs/architecture/principles/`
- "I want to know what agents exist" → `docs/architecture/components/agents.md`
- "I want to know what Phase 1 delivers" → `docs/phases/phase-1-bootstrap.md`
- "I want to see why we made this decision" → `docs/decision-records/`
- "I want to install the plugin" → `docs/guides/installing-the-plugin.md`
- "I want to add a new hook" → `docs/guides/developing-a-new-hook.md`

Each intent maps to a single folder. No mixed-concern files. Every file is <200 lines. Lazy-loading via `@include` from CLAUDE.md files means agents only load what they need.

### H.4.4 Archived vs runtime

The canonical plan (`cozy-doodling-church.md`) is copied into `docs/decision-records/v2-architecture-planning-session.md` in Phase 0. From that point forward:

- The **copy in the plugin repo** is the preserved version, git-tracked, version-controlled, backed up
- The **original in `~/.claude/plans/`** remains as a working document for this planning session only
- After Phase 0 merges, the user-memory version can be safely deleted (the repo copy is canonical)
- Neither version is **loaded at runtime** by working agents. Runtime references use `docs/architecture/principles/*.md` via `@include`.

## H.5 Revised Phase 0 Deliverables

Replaces §E.2 and §G.8.2. The `feat/architecture-lockdown` branch will contain **~53 files total**: 4 schemas (unchanged, already written), 3 tooling files (unchanged, already committed), plus ~46 new files organized per the Diataxis taxonomy.

### H.5.1 File manifest

**Root orientation (2 files):**
- `CLAUDE.md` — project root entry point, <100 lines, uses `@include` for critical principles
- `.claude/CLAUDE.md` — plugin-repo-specific context (may or may not overlap with root CLAUDE.md depending on convention — the research confirms either location works; we'll use root CLAUDE.md and not duplicate)

Revised: just **1 root CLAUDE.md** (no duplication) → saves 1 file. Total becomes 52.

**Directory-scoped CLAUDE.md (6 files, <150 lines each):**
- `hooks/CLAUDE.md`
- `agents/CLAUDE.md`
- `schemas/CLAUDE.md`
- `commands/CLAUDE.md`
- `skills/CLAUDE.md`
- `docs/CLAUDE.md`

**`docs/` tree (~40 files):**

*Top level (1):*
- `docs/README.md`

*architecture/ (1 index + 3 sub-indexes = 4):*
- `docs/architecture/README.md`
- `docs/architecture/principles/README.md`
- `docs/architecture/lifecycle/README.md`
- `docs/architecture/components/README.md`

*architecture/principles/ (10 files, each <200 lines):*
- `psf.md`
- `memory-tiers.md`
- `rrw-tiering.md`
- `stamps.md`
- `bootstrap-first.md`
- `dogfooding.md`
- `context-awareness.md`
- `plugin-vs-project.md`
- `documentation-as-code.md`
- `security.md`

*phases/ (3 files):*
- `docs/phases/README.md`
- `docs/phases/phase-0-architecture-lockdown.md`
- `docs/phases/phase-1-bootstrap.md`

*decision-records/ (8 files):*
- `docs/decision-records/README.md`
- `docs/decision-records/adr-001-graph-first-architecture.md`
- `docs/decision-records/adr-002-strict-default.md`
- `docs/decision-records/adr-003-bootstrap-first-sequencing.md`
- `docs/decision-records/adr-004-read-reason-write-tiering.md`
- `docs/decision-records/adr-005-documentation-as-code.md`
- `docs/decision-records/adr-006-context-awareness-absolute-budgets.md`
- `docs/decision-records/v2-architecture-planning-session.md` (archived canonical plan)

*guides/ (2 files):*
- `docs/guides/README.md`
- `docs/guides/getting-started.md`

**Repo root additions (1 file):**
- `SECURITY.md`

**Already committed or existing (unchanged):**
- `schemas/*.json` (4) — commit 1 and 2 of current branch
- `.python-version`, `pyproject.toml`, `uv.lock` (3) — commit 1
- `CHANGELOG.md`, `LICENSE`, `README.md`, `CONTRIBUTING.md` at repo root — already exist, minor updates may be needed

### H.5.2 Counts

| Category | New files |
|---|---|
| Root CLAUDE.md | 1 |
| Directory CLAUDE.md | 6 |
| docs/README.md | 1 |
| architecture/ + sub-indexes | 4 |
| principles (load-bearing) | 10 |
| phases (spec + two) | 3 |
| decision-records (index + 6 ADRs + archived plan) | 8 |
| guides (index + 1) | 2 |
| Repo root (SECURITY.md) | 1 |
| **Phase 0 new files** | **36** |
| Previously committed in this branch | 9 (4 schemas + 3 tooling + 2 docs to be replaced) |

Commit 2 gets soft-reset to reclaim the 2 stale doc files. Those 2 files are replaced by the 36 new files above. Net branch state after rework: 4 schemas + 3 tooling + 36 new docs = **43 files ahead of master**, across 2 clean commits.

### H.5.3 Phase 0 commit plan (revised)

1. **Commit 1** (already made): `chore(tooling): add uv venv and pyproject.toml for plugin dev env` — stays
2. **Commit 2** (soft-reset pending): replaced with `docs(architecture): lock schemas, diataxis taxonomy, principles, ADRs (Phase 0)` — includes the 4 schemas (unchanged) + 36 new doc files organized per Diataxis

After rework, both commits are conventional, each is a coherent logical unit, and the PR body references Appendices D/E/F/G/H of the canonical plan (with a note that the canonical plan is now archived at `docs/decision-records/v2-architecture-planning-session.md`).

## H.6 Revised Bootstrap (Phase 1) Scope

Phase 1 adds the context-awareness and security items from §H.1 and §H.3. Updated file counts:

### H.6.1 Bootstrap core hooks (was 12, now 16)

1. `session_start.py` (unchanged)
2. `session_end.py` (unchanged)
3. `pre_compact.py` (unchanged)
4. `post_compact.py` (unchanged)
5. `create_feature_branch.py` (unchanged)
6. `context_budget.py` (unchanged file, extended logic — absolute budgets, hard block, force handoff)
7. `branch_protection.py` (unchanged)
8. `pre_commit_cli_gate.py` (unchanged file, now also runs secret scan on staged diff)
9. `dangerous_command_block.py` (unchanged)
10. `post_edit_lint.py` (unchanged)
11. `post_auto_format.py` (unchanged)
12. `post_tool_failure.py` (unchanged)
13. **NEW: `statusline.py`** — context % + absolute token publisher (§H.1.7)
14. **NEW: `session_checkpoint.py`** — periodic auto-save (§H.1.6)
15. **NEW: `pre_write_secret_scan.py`** — regex secret scanner (§H.3.2)
16. **NEW: `session_start_gitignore_audit.py`** — gitignore validation (§H.3.2)

Plus the doc-size enforcer from §G.6: `post_edit_doc_size.py` (17 hooks total). And `subagent_stop.py` via hook type agent from Appendix F §F.8 for the transcript extractor. **Core hooks: 17.**

### H.6.2 Bootstrap core agents (was 7, now 10)

1. `meta-agent-scaffolder` (unchanged)
2. `meta-graph-registry-validator` (unchanged)
3. `meta-command-composition-reviewer` (unchanged)
4. `validation-objective-verifier` (unchanged)
5. `validation-completion-verifier` (unchanged)
6. `discover-project-state-classifier` (from Appendix F)
7. `closed-loop-transcript-todo-extractor` (from Appendix F)
8. **NEW: `meta-session-planner`** — agent-driven session chunking (§H.1.4)
9. **NEW: `closed-loop-context-rolling-summarizer`** — pulled from Phase 4 (§H.1.5)
10. **NEW: `discover-setup-wizard`** — interactive setup (§H.2.1)

### H.6.3 Bootstrap new total

- 5 shared modules (unchanged)
- **17 core hooks** (was 12 in original bootstrap-spec, 13 after Appendix F, 14 after Appendix G size enforcer, 17 now)
- 3 core commands (unchanged)
- **10 core agents** (was 5 original, 7 after Appendix F, 10 now)
- **6 schemas** (unchanged)
- 2 profiles (unchanged)
- 2 tooling scripts (unchanged)
- 1 config file (`config/doc-size-limits.json`, introduced in §G.6)

**Bootstrap file count: ~46 files.** Up from the original 31 in Appendix D §D.3 — but every addition has a direct, named justification tied to either context safety, security, or dogfooding discipline. No scope creep; every item mitigates a specific risk.

### H.6.4 Phase 1 exit gate (revised — now 13 assertions)

1. `/validate` runs cleanly against the bootstrap's own code
2. Deliberate scope violation blocked by `validation-objective-verifier`
3. Commit without stamp blocked by `pre_commit_cli_gate.py`
4. Commit with valid fresh stamp succeeds
5. Stamp > 15 min blocks commit
6. `[WIP]` bypass works
7. `.git/MERGE_HEAD` bypass works during conflict resolution
8. `write_agent_memory.py --agent ../../etc/passwd` rejected
9. Every bootstrap agent declares tier; tools/tier consistency enforced
10. `closed-loop-transcript-todo-extractor` extracts a deferred item from a synthetic transcript
11. `post_edit_doc_size.py` blocks a 201-line markdown file and allows a 150-line one
12. **NEW:** Synthetic transcript of 101K tokens + subsequent UserPromptSubmit exits 2 with "run /handoff" message (§H.1.3)
13. **NEW:** `pre_write_secret_scan.py` blocks a deliberate `AKIA*` string in a test file; `session_start_gitignore_audit.py` warns on a deliberately-stripped `.gitignore`

## H.7 Revised Totals

| Dimension | After Appendix G | After Appendix H | Delta |
|---|---|---|---|
| Agents | 156 | **156** | unchanged (no new agent types, just earlier bootstrap slotting of existing agents) |
| Commands | 28 | 28 | unchanged |
| Hooks (full framework) | 39 | **42** | +3 (`statusline.py`, `session_checkpoint.py`, `pre_write_secret_scan.py`, `session_start_gitignore_audit.py` — minus reuse of `pre_commit_cli_gate.py` for secret scan, net +3) |
| Schemas | 17 | 17 | unchanged |
| Bootstrap core agents | 7 | **10** | +3 (pulled earlier: session-planner, rolling-summarizer, setup-wizard) |
| Bootstrap core hooks | 13 | **17** | +4 (context + security hooks) |
| Bootstrap file count | 35 | **~46** | +11 |
| Phase 0 file count | 35 | **36** (+SECURITY.md) | +1 |
| Phase 1 exit-gate assertions | 11 | **13** | +2 |
| Timeline (weeks) | ~27 | **~26** | -1 (Phase 11 shrinks: no marketplace, self-serve only) |

## H.8 What Appendix H Commits To

### Context awareness (§H.1)
- **Absolute token budgets**, not relative percentages — 40K comfort, 60K warn, 80K hard, 100K force ceiling
- **Never compact** — force `/handoff` before CC's auto-compaction threshold fires; exit 2 on all work past 100K until handoff runs
- **Per-phase budgets capped at 80K** — research and design decomposed if larger
- **`meta-session-planner` in the bootstrap** — agent-driven decomposition before any significant work starts
- **`closed-loop-context-rolling-summarizer` pulled into bootstrap** from Phase 4 — fires at 60K, preserves last 5 turns + agent verdicts, compresses older content near current turn (dodging LITM)
- **`hooks/session_checkpoint.py`** — auto-saves session state every 5 edits / 15 min / phase transition
- **`hooks/statusline.py`** — ported from Modelling, publishes current context usage to `.claude/.context_pct`

### Setup agent (§H.2)
- **`discover-setup-wizard`** in the bootstrap — interactive project configuration for users; defaults-only for the plugin's own dogfooding
- **`.claude/.dsp-config.json`** persists user answers; read by `session_start.py`

### Security (§H.3)
- **`hooks/pre_write_secret_scan.py`** in bootstrap — regex scanner for AWS/GitHub/OpenAI/Anthropic/generic secrets + forbidden filenames
- **`hooks/session_start_gitignore_audit.py`** in bootstrap — validates `.gitignore` coverage
- **`SECURITY.md`** at repo root, Phase 0 deliverable
- **Phase 2 GitHub Actions workflow** — single `.github/workflows/validate.yml` running bootstrap gates on Ubuntu
- **Telemetry opt-in flipped to `false` default** — GDPR-friendly, trust-building for public plugin
- **Phase 11 shrinks** — no marketplace, no CLA, no privacy policy, no npm publish; self-serve via public GitHub only
- **Phase 2-3 agents** — full `security-secret-scanner`, `security-dep-vuln-scanner`, `security-license-compliance` pulled earlier than original Phase 9

### Documentation taxonomy (§H.4)
- **Diataxis-inspired structure** — `docs/architecture/` (principles + lifecycle + components), `docs/phases/`, `docs/decision-records/`, `docs/guides/`
- **4 principles docs, 3 phase docs, 7 ADRs, archived canonical plan, 2 guides, 1 SECURITY.md, 36 new files total in Phase 0**
- **Each file <200 lines**, mechanically enforced by `post_edit_doc_size.py` from Phase 1 exit onwards
- **Canonical plan archived to `docs/decision-records/v2-architecture-planning-session.md`** — git-preserved, no longer at risk of user-memory loss

### Retroactive branch fix
- Soft-reset commit 2 on `feat/architecture-lockdown`
- Replace the 2 stale doc files (README.md, bootstrap-spec.md) with the 36-file Diataxis structure
- Re-commit as `docs(architecture): lock schemas, diataxis taxonomy, principles, ADRs (Phase 0)`
- Nothing pushed, fully reversible

Next action after approval: execute the retroactive fix and ship Phase 0.
