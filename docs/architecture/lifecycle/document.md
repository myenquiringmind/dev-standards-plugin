# Document Phase (Cross-Cutting)

**"Write the docs. Keep them alive. Generate what can be generated."**

Documentation is not a sequential phase — it's cross-cutting, invocable from any other phase. The document phase produces Architecture Decision Records, operational runbooks, sequence diagrams, and onboarding guides.

## Trigger

`/document [mode]` where mode is one of: `adr`, `runbook`, `sequence`, `onboarding`.

## Modes

### ADR (`/document adr`)

`doc-adr-writer` (write, sonnet) captures a design decision:

- Reads the design session context (what was proposed, what was selected, what was rejected)
- Produces a structured ADR in `docs/decision-records/adr-NNN-<slug>.md`
- Format: Context → Decision → Consequences → Alternatives → References
- Validated by `py-arch-doc-reviewer` or language-appropriate equivalent

Invoked automatically at the end of the design phase. Can also be invoked manually mid-session.

### Runbook (`/document runbook`)

`doc-runbook-writer` (write, sonnet) generates operational documentation:

- Reads code + architecture docs + operational history (incident log, if available)
- Produces a numbered-step runbook in `docs/guides/`
- Includes: prerequisites, steps, verification, rollback, escalation
- Updated by `operate-runbook-executor` when a runbook is followed during an incident

### Sequence diagram (`/document sequence`)

`doc-sequence-diagrammer` (write, sonnet) produces Mermaid diagrams:

- Traces code execution paths (request handlers, event chains, agent pipelines)
- Outputs Mermaid-format sequence diagrams
- Keeps diagrams in sync with source when code changes

### Onboarding (`/document onboarding`)

`doc-onboarding-writer` (write, sonnet) generates contributor onboarding:

- Reads the current architecture, setup steps, conventions
- Produces a getting-started guide tailored to the project's stack and tooling
- Updates when the architecture evolves

## Generated vs hand-written

Some documentation is generated from code, some is hand-written:

| Type | Source of truth | Method |
|---|---|---|
| **Component catalogs** (`components/*.md`) | Agent/hook/command/skill source files | `doc-component-catalog-writer` regenerates from frontmatter |
| **Lifecycle walkthroughs** (`lifecycle/*.md`) | Phase completion + agent composition | `doc-lifecycle-writer` regenerates from actual process |
| **ADRs** (`decision-records/`) | Design sessions | `doc-adr-writer` produces, humans approve |
| **Principles** (`principles/`) | Architecture decisions | Hand-written, reviewed via PR |
| **Guides** (`guides/`) | Implementation experience | `doc-*-writer` agents produce; humans edit |

**Rule:** if a doc can be generated from the source of truth, it should be. Hand-editing a generated file is an anti-pattern — the generator will overwrite the edits on the next run.

## Size discipline

Every document file is ≤200 lines, enforced by `hooks/post_edit_doc_size.py`. Long content is split into multiple files or referenced via `@include` from a parent doc.

## Interactions

- **Invoked from:** any phase (`/document` is always available)
- **Produces:** ADRs, runbooks, diagrams, guides in `docs/`
- **Validated by:** language-appropriate arch-doc reviewers
- **Gated by:** `meta-session-planner` (sizes the documentation work)
- **Feeds:** project memory (docs are git-tracked, searchable, version-controlled)
