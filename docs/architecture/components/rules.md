# Rules Catalog

11 rules in the plugin's own `.claude/rules/` directory. These govern the plugin's **own dogfooded development** — they are NOT shipped to users (plugins cannot ship rules; see `@principles/plugin-vs-project.md`).

## What rules are

Rules are markdown files in `.claude/rules/` that Claude loads on demand. They provide behavioural guidance — things Claude should know and follow while working in specific directories. Rules are the **first rung** of the PSF: cheapest to load, path-scoped, advisory (fail-open).

Unlike hooks (which execute code) or agents (which invoke LLM judgment), rules are **passive text** loaded into the model's context. They work by influencing Claude's behaviour, not by mechanically blocking actions.

## The 11 plugin-internal rules

| Rule file | Scoped to | Purpose |
|---|---|---|
| `session-lifecycle.md` | all work | Command ownership boundaries, session start/end protocol, pre-commit gate, WIP/merge bypasses, context budget escalation (warn → hard cut → force handoff) |
| `context-preservation.md` | all work | Memory persistence across sessions, compaction survival, session-state checkpoints |
| `hook-development.md` | `hooks/**` | Hook Python conventions: exit codes, `_os_safe` mandatory, stdin JSON, timeout budgets, shared module imports |
| `agent-frontmatter.md` | `agents/**` | Agent YAML frontmatter: required fields, tier consistency, naming regex, memory discipline |
| `testing-plugin.md` | `hooks/tests/**`, `tests/**` | Test conventions for the plugin's own code: pytest, fixtures, property tests, deterministic seeds |
| `anti-rationalization.md` | all work | Agent failure mode mitigations: no sycophancy, no premature closure, no false confidence, verify before claiming done |
| `os-safety-internal.md` | `hooks/**`, `scripts/**` | Windows-first discipline: `_os_safe.py` for all writes, path normalization, atomic operations, portalocker |
| `agent-coordination.md` | `agents/**`, `commands/**` | Multi-agent coordination: conflict resolution, confidence thresholds, escalation paths, timeout cascades |
| `telemetry.md` | `hooks/**` | Telemetry emission conventions: JSONL format, local-only, field allowlist, rotation policy |
| `security-internal.md` | all work | The plugin's own security posture: no secrets in code, gitignore audit, dependency pinning, license compliance |
| `agentic-failure-modes.md` | `agents/**` | Columbia DAPLab failure modes: sycophancy, premature closure, false confidence, context leakage, tool-call hallucination, over-generalization |

## When rules load

- Rules **without** `paths:` frontmatter load unconditionally at session start (alongside CLAUDE.md)
- Rules **with** `paths:` (or `globs:`) load on demand when Claude reads a file matching the pattern
- Path-scoped rules fire on **READ, not WRITE** (known CC limitation)
- For write-time enforcement, use a **hook** (PSF rung 2), not a rule

## How rules interact with other components

```
Claude reads a file in hooks/
      ↓
CC lazy-loads .claude/rules/hook-development.md (if paths: matches)
      ↓
Claude's next actions are influenced by the rule's content
      ↓
If Claude violates the rule, hooks catch it mechanically:
  - post_edit_lint.py catches code style violations
  - pre_write_secret_scan.py catches security violations
  - post_edit_doc_size.py catches size limit violations
```

Rules advise; hooks enforce. They're complementary, not redundant. A rule tells Claude *why* to do something; a hook blocks it if Claude doesn't.

## Optional user-rule templates

`templates/user-rules/*.md` contains rule templates the `/setup` command can optionally copy into a user's `.claude/rules/` with consent. These are the same conventions as the skills but delivered as rules (which load eagerly) rather than skills (which load on file-path match). Users who want stronger enforcement opt into rules; users who prefer soft guidance use the skills.

15 templates available, matching the 14 user-facing standards skills plus a combined template.
