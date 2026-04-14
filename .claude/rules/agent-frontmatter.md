# Agent Frontmatter

Every agent file in `agents/` must have YAML frontmatter validated by `schemas/agent-frontmatter.schema.json`. This rule summarises the requirements so you don't have to read the schema every time.

## Required fields

Every agent must declare:

| Field | Type | Constraint |
|---|---|---|
| `name` | string | Kebab-case with scope prefix (e.g. `py-solid-dry-reviewer`, `meta-agent-scaffolder`) |
| `description` | string | 1-500 chars. One-line summary for graph registry and auto-invocation matching |
| `tools` | array | Explicit tool allowlist. At least one tool |
| `model` | string | `opus`, `sonnet`, or `haiku` |
| `memory` | string | `project`, `local`, or `none` |
| `maxTurns` | integer | 1-50 |

## Name prefix convention

The name prefix declares the agent's scope category. It must match one of the PSF prefixes:

`py-`, `fe-`, `db-`, `api-`, `pattern-`, `antipattern-`, `design-`, `discover-`, `research-`, `doc-`, `meta-`, `validation-`, `refactor-`, `operate-`, `maintain-`, `deploy-`, `security-`, `testing-`, `interop-`, `bg-`, `codebase-`, `closed-loop-`

## Tier field

Every agent should declare a `tier` reflecting its Read/Reason/Write specialisation:

| Tier | Can do | Cannot do |
|---|---|---|
| `read` | Read, Bash, Glob, Grep | Edit, Write, NotebookEdit |
| `reason` | Read, Bash, Glob, Grep | Edit, Write, NotebookEdit |
| `write` | All tools | — |
| `read-reason-write` | All tools | — (sanctioned exception for small pipeline agents) |

The schema enforces tool consistency: `read` and `reason` tier agents with Edit/Write in their tools list will fail validation.

## Optional fields

| Field | When to use |
|---|---|
| `effort` | Only with `model: opus`. Values: `low`, `medium`, `high`, `max` |
| `isolation` | Set to `worktree` for auto-fixer agents that edit code |
| `background` | `true` for non-blocking background agents |
| `pack` | Feature pack: `core`, `python`, `frontend`, `database`, `interface`, `tdd`, `design`, `patterns`, `security`, `document`, `operate`, `codebase-scanners` |
| `scope` | `core` (always active) or `profile-scoped` (active when matching language profile present) |
| `skills` | Skills preloaded into the subagent at startup |
| `disallowedTools` | Belt-and-braces blocklist alongside the tools allowlist |
| `overlay` | `true` if this agent overlays a plugin-canonical base agent |
| `color` | Optional UI hint |

## Conditional rules

- `effort: max` requires `model: opus`
- `isolation: worktree` requires Edit or Write in the tools list
- `tier: read` or `tier: reason` forbids Edit, Write, NotebookEdit in tools

## Validation

The schema is at `schemas/agent-frontmatter.schema.json`. From Phase 2 onwards, `meta-agent-arch-doc-reviewer` validates every agent file at `/validate` time.
