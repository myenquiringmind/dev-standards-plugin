# Develop Phase

**"Write the code. Tests first. Validate before commit."**

The develop phase covers scaffolding, TDD implementation, bug fixes, debugging, pattern application, and refactoring. It is the main implementation phase and the heaviest consumer of stack-specific agents.

## Sub-phases

### Scaffold (`/scaffold <module>`)

1. `meta-folder-structure-advisor` validates target directory
2. `meta-filename-advisor` validates filenames against profile conventions
3. Generator creates stub files (method bodies `...`) + comprehensive test skeleton
4. Tests must be RED (all FAIL, not ERROR)

### TDD (`/tdd <objective>`)

Eight-phase cycle ported from the Modelling project:

1. **DETECT SCAFFOLD** — check if tests exist already
2. **RUN TESTS** — classify: ALL PASS (→ refactor), ALL FAIL (→ green), MIXED (→ green), ERROR (→ fix)
3. **DESIGN TESTS** — if no scaffold: generate test categories (unit, property, deterministic)
4. **RED** — write tests first; verify every test FAILs (not ERRORs); max 3 attempts
5. **GREEN** — minimal implementation; tests are the spec, **do not modify tests**
6. **REFACTOR** — simplification pass; `py-code-simplifier` or `fe-code-simplifier` advises; `py-doc-checker` or `fe-doc-checker` auto-fixes docs
7. **VALIDATE** — invoke `/validate` (see `lifecycle/validate.md`)
8. **SUMMARY** — structured report

After each edit during GREEN/REFACTOR:
- `post_edit_lint.py` runs language-aware lint
- `post_auto_format.py` applies formatter
- `post_track_changed_files.py` updates orchestrator state

### Fix (`/fix <bug>`)

Bug investigation with root cause analysis. Produces: fix + regression test.

### Debug (`/debug <symptom>`)

4-phase systematic debugging: Observe → Hypothesise → Test → Fix. `operate-incident-responder` (opus max) drives the loop.

### Pattern (`/pattern [name]`)

Identifies applicable design pattern from the 54-pattern catalog; scaffolds a language-appropriate implementation. `/pattern-scan` runs all 8 anti-pattern detectors as background agents.

### Refactor (`/refactor`)

Pipeline: `refactor-detector` (read) → `refactor-planner` (reason) → `refactor-applier` (write, worktree). Changes applied in isolation; validated before merge.

## Stack agents active during develop

| Stack | Agents | Trigger |
|---|---|---|
| Python | `py-solid-dry-reviewer`, `py-security-reviewer`, `py-doc-checker`, `py-code-simplifier`, `py-tdd-process-reviewer`, `py-arch-doc-reviewer`, `py-migration-reviewer`, `py-api-reviewer`, `py-logging-reviewer` | `.py` files in diff |
| Frontend | `fe-component-reviewer`, `fe-security-reviewer`, `fe-doc-checker`, `fe-code-simplifier`, `fe-accessibility-reviewer`, `fe-state-reviewer`, `fe-performance-reviewer` | `.js`/`.tsx`/`.ts` files in diff |
| Interface | `api-contract-reviewer`, `api-type-boundary-reviewer`, `api-versioning-reviewer` | API route files in diff |
| Database | `db-schema-reviewer`, `db-migration-safety-reviewer`, `db-query-optimizer-advisor` | Migration files in diff |

## Exit

Code passes all validation, tests are GREEN (were RED before GREEN), stamps written. Ready to commit.

## Interactions

- **Consumes:** design phase outputs (architecture docs, ADRs, API contracts, schema designs)
- **Triggers:** validate phase on every `/validate` call
- **Background:** anti-pattern detectors, `security-sbom-generator`, `codebase-pattern-sweep` run asynchronously
- **Gated by:** `meta-session-planner` (sizes TDD work), stamp gate (blocks commits without stamps)
