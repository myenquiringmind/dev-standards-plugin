# Phase 0 — Architecture Lockdown

**Duration:** 1 week
**Branch:** `feat/architecture-lockdown`
**Status:** in progress (this file was generated during Phase 0 execution)

Phase 0 locks the architectural foundations before Phase 1 bootstrap work begins. It delivers schemas, principles, ADRs, directory CLAUDE.md files, and the Diataxis documentation skeleton. No code is written; no hooks fire; the commit gate does not yet exist.

## Deliverables

### Schemas (4, draft-2020-12)

- `schemas/graph-registry.schema.json` — validates the derived graph registry (11 node types, 12 edge types, per-type metadata shapes via `anyOf`)
- `schemas/stamp.schema.json` — validates the five validation stamp files (15-min TTL, branch-specific, 5 gate categories)
- `schemas/agent-frontmatter.schema.json` — validates agent markdown frontmatter including the `tier` field with R/R/W conditional rules
- `schemas/profile.schema.json` — validates language profile files (detection markers, tool specs, naming conventions, validation step tuples)

All four schemas self-validate against the draft-2020-12 meta-schema. Positive and negative examples verified via a throwaway script before commit.

### Python development environment (3 files)

- `pyproject.toml` with PEP 735 `[dependency-groups].dev` (jsonschema, pytest, portalocker, ruff, mypy, hypothesis) and strict ruff/mypy/pytest config
- `.python-version` pinning to 3.13
- `uv.lock` reproducing the environment exactly

Separate from `requirements.txt` which declares runtime Python deps the plugin installs into *target* projects via `lib/venv/`.

### Repo orientation (1 file)

- `CLAUDE.md` at repo root — <100 lines, the entry point for any agent working in this repo

### Directory-scoped CLAUDE.md (6 files, one per subdirectory)

- `hooks/CLAUDE.md` — hook development conventions
- `agents/CLAUDE.md` — agent frontmatter, R/R/W tiering, memory discipline
- `schemas/CLAUDE.md` — schema authoring conventions
- `commands/CLAUDE.md` — command composition rules
- `skills/CLAUDE.md` — skill authoring conventions, plugin-vs-project duality
- `docs/CLAUDE.md` — documentation size discipline

### Documentation hierarchy (`docs/` tree)

Following the Diataxis taxonomy:

**Top-level:**
- `docs/README.md` — navigation by user intent

**`architecture/` (explanation + reference):**
- `architecture/README.md`, `architecture/principles/README.md`, `architecture/lifecycle/README.md`, `architecture/components/README.md` (4 indexes)
- `architecture/principles/psf.md`, `memory-tiers.md`, `rrw-tiering.md`, `stamps.md`, `bootstrap-first.md`, `dogfooding.md`, `context-awareness.md`, `plugin-vs-project.md`, `documentation-as-code.md`, `security.md` (10 principles)

**`phases/` (reference — implementation roadmap):**
- `phases/README.md` (index + 11-phase table)
- `phases/phase-0-architecture-lockdown.md` (this file)
- `phases/phase-1-bootstrap.md` (next phase contract)

**`decision-records/` (explanation — why we chose):**
- `decision-records/README.md` (index + ADR conventions)
- 6 ADRs: graph-first architecture, strict default, bootstrap-first sequencing, read-reason-write tiering, documentation-as-code, context-awareness absolute budgets
- `decision-records/v2-architecture-planning-session.md` — archived canonical plan (~3300 lines, exempt from size limit)

**`guides/` (how-to):**
- `guides/README.md` (index)
- `guides/getting-started.md` (for contributors getting oriented)

### Security baseline (1 file)

- `SECURITY.md` at repo root — vulnerability reporting policy, scope, known considerations, responsible disclosure

## Total Phase 0 files

| Category | New files |
|---|---|
| Schemas | 4 |
| Python tooling | 3 |
| Root CLAUDE.md | 1 |
| Directory CLAUDE.md | 6 |
| `docs/README.md` + architecture indexes | 5 |
| Principles | 10 |
| Phases | 3 |
| Decision records (README + 6 ADRs + archived plan) | 8 |
| Guides | 2 |
| `SECURITY.md` | 1 |
| **Total** | **43 new files** |

Across **2 commits** on `feat/architecture-lockdown`:

1. `chore(tooling): add uv venv and pyproject.toml for plugin dev env` (commit 1, already made)
2. `docs(architecture): lock schemas, diataxis taxonomy, principles, ADRs (Phase 0)` (commit 2, the big one)

## Exit gate

Phase 0 is complete when:

1. All 4 JSON Schemas self-validate (checked during Phase 0 execution)
2. Every markdown file in `docs/`, `.claude/`, and at repo root is ≤200 lines (except the exempt archived plan)
3. `feat/architecture-lockdown` PR opens cleanly against master with no conflicts
4. PR body references Appendices D/E/F/G/H of the canonical plan (archived copy at `docs/decision-records/v2-architecture-planning-session.md`)
5. PR merges to master

After merge: Phase 1 begins with the parallel `feat/bootstrap-*` branches in worktrees under `C:\Users\jmarks01\Projects\dsp-worktrees\`.

## Pre-bootstrap status

Phase 0 is **pre-bootstrap**. The commit gate, stamp model, validation hooks, and agent scaffolders do not yet exist. Commits on this branch are explicitly exempt from the gate (which has no way to enforce on commits made before it exists). Once Phase 1 lights up the gate, Phase 0 commits are recorded in the incident log as historical context.

From Phase 1 exit onwards, **every commit is gated**. Phase 0 is the last set of hand-crafted commits; everything after is dogfooded through the framework's own validation.

## References

- Canonical plan archive: `../decision-records/v2-architecture-planning-session.md`
- Phase 1 contract: `phase-1-bootstrap.md`
- ADR on bootstrap-first sequencing: `../decision-records/adr-003-bootstrap-first-sequencing.md`
