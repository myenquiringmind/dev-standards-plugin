# Components

This folder contains **the reference catalog of what exists in the framework**: every agent, command, hook, skill, rule, schema, and MCP server. It is populated as components materialize.

## The seven catalogs

| Catalog | Populated when |
|---|---|
| `agents.md` | Per-agent documentation rolls up from each agent's frontmatter and prose as agents are built. Full ~156-agent catalog materializes across Phases 3-10. |
| `commands.md` | Per-command documentation from frontmatter + phase mapping. Populated across Phases 1-10. |
| `hooks.md` | Per-hook documentation from module docstrings. Phase 1 bootstrap populates the initial 17 core hooks. |
| `skills.md` | Per-skill documentation from SKILL.md frontmatter. Populated across Phases 1-10 as skills are shipped. |
| `rules.md` | Rules for the plugin's own dogfooded development (not shipped to users). Populated in Phase 2 as the rules are written. |
| `schemas.md` | JSON Schema catalog. Phase 0 populates the 4 foundational schemas. |
| `mcp-servers.md` | Bundled MCP server catalog. Populated in Phase 10. |

## Phase 0 status

**None populated yet.** Phase 0 is architecture lockdown — the catalogs are specified in the canonical plan (`docs/decision-records/v2-architecture-planning-session.md`) but not yet materialized as per-component documentation.

## Why this is generated, not hand-written

Component catalogs are **derived artifacts**. The source of truth is:

- For agents: the `agents/**/*.md` files themselves with their frontmatter
- For hooks: the `hooks/*.py` module docstrings and event/matcher declarations
- For commands: the `commands/*.md` files with frontmatter
- For skills: `skills/*/SKILL.md` with frontmatter
- For rules: `.claude/rules/*.md` in this repo
- For schemas: `schemas/*.json` files
- For MCP servers: `mcp-servers/*/` directories

A `doc-component-catalog-writer` agent (built in Phase 9) regenerates these catalogs from the source of truth on every relevant change. Hand-writing them would drift immediately.

## Until then

Components are documented in:

- The canonical plan archive — `docs/decision-records/v2-architecture-planning-session.md` (Appendices A, B, C)
- The agent manifest files themselves under `agents/**/*.md` (once built)
- Phase specs under `docs/phases/phase-N-*.md`

When Phase 9 runs, `doc-component-catalog-writer` generates the catalog files from these sources. Do not edit files in this folder manually before that happens — they will be regenerated.
