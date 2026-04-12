# Design Phase

**"What's the architecture? What are the trade-offs? Which approach do we pick?"**

The design phase produces architecture decisions, API contracts, schema designs, and threat models — all before any code is written. It consumes the discover phase's factual outputs (scanner reports, gap analysis, requirements).

## Trigger

`/design <objective>` or `/plan <objective>`.

## Flow

### Step 1: Brainstorm alternatives

`design-brainstormer-advisor` (reason, opus max) generates 2-3 alternative approaches with explicit trade-offs. The user selects one.

### Step 2: Formalise requirements

`design-requirements-analyst` (reason, opus) extracts functional and non-functional requirements into a structured document.

### Step 3: Architecture review (blocking)

`design-architecture-reviewer` (write/blocking, opus max) validates the selected approach against SOLID, Clean Architecture, and layer boundary rules. **Blocks if layering is violated.** This is the first blocking gate in the design phase.

### Step 4: Interface design

`design-api-contract-designer` (reason, opus) produces OpenAPI/tRPC contracts for interface boundaries.

`design-schema-designer` (reason, opus) produces database schema with normalisation, indexing, and migration planning.

### Step 5: Threat model

`security-threat-modeler` (reason, opus max) runs STRIDE analysis against the proposed design. Identifies attack surfaces, trust boundaries, and mitigations.

### Step 6: Gap analysis integration

`design-gap-analyst` (reason, opus max) — if the discover phase produced scanner reports, the gap analyst cross-references the proposed design against existing state. "Here's what exists, here's what's needed, here's the delta."

### Step 7: Record the decision

`doc-adr-writer` (write, sonnet) captures the decision as an Architecture Decision Record in `docs/decision-records/adr-NNN-<slug>.md`.

## Outputs

Written to `docs/design/<topic>/`:

- `architecture.md` — the selected architecture
- `adr-NNN-<slug>.md` — the decision record
- `api-contract.yaml` — OpenAPI spec (if applicable)
- `schema-design.md` — database schema (if applicable)
- `threat-model.md` — STRIDE analysis (if applicable)

## Exit

Architecture doc + ADR + API contracts + threat model committed. All blocking reviewers passed. Ready for `/scaffold` or `/tdd`.

## Interactions

- **Consumes:** discover phase outputs (scanner reports, gap analysis, requirements)
- **Feeds into:** develop phase (scaffold reads architecture docs; TDD uses them as spec)
- **Gated by:** `meta-session-planner` (sizes design work), `design-architecture-reviewer` (blocks bad layering)
- **Records to:** `docs/decision-records/` (ADRs are permanent history)
