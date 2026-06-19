# commands/ — User-invoked workflows

You are working in the commands directory. Commands are the framework's public API: the `/` entries a user types to invoke a workflow.

## What goes here

One markdown file per command. File name is the command name minus the slash: `/validate` lives at `validate.md`, `/tdd` at `tdd.md`, `/new-agent` at `new-agent.md`.

## Required frontmatter

Every command declares:

```yaml
---
context: fork | none        # fork = run in an isolated subagent context (dominant choice)
model: opus | sonnet | haiku # resource allocation (opus for judgment, haiku for summaries)
allowed-tools: <list>       # tools the command can invoke
argument-hint: <string>     # autocomplete hint shown in the CC UI
fast-command: true          # optional — rule-3 planner exemption for fixed-cost commands (see below)
---
```

## Composition rules (non-negotiable)

1. **Commands compose agents. Agents never call commands.** Composition flows one way.
2. **Each command has exactly one responsibility.** `/validate` validates. `/tdd` runs TDD. `/scaffold` scaffolds. No mixed responsibilities. `meta-command-composition-reviewer` enforces this at commit time.
3. **Every long-running command invokes `meta-session-planner` as its first step.** The planner sizes the work against the current session's budget, decomposes if necessary, writes the plan to `session-state.md`. Skipping this is blocked by the composition reviewer. **Sanctioned exception — fast commands:** a fixed-cost command whose work cannot meaningfully exceed the session budget (no fan-out, no full-project walk, no agent-heavy loop) may opt out by declaring `fast-command: true` in frontmatter, with the reason stated in the body. The planner adds no value when the cost is bounded and small. `meta-command-composition-reviewer` honours this marker and does not flag such a command. Abuse it and you defeat the budget guard — reserve it for genuinely fast commands (e.g. `/setup`, `/validate`).
4. **Commands emit phase markers.** The first step writes the current phase to `.current_phase` (read by `context_budget.py`). The last step clears it.

## Lifecycle phases and commands

See `docs/phases/README.md` for the 11-phase roadmap. Each command is associated with one lifecycle phase (discover, research, design, develop, test, validate, deploy, operate, maintain, document, meta).

## Naming

Commands use kebab-case verbs or verb-noun pairs:

- `validate.md`
- `scaffold.md`
- `tdd.md`
- `new-agent.md`
- `validate-agents.md`
- `handoff.md`

## Scaffolding a new command

Use `meta-command-scaffolder` via `/new-command <name>` once Phase 1 is live. Do not hand-write new commands afterwards — the scaffolder enforces frontmatter, composition rules, and graph registry updates.

## Read these first

- `@docs/architecture/principles/psf.md` — commands sit at the fifth rung of the PSF (public API, highest privilege)
- `@docs/architecture/principles/context-awareness.md` — why `meta-session-planner` runs first
- `@docs/architecture/components/commands.md` — full command catalog (populated as commands are built)
