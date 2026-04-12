# Plugin vs Project Duality

The framework exists in two contexts simultaneously. Failing to distinguish them was the single biggest mistake the original plan made — it called for "22 rules shipped by the plugin" when Claude Code plugins **cannot ship rules at all**. The duality must be explicit.

## The two contexts

### Context 1: the plugin's own repo

`C:\Users\jmarks01\Projects\dev-standards-plugin\` — this repo. Its purpose is to build and maintain the plugin. It has:

- **`.claude/CLAUDE.md`** and **`CLAUDE.md`** — for agents working *on the plugin itself*
- **`.claude/rules/*.md`** — dogfooded rules that govern the plugin's own development (agent frontmatter conventions, hook development standards, anti-rationalization constraints, agent coordination, session lifecycle, telemetry conventions)
- **`docs/architecture/`** — the architectural principles used to reason about the plugin
- **Hooks, agents, commands, skills** — both as source code and as dogfooded tools that run during the plugin's own development

Everything in this context is for the people (and agents) **building the plugin**. It is not shipped to users.

### Context 2: a user project with the plugin installed

A user clones `dev-standards-plugin` from GitHub, runs `/plugin install dev-standards-plugin`, and opens their own project in Claude Code. What arrives in their session:

- **Hooks** (from `hooks/*.py`) run on every tool call
- **Agents** (from `agents/**/*.md`) are available for invocation
- **Commands** (from `commands/*.md`) appear in the `/` menu
- **Skills** (from `skills/*/SKILL.md`) auto-invoke based on `paths:` globs
- **Schemas** (from `schemas/*.json`) validate internal plugin state
- **Config** (from `config/*.json`) including language profiles

**The user's own `.claude/CLAUDE.md` and `.claude/rules/` are untouched.** Claude Code plugins cannot modify users' project-level instruction files. Plugins contribute skills; user projects contribute rules.

This is confirmed by research of the claude-plugins-official repo: no official plugin ships CLAUDE.md files; they ship skills exclusively.

## Consequences

### 1. Rules live in the plugin repo; skills ship to users

A rule like "Python functions must have Google-style docstrings" is **not a rule shipped by the plugin**. It's a **skill** (`skills/python-standards/SKILL.md`) that auto-invokes on `**/*.py` and injects the convention into the user's session.

Conversely, a rule like "all bootstrap hooks must use `_os_safe.py` for file writes" is a rule in the plugin repo's own `.claude/rules/hook-development.md`. It governs the plugin's own code, not the user's code.

### 2. The "22 rules" from the original plan split into three categories

- **Rules in the plugin's own repo** (11): session-lifecycle, context-preservation, hooks, testing-plugin, anti-rationalization, os-safety-internal, agent-coordination, telemetry, agentic-failure-modes, security-internal, agent-frontmatter
- **Skills shipped to users** (14+): python-standards, javascript-standards, api-contracts, database, security-user, design-patterns, testing-user, naming-database, naming-api, naming-env-vars, naming-git, naming-observability, naming-cicd, naming-containers, os-safety-user
- **Optional user-rule templates** (15): `templates/user-rules/*.md` files the plugin's `/setup` command can optionally copy into a user's `.claude/rules/` with the user's consent, giving mechanical enforcement (rules fire at session start) rather than contextual hints (skills fire on file access)

### 3. Shipping path for each primitive

| Primitive | Plugin repo location | How it reaches users |
|---|---|---|
| Hook | `hooks/*.py` | Registered via `hooks/hooks.json` in plugin manifest; runs in user sessions automatically |
| Agent | `agents/**/*.md` | Registered via plugin manifest; invocable in user sessions |
| Command | `commands/*.md` | Registered via plugin manifest; appears in user's `/` menu |
| Skill | `skills/*/SKILL.md` | Registered via plugin manifest; auto-invokes on `paths:` match |
| Schema | `schemas/*.json` | Used internally by the plugin; validates plugin state |
| Config | `config/*.json` | Used internally by the plugin; profiles, defaults |
| **Rule** | `.claude/rules/*.md` | **Not shipped** — governs the plugin's own development only |
| **User rule template** | `templates/user-rules/*.md` | Copied into user's `.claude/rules/` by `/setup` on opt-in |

### 4. CLAUDE.md files in the plugin repo are for us, not for users

Our `CLAUDE.md`, `.claude/CLAUDE.md`, `hooks/CLAUDE.md`, `agents/CLAUDE.md`, etc., are for agents working on the plugin itself. When a user installs the plugin, these files are not loaded into the user's session. The user's own CLAUDE.md hierarchy (or absence of it) is what governs their session.

### 5. The dogfooding loop

The plugin's own development uses:

- The plugin's own hooks (`hooks/*.py`) to gate commits
- The plugin's own agents (`agents/**/*.md`) to validate work
- The plugin's own schemas (`schemas/*.json`) to validate its own components
- The plugin's own rules (`.claude/rules/*.md`) to guide agents
- The plugin's own skills (`skills/*/SKILL.md`) to inject conventions

And when users install the plugin, they get the same agents/hooks/commands/skills but apply them to **their own** code. The rules and CLAUDE.md files that govern the plugin's own development stay in the plugin's repo.

## Why this matters

Conflating the two contexts produces schemas that expect plugin-level rules (impossible), agent designs that assume the plugin's CLAUDE.md loads in user sessions (it doesn't), and documentation strategies that can't be shipped (they're local to the repo, not distributable).

Getting the duality right simplifies everything: the plugin ships a known set of primitives via the manifest, the plugin's own development uses an additional set of primitives local to the repo, and neither context contaminates the other.
