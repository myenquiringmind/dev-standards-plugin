# Phase 5 — Exit Report

Phase 5 paid down the framework's oldest debt: thirteen v1 agents that lived as bare prompt files at the `agents/` flat root — no frontmatter, invisible to `build_graph_registry`, governed by no hook, constrained by no tier — are now first-class v2 agents. Each gained schema-valid frontmatter, a declared R/R/W tier, an AgentVerdict body, a category-subdir home, and a one-line successor annotation naming the Phase 6–10 agent(s) that will eventually supersede it. The framework's own agent population is now as disciplined as the agents it generates. `bootstrap_smoke` grew 33 → 37; a committed AgentVerdict contract closes the last verdict-shape ambiguity.

## What shipped

| Stream | Deliverables | PR |
|---|---|---|
| Spec | `docs/phases/phase-5-core-agent-refactor.md` | #100 |
| 2 — Validation cluster | `code-reviewer`, `validation-standards`, `lint-standards`, `type-standards` → `agents/validation/` | #101 |
| 3 — Doc/naming/testing | `doc-writer`→`document/doc-technical-writer`, `naming-standards`→`meta/meta-naming-standards-reviewer`, `test-standards`→`testing/testing-strategy-reviewer` | #102 |
| 4 — Operate/maintain | `investigator`, `logging-standards`, `error-standards`, `git-standards` → `operate/`; `housekeeping-standards`→`maintain/`; `standards-orchestrator`→`meta/meta-standards-orchestrator` | #103 |
| Exit gate | `agent-verdict.schema.json` + `bootstrap_smoke` 33→37 + live verdict check + this report; TR-0005 resolved | this PR |

Four implementation PRs across the phase (#100–#103), this PR closing. All 13 legacy agents retrofitted; `agents/` root holds only `CLAUDE.md`.

## The 13 retrofitted agents

| Legacy | v2 | Tier | Model |
|---|---|---|---|
| code-reviewer | `validation-code-reviewer` | write | sonnet |
| validation-standards | `validation-standards-reviewer` | write | sonnet |
| lint-standards | `validation-lint-reviewer` | write | haiku |
| type-standards | `validation-type-safety-reviewer` | write | sonnet |
| doc-writer | `doc-technical-writer` | write | sonnet |
| naming-standards | `meta-naming-standards-reviewer` | write | sonnet |
| test-standards | `testing-strategy-reviewer` | write | sonnet |
| investigator | `operate-root-cause-analyst` | reason | opus |
| logging-standards | `operate-logging-reviewer` | write | sonnet |
| error-standards | `operate-error-handling-reviewer` | write | sonnet |
| git-standards | `operate-git-workflow-reviewer` | write | sonnet |
| housekeeping-standards | `maintain-housekeeping-reviewer` | write | sonnet |
| standards-orchestrator | `meta-standards-orchestrator` | reason | opus |

All emit the canonical `{agent, status, confidence, findings}` verdict (the two reason-tier agents map `status` to resolved/inconclusive and `findings` to their analysis/plan).

## Mechanical gate results

`scripts/bootstrap_smoke.py` final run, against this branch:

```
[bootstrap-smoke] 34/37 [PASS] phase-5-flat-root-empty
[bootstrap-smoke] 35/37 [PASS] phase-5-retrofit-frontmatter - 13 agents
[bootstrap-smoke] 36/37 [PASS] phase-5-registry-discovers-retrofits - 13 nodes
[bootstrap-smoke] 37/37 [PASS] phase-5-retrofit-body-structure - 13 bodies
[bootstrap-smoke] 37/37 passed - Phase 1+2+3+4+5 exit gate OK
```

Exit gate: **37/37**. Full Python suite: **917/917** (908 + 9 agent-verdict schema tests). ruff, ruff-format, mypy-strict all clean. Graph registry: 78 → **91** nodes (the 13 retrofits; the legacy files were never registry nodes).

The four Phase 5 assertions map onto the spec's exit-gate bullets:

| # | Assertion | What it proves |
|---|---|---|
| 34 | `phase-5-flat-root-empty` | no v1 flat-root agent remains; `agents/*.md` is only `CLAUDE.md` |
| 35 | `phase-5-retrofit-frontmatter` | all 13 retrofits have schema-valid frontmatter with a tier consistent with their tools (schema `allOf` passes) |
| 36 | `phase-5-registry-discovers-retrofits` | `build_graph_registry` emits all 13 as nodes (built to a throwaway path and checked) |
| 37 | `phase-5-retrofit-body-structure` | each body carries the arch-doc-reviewer structure — `# <name>` + `## Procedure` + `## Output` + `## Do not` |

`scripts/live_integration_smoke.py` gains check 34 (`retrofit-verdict-live`): `validation-standards-reviewer` is run against a synthetic SQL-injection diff and its JSON output validated against the committed `agent-verdict.schema.json` — skip-when-no-`ANTHROPIC_API_KEY`, so unkeyed CI is unaffected.

## TR-0005 — resolved

The three coexisting AgentVerdict shapes are reconciled:

- **Canonical shape** `{agent, status, confidence, findings}` is pinned by `schemas/contracts/agent-verdict.schema.json` and governs all 13 retrofit agents plus every future verdict-emitting reviewer/analyst.
- The Phase 5 spec's retrofit-contract wording was amended from the planning-session `{ok, reason, confidence, evidence}` to the canonical shape (`ok→status`, `evidence→findings`, `confidence` retained).
- The two Phase 1 scope-verifiers (`validation-objective-verifier`, `validation-completion-verifier`) keep their richer `{agent, status, errors, classifications}` variant **by design** — it feeds `/validate`'s stamp flow, which keys on `status`. Restructuring them to `findings` is unnecessary (the gate is unaffected) and higher-risk than the value warrants, so this resolution scopes the canonical schema to the verdict family and documents the verifiers as a sanctioned variant rather than forcing them to conform.

This is a deliberate narrowing of TR-0005's original step 3/4 (which proposed touching the verifiers): the contract's purpose — a committed schema for the live check and future agents — is fully served without modifying gate-feeding agents.

## Design decisions recorded in-phase

| Decision | Why | Stream |
|---|---|---|
| Retrofit-in-place, not retire/redistribute | The 13 don't map 1:1 to the v2 catalog; interim cross-cutting coverage keeps commands/skills working until successors land | spec |
| `*-reviewer` agents are `tier: write` even when verdict-only (no Edit tools) | Canonical F.13 — "verdicts are structured writes"; draws a non-blocking arch-doc-reviewer note that F.13 overrides | 2 |
| Reviewer learned 7 canonical prefix→directory exceptions | `doc→document`, `db→database`, `py→python`, etc.; prefix≠dirname is correct for these. Pre-existingly latent for the `db` cluster | 3 |
| Canonical verdict schema scoped to the retrofit family | Gate-feeding verifiers keep their richer shape; see TR-0005 above | exit |

## Carry-forward to Phase 6+

### Deferred (per spec, not regressions)

- **Building the Phase 6–10 successor agents** — each `py-*`/`fe-*`/`testing-*`/`doc-*` population lands in its own phase and retires the interim agent it replaces, updating the registry.
- **`meta-conflict-resolver` / `meta-sycophancy-detector`** (#123/#124) — new meta-agents, later work.

### Tier-3 still open

- **TR-0003** — memory-tier mismatch on read/reason agents. Untouched by Phase 5.
- **TR-0004 step 5** — principle-doc audit pass.
- **TR-0002** — uv-env agents.

### Lessons accreted to auto-memory

- The arch-doc-reviewer now encodes the canonical prefix→directory map; future divergent dirs extend that one bullet rather than adding a parallel check.
- `git rm` already stages a deletion — re-listing the path in a later `git add` aborts the whole `add`; stage new files separately.

## Dogfooding summary

Every commit from here is subject to Phase 1–4 enforcement plus Phase 5's structural checks: the `agents/` flat root must stay empty, every agent must keep schema-valid frontmatter with a consistent tier, `build_graph_registry` must discover the full population, and every retrofit body must keep its four required sections. The 37-assertion smoke still runs under a minute.

Phase 5's value proposition — *the framework's own agent population is now disciplined, discoverable, and tier-constrained, with one committed verdict contract* — is realised. Phase 6 begins replacing the interim coverage with language-specific reviewers; the `closed-loop-quality-scorer` now has a full agent population to score from day one.
