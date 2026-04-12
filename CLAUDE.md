# dev-standards-plugin

This repo is the `dev-standards-plugin` framework — an agentic development lifecycle framework delivered as a Claude Code plugin. It is also a working repo that **dogfoods its own rules**: every commit here is gated by the framework's own hooks, validated by its own agents, and stamped by its own gate model.

## Orientation

Editing something? Start here:

- **A hook?** → `hooks/CLAUDE.md`
- **An agent?** → `agents/CLAUDE.md`
- **A schema?** → `schemas/CLAUDE.md`
- **A command?** → `commands/CLAUDE.md`
- **A skill?** → `skills/CLAUDE.md`
- **A doc?** → `docs/CLAUDE.md`

## What you need to know in every session

Four load-bearing principles. Each is a small, scoped file. Read them once; they survive compaction.

- `docs/architecture/principles/psf.md` — Primitive Selection Framework (where new logic lives)
- `docs/architecture/principles/stamps.md` — 3+ stamp validation gate model
- `docs/architecture/principles/bootstrap-first.md` — why we dogfood from the bootstrap
- `docs/architecture/principles/context-awareness.md` — never compact, guideline budgets, session planner

## Current state

- **Target version:** v2.0.0 (in development)
- **Current phase:** see `docs/phases/README.md`
- **Canonical plan:** `docs/decision-records/v2-architecture-planning-session.md` (archived; not loaded at runtime)
- **ADRs:** `docs/decision-records/`
- **Decomposed architecture:** `docs/architecture/principles/`

## What NOT to do

- **Never commit to `master` directly.** `hooks/branch_protection.py` blocks this; use a feature branch under `feat/<category>-<slug>`.
- **Never skip `/validate`.** The stamp-enforced commit gate blocks commits without valid stamps. `[WIP]` and `.git/MERGE_HEAD` are the only bypasses.
- **Never load the canonical plan at runtime.** It's a decision record, not runtime context. Reference `docs/architecture/principles/*.md` via `@include` instead.
- **Never exceed 200 lines in a markdown file** without deliberate exemption. The size limit hook enforces this from Phase 1 exit.
- **Never enter compaction.** Force `/handoff` at the dynamic cut (~62% of the active model's window) before CC auto-compacts.

## The plugin is public

This repo is or will be publicly visible. Do not commit secrets. `hooks/pre_write_secret_scan.py` blocks common patterns but isn't foolproof — think before you paste. See `docs/architecture/principles/security.md`.

## Reference

- Canonical plan (archive): `docs/decision-records/v2-architecture-planning-session.md`
- Component catalog: `docs/architecture/components/` (populated as components are built)
- Lifecycle phases: `docs/architecture/lifecycle/`
- Implementation phases: `docs/phases/`
- How-to: `docs/guides/`
