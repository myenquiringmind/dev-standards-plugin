# schemas/ — JSON Schema definitions

You are working in the schemas directory. Schemas are JSON Schema draft-2020-12 files that validate the framework's data contracts.

## What's here

### Foundational schemas (Phase 0)

- `graph-registry.schema.json` — validates `config/graph-registry.json` (derived artifact; never hand-edited)
- `stamp.schema.json` — validates the five validation stamp files
- `agent-frontmatter.schema.json` — validates agent markdown frontmatter, including the `tier` field for R/R/W enforcement
- `profile.schema.json` — validates language profile files

### Report schemas

`schemas/reports/` holds JSON Schemas for agent/hook report outputs. Two schemas shipped in Phase 1:

- `project-state.schema.json` — produced by `discover-project-state-classifier` during `/setup`. Classifies the working directory as greenfield / growing-green / brownfield.
- `transcript-todo-extraction.schema.json` — produced by `closed-loop-transcript-todo-extractor` after every `SubagentStop`. Captures deferred items from the subagent's narrative.

Phase 3+ adds scanner report outputs from the brownfield scanner pipeline (codebase / database / api scanners).

### Contract schemas (future)

`schemas/contracts/` will hold JSON Schemas for interface contracts (`AgentVerdict`, `HookInput`, etc.). Deferred until Phase 2.

## Rules

1. **Draft-2020-12 only.** All schemas declare `"$schema": "https://json-schema.org/draft/2020-12/schema"`.
2. **Every schema has `$id`**: a stable URL identifier under `https://dev-standards-plugin/schemas/...`.
3. **Every schema self-validates** against the meta-schema. The Phase 0 exit gate verifies this.
4. **`additionalProperties: false` unless there's a documented reason** to allow arbitrary extension.
5. **Use `$defs` for reusable sub-schemas.** Don't inline complex types.
6. **Prefer `oneOf` / `anyOf` precisely.** `oneOf` requires exactly one match; `anyOf` allows multiple. A generic fallback shape requires `anyOf`, not `oneOf` (see the graph-registry schema for the lesson learned).
7. **Every schema has positive AND negative test examples** in the Phase 0 verifier or `tests/schemas/`.

## Naming

- `<name>.schema.json` at the top level — foundational schemas
- `reports/<report-name>.schema.json` — scanner report outputs
- `contracts/<contract-name>.schema.json` — interface contracts

## Writing a new schema

1. Start with `$schema`, `$id`, `title`, `description`
2. Declare `type: "object"` (most framework schemas are objects)
3. List `required` fields explicitly
4. For each property, specify `type` and human-readable `description`
5. Set `additionalProperties: false` unless extension is a design goal
6. Add conditional rules (`if/then/else`, `allOf`) at the end
7. Add positive and negative test examples to the verifier

## Testing

Phase 0 used a throwaway `tmp/verify-phase-0.py` script. From Phase 2 onwards, schema tests live in `tests/schemas/test_<name>.py` and run under pytest via `uv run pytest tests/schemas/`.

A schema PR must include at least one positive example that validates and one negative example that is deliberately rejected.

## Read these first

- `@docs/architecture/components/schemas.md` — full schema catalog (populated as schemas are added)
- The existing schemas themselves — they are short, self-documenting, and the canonical examples
