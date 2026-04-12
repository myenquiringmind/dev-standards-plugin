# Command Catalog

28 commands. Each is a user-invoked workflow with exactly one responsibility, explicit phases, and a defined context-fork strategy. Commands are the framework's public API — the `/` entries a user types. See PSF at `@principles/psf.md` (commands are the fifth rung).

## Full inventory

| Command | Phase | Model | Agents composed | Output |
|---|---|---|---|---|
| `/discover` | Discover | opus | requirements-elicitor, stakeholder-mapper, project-state-classifier, R-tier scanners (brownfield) | `docs/discover/<topic>/` |
| `/research` | Research | opus | prior-art-scanner, spike-planner | `docs/research/<topic>/` |
| `/design` | Design | opus | brainstormer, requirements-analyst, architecture-reviewer, api-contract-designer, schema-designer, threat-modeler, adr-writer, gap-analyst | `docs/design/<topic>/` + ADR |
| `/plan` | Design | opus | requirements-analyst, architecture-reviewer | Implementation plan with tasks |
| `/scaffold` | Develop | opus | folder-structure-advisor, filename-advisor, stub + test skeleton generator | Scaffolded module (RED state) |
| `/tdd` | Develop | opus | stack agents (py-*/fe-*), CLI runners, objective-verifier | Working code, stamps written |
| `/fix` | Develop | sonnet | incident-responder (for debugging), stack reviewers | Bug fix + regression test |
| `/debug` | Develop | opus | 4-phase debug loop (Observe, Hypothesise, Test, Fix) | Root cause + fix |
| `/pattern [name]` | Develop | opus | Relevant `pattern-*-advisor` | Pattern scaffold in target language |
| `/pattern-scan` | Develop | sonnet | All `antipattern-*-detector` (background) | Anti-pattern report |
| `/refactor` | Develop | opus | refactor-detector, refactor-planner, refactor-applier (worktree) | Refactored code in worktree |
| `/typecheck` | Test | sonnet | CLI runners per profile, testing-pyramid-enforcer | Type error report + pyramid status |
| `/validate` | Validate | opus | Full validate gate per profile (see lifecycle/validate.md) | Stamps written |
| `/validate-agents` | Validate | opus | agent-arch-doc-reviewer, command-composition-reviewer, graph-registry-validator | `.agent_validation_stamp` |
| `/security-scan` | Validate | sonnet | sast-runner, secret-scanner, dep-vuln-scanner, license-compliance, sbom-generator | Security report |
| `/review` | Validate | opus | Delegates to domain agents based on file types | Code review |
| `/scan [target]` | Discover | sonnet | R-tier scanner pipeline (facts only, no gap analysis) | `.claude/discover/*.json` |
| `/document [mode]` | Document | sonnet | adr-writer, runbook-writer, sequence-diagrammer, or onboarding-writer | Documentation artifact |
| `/release` | Deploy | opus | release-reviewer, migration-sequence-reviewer, canary-advisor | Tagged release |
| `/incident` | Operate | opus | incident-responder, slo-monitor, runbook-executor | Incident record + runbook update |
| `/maintain` | Maintain | sonnet | dependency-updater, deprecation-scanner, flake-detector | Dependency PR, deprecation report |
| `/handoff` | Lifecycle | haiku | Session state writer | MEMORY.md + session-state.md |
| `/status` | Lifecycle | haiku | Session state reader | Current state report |
| `/logs` | Lifecycle | haiku | Session activity viewer | Log dump |
| `/setup` | Lifecycle | sonnet | detect-language, setup-wizard, profile initializer | `.language_profile.json` + `.dsp-config.json` |
| `/escalate` | Meta | opus | conflict-resolver or human handoff | Resolved verdict or human briefing |
| `/feedback` | Meta | haiku | Incident log writer (explicit user signal) | Feedback record |
| `/new-agent` | Meta | opus | agent-scaffolder, agent-arch-doc-reviewer, graph-registry-validator, primitive-selection-reviewer | New agent file + registry update |
| `/new-command` | Meta | opus | command-scaffolder, command-composition-reviewer | New command file |
| `/new-hook` | Meta | opus | hook-scaffolder + hook test suite | New Python hook + tests |
| `/new-rule` | Meta | sonnet | Rule review + placement | New rule file with frontmatter |

## Composition rules

1. **Commands compose agents; agents never call commands.** One-way composition.
2. **Each command has exactly one responsibility.** `meta-command-composition-reviewer` enforces this.
3. **Every long-running command invokes `meta-session-planner` first.** Sizes the work against the session budget.
4. **Commands emit phase markers.** First step writes `.current_phase`; last step clears it.

## How commands interact with other components

```
User types /validate
      ↓
Command ──invokes──> meta-session-planner (sizes work)
         ──detects──> language profile (which gates to run)
         ──composes──> R-tier CLI runners (ruff, mypy, pytest)
         ──composes──> W-tier subagent reviewers (py-solid-dry, py-security, ...)
         ──writes──> validation stamp (via hooks/stamp_validation.py)
         ──reads──> _hook_shared.py (canonical step tuples)
```

Commands trigger tool calls; hooks fire on those tool calls. Commands and hooks interact indirectly through the tool-call lifecycle.

## Bootstrap commands

Phase 1 ships 3: `/validate`, `/handoff`, `/setup`. The remaining 25 land in Phases 6-10.
