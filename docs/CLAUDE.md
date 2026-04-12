# docs/ — Architecture and reference documentation

You are working in the docs directory. Every file here is an architectural artifact subject to strict size discipline.

## Size limit

**Every markdown file in `docs/` must be ≤200 lines.**

Enforced by `hooks/post_edit_doc_size.py` from Phase 1 exit onwards. Violations block the commit. The only exemption is `docs/decision-records/v2-architecture-planning-session.md` (the archived canonical plan is a historical artifact, not runtime context).

**Why:** every agent that needs to understand an architectural concept loads the relevant file lazily via `@include` from a CLAUDE.md. If individual files are large, agents load enormous context. Keeping each file small and scoped keeps context loads surgical and keeps decomposition honest.

## Taxonomy (Diataxis)

The `docs/` tree follows the Diataxis documentation taxonomy (see diataxis.fr). Four quadrants split on user intent × content type:

| | Practical | Theoretical |
|---|---|---|
| **Study** | `tutorials/` (learning) — deferred to Phase 10+ | `architecture/principles/` (explanation) |
| **Work** | `guides/` (how-to) | `architecture/components/` (reference) |

Plus two framework-specific folders:

- `phases/` — implementation roadmap (reference for the 11-phase plan)
- `decision-records/` — Architecture Decision Records (explanation of past decisions)

## What goes where

- **Explaining a concept** → `docs/architecture/principles/<concept>.md`
- **Cataloging a component type** → `docs/architecture/components/<type>.md`
- **Describing a lifecycle phase** → `docs/architecture/lifecycle/<phase>.md`
- **Specifying an implementation phase** → `docs/phases/phase-<N>-<name>.md`
- **Recording a decision** → `docs/decision-records/adr-<NNN>-<slug>.md`
- **How-to for a specific task** → `docs/guides/<task>.md`
- **Tutorial for newcomers** → `docs/tutorials/` (deferred)

## Authoring conventions

1. **First line is a top-level heading** matching the file's topic.
2. **Second paragraph states the purpose** in plain English. "This document explains X."
3. **≤200 lines** including frontmatter, code fences, tables. No exceptions.
4. **Reference other docs via `@path`** syntax — Claude Code's `@include` mechanism loads the referenced file when the including file is read.
5. **Use the canonical terminology** from the ADRs. Don't invent synonyms.
6. **When in doubt, link, don't duplicate.** If two files would say the same thing, one of them should link to the other.

## Archived canonical plan

`docs/decision-records/v2-architecture-planning-session.md` is a copy of the full planning session that produced this architecture. It is NOT loaded at runtime. It is a historical decision record kept in git so the work cannot be lost. When reading it for context, be deliberate — it's ~3300 lines.

## Read these first

- `@docs/architecture/principles/documentation-as-code.md` — the discipline and the failure case
- `@docs/architecture/principles/dogfooding.md` — why the docs structure itself is a dogfooding artifact
- `docs/README.md` — the top-level index of what lives where
