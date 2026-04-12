# ADR-002: Strict Default Enforcement

**Status:** Accepted
**Date:** 2026-04-11
**Deciders:** User decision (Q&A during planning session)

## Context

Every enforcement framework faces the adoption-vs-quality trade-off. A strict-by-default framework blocks work frequently, frustrating new adopters. An advisory-by-default framework gets ignored, providing a false sense of safety. The Modelling project (the predecessor whose patterns we're porting) ran strict-by-default and proved it was sustainable — but the Modelling project was a single-developer, single-repo tool.

## Decision

**Strict by default.** The stamp gate blocks on every step it declares blocking. Zero tolerance. The only bypasses are:

1. `[WIP]` in the commit message — emergency handoff escape hatch
2. `.git/MERGE_HEAD` exists — merge-in-progress conflict resolution

No other bypasses. `--no-verify` does not help (the gate is a CC hook, not a git hook). `userConfig.strictnessOverride` exists as an escape hatch for teams that cannot adopt strict immediately, but the default stays strict.

This matches the Modelling project's stance and was explicitly chosen over "balanced default" (which was the recommended option in the Q&A).

## Consequences

- **New adopters will experience friction.** The `/validate` gate blocks commits until all steps pass. This is intentional — the point is to catch problems before they enter the codebase, not after.
- **`[WIP]` bypass must be used judiciously.** It's for emergency context handoff (context budget exceeded, session must end), not for skipping validation. `closed-loop-incident-retrospective-analyst` flags WIP bypass patterns in weekly reviews.
- **`userConfig.strictnessOverride`** lets teams dial down to `balanced` (block on security + objective only, warn on SOLID/DRY) or `advisory` (nothing blocks). But the default is strict.
- **The plugin's own development** uses strict. Every commit to `dev-standards-plugin` passes through the strict gate from Phase 1 exit onwards.

## Alternatives considered

- **Balanced default** (block security + objective; warn SOLID/DRY; advise patterns + style). This was my recommendation. Rejected by the user: they want the Modelling project's proven stance, not a compromise.
- **Advisory default** (nothing blocks; everything is feedback). Rejected: provides no enforcement. The user's experience with advisory-only tools is that they get ignored under deadline pressure.

## References

- Canonical plan §11 (Hard Trade-offs, position 7)
- `@docs/architecture/principles/stamps.md` — the gate model
- `@docs/architecture/principles/dogfooding.md` — why the plugin's own development uses strict
