# Primitive Selection Framework (PSF)

The single decision reference: **when a new constraint or capability enters the framework, where does it live?**

## The decision order

Pick the **leftmost** primitive that can express the requirement:

```
Rule → Hook → Agent → Skill → Command → MCP tool
```

If in doubt, prefer the **lowest-privilege** primitive that can enforce the requirement.

## The six primitives

### Rule

**When to use.** Immutable behavioural guidance the model should know when editing specific paths. Cheap to load (<1KB), path- and phase-scoped via directory placement. Rules are *read* by the model; rules never execute.

**Lifetime.** Loaded lazily when Claude reads matching files.

**Fail mode.** Fails open (advisory guidance).

**Example.** `".claude/rules/hook-development.md"` describes conventions for Python hooks. Loaded when Claude reads a file under `hooks/`. Claude is expected to honour the guidance; nothing mechanically enforces it.

### Hook

**When to use.** Deterministic code on a Claude Code lifecycle event. Must execute reliably regardless of model attention. Blocks work or emits telemetry. Runs in <30s. A hook that needs judgment should invoke an agent (via `hook type: agent`).

**Lifetime.** Per-event.

**Fail mode.** Fails closed (exit 2 blocks the tool call).

**Example.** `hooks/pre_commit_cli_gate.py` reads the validation stamp on every `git commit` attempt. If the stamp is missing, stale, or branch-mismatched, it exits 2 and the commit is blocked. No judgment involved — pure mechanical enforcement.

### Agent

**When to use.** Judgment that exceeds regex/AST inspection. Produces a typed verdict (`AgentVerdict`). Benefits from isolated context and narrow tool allowlists. Agents are the **judgment layer**.

**Lifetime.** Per-invocation; may carry persistent memory across sessions.

**Fail mode.** Returns `{ok: bool, reason: str, confidence: float}`.

**Example.** `py-solid-dry-reviewer` reads modified Python files and produces a verdict on SOLID/DRY compliance. A regex cannot decide whether a class violates the Single Responsibility Principle — that needs judgment.

### Skill

**When to use.** Auto-triggered capability bundle that spans multiple turns. Applies across many commands. Should activate without the user invoking it by name, based on `paths:` globs matching the files being edited.

**Lifetime.** Description loaded always (~100 tokens); full content loaded on invocation (~5K tokens for SKILL.md first 5K). Shared 25K budget across all invoked skills post-compaction.

**Fail mode.** Fails open (skill content is advisory).

**Example.** `python-standards-skill` auto-invokes whenever Claude works in a file matching `**/*.py`. It injects Python conventions (naming, docstrings, typing, logging) into the session. The skill is authored once, used everywhere.

### Command

**When to use.** User-invoked multi-agent workflow with a single nameable responsibility. Commands compose agents; agents never call commands. Commands are the framework's **public API**.

**Lifetime.** Per-invocation.

**Fail mode.** Explicit exit code + structured output.

**Example.** `/validate` composes language detection + CLI checks + subagent reviewers + stamp writer into one user-facing workflow. The user types `/validate`; the command orchestrates the pipeline.

### MCP tool

**When to use.** Reusable capability across Claude sessions, other MCP clients, or CI. Durable state. Network or auth complexity a hook shouldn't own.

**Lifetime.** Framework lifetime (long-running or stdio subprocess).

**Fail mode.** Protocol-defined (MCP error responses).

**Example.** `graph-query` MCP server exposes tools like `find_validators_for(file_path)` and `topological_order()` against the graph registry. Queries need to persist across sessions and be callable from CI tools — that's MCP, not a hook.

## Why leftmost-first

The leftmost primitives (Rule, Hook) are cheap, deterministic, and fail-safe. The rightmost (Command, MCP) are expensive, sophisticated, and require careful design. Reaching for an agent when a rule would suffice is over-engineering; reaching for a hook when a rule would suffice ties the framework to imperative enforcement when declarative guidance would work.

**Principle:** a regex check belongs in a hook, not an agent. A cross-session query belongs in MCP, not a hook. PSF is enforced at `/new-agent`, `/new-hook`, `/new-rule` by `meta-primitive-selection-reviewer`.

## Anti-patterns

- Using an agent for a check a regex could do → waste of tokens
- Using a command for something the user doesn't invoke → blurs the public API surface
- Using a rule for something that must mechanically enforce → false sense of safety
- Using MCP for something that only one session needs → unnecessary complexity

## Enforcement

- Schema: `schemas/agent-frontmatter.schema.json` enforces tier consistency
- Meta-agent: `meta-primitive-selection-reviewer` reviews new additions against PSF
- Review: this document is load-bearing and referenced from `CLAUDE.md` at the repo root
