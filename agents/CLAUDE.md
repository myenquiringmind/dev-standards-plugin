# agents/ — Agent markdown files

You are working in the agents directory. Agents are subprocess LLM invocations with their own tool allowlist, context, and contract. They return typed `AgentVerdict` structures. They are the judgment layer of the framework.

## Structure

Agents are organized by category:

```
agents/
├── design/            # Design phase agents
├── discover/          # Discover phase agents
├── research/          # Research phase agents
├── document/          # Documentation agents
├── patterns/          # Design pattern advisors
│   ├── creational/
│   ├── structural/
│   ├── behavioural/
│   ├── architectural/
│   ├── concurrency/
│   ├── distributed/
│   ├── integration/
│   ├── resilience/
│   ├── ddd/
│   ├── api/
│   └── testing/
├── antipatterns/      # Anti-pattern detectors (background)
├── python/            # Python stack reviewers
├── frontend/          # Frontend/React reviewers
├── interface/         # API/contract boundary reviewers
├── interop/           # FFI/multi-language boundary reviewers
├── database/          # Database schema and migration reviewers
├── codebase/          # Brownfield scanners (R-tier)
├── security/          # Security-focused agents
├── testing/           # Test strategy agents
├── validation/        # Objective and completion verifiers
├── meta/              # Dogfooding/self-referential agents
├── refactor/          # Refactoring pipeline
├── operate/           # Operate-phase agents
├── maintain/          # Maintain-phase agents
├── deploy/            # Deploy-phase agents
└── closed-loop/       # Closed-loop improvement agents
```

## Required frontmatter

Every agent file declares YAML frontmatter matching `schemas/agent-frontmatter.schema.json`. Required fields: `name`, `description`, `tools`, `model`, `memory`, `maxTurns`. See `@docs/architecture/components/agents.md` once materialized.

## Naming

Pattern: `<scope>-<domain>-<role>.md`

- Scope prefix: `py`, `fe`, `db`, `api`, `pattern`, `antipattern`, `design`, `discover`, `research`, `doc`, `meta`, `validation`, `refactor`, `operate`, `maintain`, `deploy`, `security`, `testing`, `interop`, `bg`, `codebase`, `closed-loop`
- Domain: what it reviews or produces (solid-dry, schema, migration, strategy, ...)
- Role: `-reviewer` (blocking), `-checker` (auto-fixer), `-advisor` (advisory), `-scaffolder` (generator), `-designer` (design phase), `-scanner` (read tier), `-profiler` (read tier), `-analyst` (reason tier), `-planner` (reason tier)

The `schemas/agent-frontmatter.schema.json` name regex enforces this.

## R/R/W tiering

Every agent declares a `tier` in frontmatter: `read`, `reason`, `write`, or `read-reason-write` (sanctioned exception). The schema blocks Edit/Write tools on read and reason tiers.

- **Read tier** — scanners, profilers, extractors. Tools: `Read, Glob, Grep, Bash` (read-only subset). No Edit/Write.
- **Reason tier** — analysts, planners, gap-analyzers. Tools: `Read, Bash`. No Edit/Write. May use `opus max` effort for high-judgment work.
- **Write tier** — scaffolders, reviewers, auto-fixers. Tools include `Edit, Write`. Auto-fixers typically use `isolation: worktree`.
- **Read-reason-write** — sanctioned exceptions only (e.g., `closed-loop-transcript-todo-extractor`). Document why splitting would be over-engineering.

See `@docs/architecture/principles/rrw-tiering.md`.

## Persistent agent memory

Read-only agents (no Edit/Write access) persist learnings via `hooks/write_agent_memory.py --agent <name> --append`, invoked from Bash with content on stdin. This is how advisory agents accumulate project-specific exemptions across sessions. Memory lives in `${CLAUDE_PLUGIN_DATA}/agent-memory/<agent-name>/MEMORY.md`.

## Scaffolding a new agent

Use `meta-agent-scaffolder` via `/new-agent <category>/<name>` once Phase 1 is live. Do not hand-write new agents after that — the scaffolder enforces frontmatter, tier consistency, graph registry update, and naming.

## Read these first

- `@docs/architecture/principles/psf.md` — agents sit at the third rung of the PSF
- `@docs/architecture/principles/rrw-tiering.md` — the tier system and enforcement
- `@docs/architecture/principles/stamps.md` — blocking agents feed the stamp gate
