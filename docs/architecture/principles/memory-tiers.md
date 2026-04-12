# Four-Tier Memory

The framework separates memory into four tiers based on scope and lifetime. Each tier has a distinct location, a distinct writer, and a distinct readership. **Tiers never cross-write.**

## The four tiers

| Tier | Location | Scope | Lifetime | Written by | Read by |
|---|---|---|---|---|---|
| **Session** | `~/.claude/projects/<slug>/memory/` (Claude Auto Memory) | Current session | Until compact or SessionEnd | Claude harness + `session_end.py` | `session_start.py` |
| **Project** | `<repo>/.claude/memory/` | All sessions in this repo | Repo lifetime, git-tracked | `/handoff`, agents with `memory: project` | `session_start.py`, agents |
| **Agent** | `${CLAUDE_PLUGIN_DATA}/agent-memory/<agent>/MEMORY.md` | Per-agent, cross-project | Framework lifetime | `hooks/write_agent_memory.py` | The agent on next invocation |
| **Framework** | `${CLAUDE_PLUGIN_DATA}/framework-memory/` | Global principles, incidents, telemetry, graph history, quality scores | Permanent, append-only | Incident/telemetry hooks, closed-loop agents | MCP servers, retrospective analyst |

## Critical rule: never cross-write

Claude Auto Memory (session tier) is owned by the CC harness. Framework memory (`${CLAUDE_PLUGIN_DATA}/framework-memory/`) is owned by the plugin. **They never cross-write.**

- `session_start.py` *reads* Auto Memory to seed session context, but never writes to it
- Framework agents never write to `~/.claude/projects/<slug>/memory/`
- Project tier is written by explicit user action (`/handoff`, `/feedback`) or by project-scoped agents; it's git-tracked so the repo is the source of truth
- Agent tier is written via `hooks/write_agent_memory.py`, which validates the agent name to prevent path traversal

## Session tier — Claude Auto Memory

The CC harness writes `MEMORY.md` and topic files to `~/.claude/projects/<slug>/memory/` automatically as Claude works. This is outside the plugin's control. The first 200 lines or 25KB of `MEMORY.md` load at session start; other files load on demand.

**The plugin reads Auto Memory at SessionStart** via `session_start.py` to seed context with prior session state. The plugin never writes to Auto Memory — it has its own tier for framework state.

## Project tier — git-tracked, per-repo

Lives in the repo at `<repo>/.claude/memory/`. Contains:

- `session-state.md` — current session snapshot written by `/handoff` and by `hooks/session_checkpoint.py`
- Any agent-produced artifacts scoped to "this repo specifically" (scanner reports, ADR drafts, etc.)

Survives across sessions because it's committed to git. Loaded at session start by `session_start.py`.

## Agent tier — per-agent, cross-project

Each agent has a dedicated directory at `${CLAUDE_PLUGIN_DATA}/agent-memory/<agent-name>/`. Contains `MEMORY.md` with learnings the agent has accumulated across sessions and projects.

Read-only agents (no Edit/Write in their tool allowlist) persist learnings by invoking `hooks/write_agent_memory.py` from Bash, passing content on stdin. This is the mechanism by which advisory agents build up project-specific exemptions and pattern recognition without needing Edit/Write tools.

Example: `py-code-simplifier` encounters deferred imports used for circular-dependency avoidance. It records the exemption pattern in its memory. Next time it sees the same pattern, it doesn't re-flag the issue.

## Framework tier — permanent, append-only

Lives outside any repo at `${CLAUDE_PLUGIN_DATA}/framework-memory/`. Contains:

- `incidents/<YYYY-MM>/<ulid>.json` — incident log (append-only)
- `telemetry/<agent>.jsonl` — per-agent telemetry
- `quality-scores.json` — rolling quality metrics per agent
- `retrospectives/` — weekly retrospective reports
- `principles/` — principles promoted from agent memory by the knowledge compactor
- `graph-history/` — graph registry snapshots

This tier is **global across all projects** where the plugin is installed. The `incident-log` and `memory-search` MCP servers expose queries over this tier.

**Framework tier is keyed by `(repo_origin_url, branch)`** so incidents and memory from one project don't leak into another. `closed-loop-quality-scorer` tracks metrics per-agent globally; scores improve (or regress) based on aggregated data across all projects.

## Compaction and memory

CLAUDE.md survives compaction fully (re-read from disk). The other tiers are loaded at SessionStart and may or may not survive compaction depending on what the CC harness decides. **Load-bearing content that must survive compaction belongs in CLAUDE.md or in rules referenced by CLAUDE.md via `@include`**, not in project or agent memory tiers.

See `@docs/architecture/principles/documentation-as-code.md` for the implications for docs.

## Why four tiers

- **Session tier** is ephemeral working memory; crash-recovery uses project tier
- **Project tier** is per-repo state that needs to be shareable via git
- **Agent tier** is cross-project agent learning (precision/recall over time)
- **Framework tier** is the closed-loop infrastructure: incidents, telemetry, retrospectives, principles

Collapsing any two would lose a distinction that matters to either the agent producing the data or the consumer reading it.
