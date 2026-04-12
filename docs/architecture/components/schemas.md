# Schema Catalog

17 JSON Schema files (draft-2020-12) that validate the framework's data contracts. Schemas are the type system — they catch structural errors at declaration time, before any agent runs.

## Foundational schemas (Phase 0, committed)

| Schema | Validates | Key constraints |
|---|---|---|
| `schemas/graph-registry.schema.json` | `config/graph-registry.json` (derived artifact) | 11 node types, 12 edge types, per-type metadata shapes via `anyOf`, node id uniqueness |
| `schemas/stamp.schema.json` | `.validation_stamp`, `.frontend_validation_stamp`, etc. | Fixed 15-min TTL (`ttl_seconds: 900`), branch-specific, 5 gate categories |
| `schemas/agent-frontmatter.schema.json` | Agent markdown YAML frontmatter | Scope-prefix name regex, `tier` field with R/R/W conditional rules (read/reason cannot declare Edit/Write), effort/model consistency, worktree/tools consistency |
| `schemas/profile.schema.json` | `config/profiles/*.json` | Detection markers + extensions, tool specs (formatter/linter/typeChecker/testRunner), naming conventions, validation step tuples |

## Report schemas (Phase 1-3)

| Schema | Validates | Producer |
|---|---|---|
| `schemas/reports/project-state.schema.json` | `discover-project-state-classifier` output | Phase 1 |
| `schemas/reports/transcript-todo-extraction.schema.json` | `closed-loop-transcript-todo-extractor` output | Phase 1 |
| `schemas/reports/codebase-inventory.schema.json` | `codebase-inventory-scanner` output | Phase 3 |
| `schemas/reports/codebase-dependency-graph.schema.json` | `codebase-dependency-grapher` output | Phase 3 |
| `schemas/reports/codebase-convention-profile.schema.json` | `codebase-convention-profiler` output | Phase 3 |
| `schemas/reports/db-schema-report.schema.json` | `db-schema-scanner` output | Phase 3 |
| `schemas/reports/db-data-profile.schema.json` | `db-data-profiler` output | Phase 3 |
| `schemas/reports/api-contract-report.schema.json` | `api-contract-extractor` output | Phase 3 |
| `schemas/reports/api-usage-profile.schema.json` | `api-usage-profiler` output | Phase 3 |

## Contract schemas (Phase 2+)

| Schema | Validates | Defined by |
|---|---|---|
| `schemas/contracts/agent-verdict.schema.json` | `AgentVerdict` return type | Interface contract §4.4 |
| `schemas/contracts/validation-stamp.schema.json` | Stamp shape (alias of stamp.schema.json) | Interface contract §4.4 |
| `schemas/contracts/incident.schema.json` | Incident log records | Interface contract §4.4 |
| `schemas/contracts/telemetry-record.schema.json` | Telemetry JSONL entries | Interface contract §4.4 |

## How schemas interact with other components

```
Agent scaffolder writes a new agent file
      ↓
meta-agent-arch-doc-reviewer validates frontmatter against agent-frontmatter.schema.json
      ↓
If invalid (e.g., tier=read with Edit in tools) → AgentVerdict {ok: false}
      ↓
Commit blocked by stamp gate (agent validation stamp missing)
```

Schemas are consumed by:
- **Agents** (`meta-agent-arch-doc-reviewer`, `meta-graph-registry-validator`) at validate time
- **Hooks** (`pre_commit_cli_gate.py` reads stamps against stamp.schema.json)
- **Scripts** (`build-graph-registry.py` validates the output against graph-registry.schema.json)
- **Tests** (Phase 0 verifier tested positive/negative examples against all 4 foundational schemas)

## Schema conventions

1. **Draft-2020-12 only.** All schemas declare `"$schema": "https://json-schema.org/draft/2020-12/schema"`.
2. **`additionalProperties: false`** unless extension is a design goal.
3. **Every schema self-validates** against the meta-schema.
4. **Every schema has positive AND negative test examples.**
5. **Use `$defs` for reusable sub-schemas.** Don't inline complex types.

See `schemas/CLAUDE.md` for full authoring conventions.
