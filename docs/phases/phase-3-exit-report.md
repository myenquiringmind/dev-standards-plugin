# Phase 3 — Exit Report

Phase 3 filled the framework's biggest greenfield bias: **R-tier scanners and reason-tier analysts** that read the existing system as fact and feed structured reports into downstream Design / Reviewer agents. Six scanners (4 codebase + 1 db + 1 api) and three reason-tier analysts (architecture-reconstructor, db-migration-planner skeleton, api-breaking-change-analyzer skeleton) shipped, each paired with a pinned report schema. Two new language profiles (typescript first-class, go/rust placeholders) joined python; `bootstrap_smoke` grew from 21 → 28 assertions. The framework can now ingest a brownfield codebase as data without re-deriving its shape on every reviewer invocation.

## What shipped

| Group | Deliverables | PRs |
|---|---|---|
| Phase 3 spec | `docs/phases/phase-3-language-profiles-and-scanners.md` | #79 |
| Stream 1 — Language profiles | `typescript.json` (P0), `go.json` / `rust.json` (P2 placeholders); `fullstack.json` deliberately deferred | #80 |
| Stream 2 — Codebase R-tier scanners | `codebase-inventory-scanner`, `codebase-dependency-grapher`, `codebase-dead-code-detector`, `codebase-convention-profiler` (each + report schema) | #81, #82, #83, #84 |
| Stream 3 — DB scanner | `db-schema-scanner` + `db-schema.schema.json`. PostgreSQL first-class via `psql`; MySQL/SQLite/MongoDB CLIs allowlisted with introspection deferred to Phase 6+ stack agents | #85 |
| Stream 4 — API scanner | `api-contract-extractor` + `api-contract.schema.json`. OpenAPI parsed first-class; tRPC + GraphQL detected with full parsing deferred | #86 |
| Stream 5 — Reason analysts | `codebase-architecture-reconstructor` (full), `db-migration-planner` (skeleton), `api-breaking-change-analyzer` (skeleton). Each + paired report schema | #87, #88, #89 |
| Exit gate | `bootstrap_smoke` 21 → 28 assertions; this report | this PR |

11 PRs landed across the phase (#79–#89, with this PR closing). All Phase 3 deliverables on the spec checklist landed; one item (`fullstack.json`) explicitly deferred with rationale recorded in stream 1's PR.

## Mechanical gate results

`scripts/bootstrap_smoke.py` final run, against master at the merge of this PR:

```
[bootstrap-smoke]  1/28 [PASS] validate-command-present
[bootstrap-smoke]  2/28 [PASS] objective-verifier-present
[bootstrap-smoke]  3/28 [PASS] commit-without-stamp-blocks
[bootstrap-smoke]  4/28 [PASS] valid-stamp-passes
[bootstrap-smoke]  5/28 [PASS] stale-stamp-blocks
[bootstrap-smoke]  6/28 [PASS] wip-bypass
[bootstrap-smoke]  7/28 [PASS] merge-head-bypass
[bootstrap-smoke]  8/28 [PASS] path-traversal-rejected
[bootstrap-smoke]  9/28 [PASS] agent-tier-consistency
[bootstrap-smoke] 10/28 [PASS] transcript-todo-extractor-schema
[bootstrap-smoke] 11/28 [PASS] doc-size-limit
[bootstrap-smoke] 12/28 [PASS] context-budget-hard-cut
[bootstrap-smoke] 13/28 [PASS] secret-scan-and-gitignore
[bootstrap-smoke] 14/28 [PASS] tier-enforcer-blocks-edit
[bootstrap-smoke] 15/28 [PASS] bash-tier-guard-blocks-rm
[bootstrap-smoke] 16/28 [PASS] stop-validation-dirty-tree
[bootstrap-smoke] 17/28 [PASS] stop-failure-incident
[bootstrap-smoke] 18/28 [PASS] telemetry-concurrent
[bootstrap-smoke] 19/28 [PASS] tuple-growth-path
[bootstrap-smoke] 20/28 [PASS] checkpoint-gate-stale
[bootstrap-smoke] 21/28 [PASS] secret-scan-staged
[bootstrap-smoke] 22/28 [PASS] phase-3-language-profiles - 5 profiles
[bootstrap-smoke] 23/28 [PASS] phase-3-codebase-scanners - 4 agents
[bootstrap-smoke] 24/28 [PASS] phase-3-db-api-scanners - 2 agents
[bootstrap-smoke] 25/28 [PASS] phase-3-reason-analysts - 3 analysts
[bootstrap-smoke] 26/28 [PASS] phase-3-codebase-schemas - 4 schemas
[bootstrap-smoke] 27/28 [PASS] phase-3-db-api-schemas - 2 schemas
[bootstrap-smoke] 28/28 [PASS] phase-3-analyst-schemas - 3 schemas
[bootstrap-smoke] 28/28 passed - Phase 1+2+3 exit gate OK
```

Exit gate: **28/28**. Full Python test suite at exit: **830/830**. ruff, ruff-format, mypy-strict, pytest all clean.

**Note on structural checks.** Assertions 22-28 are exercised structurally (file-presence + frontmatter + schema-meta-validation + minimal positive examples). Live invocation of the scanners against real codebases is out of scope for the smoke; that coverage lives in `scripts/live_integration_smoke.py` and Phase 6+ stack reviewer integration tests.

## Scope expansions accepted in-phase

| Change | Why | PR |
|---|---|---|
| `fullstack.json` profile deliberately deferred | Composite profiles need a refactor to `detect_language`'s first-match-wins logic; deferred to a later phase that revisits multi-profile activation rather than papering over the gap | #80 |
| Pre-existing splitter quirk documented in `db-schema-scanner` | Bash-gate splits on `;` inside quoted SQL; surfaced during scanner authoring. Three places call it out (procedure step, "Phase 3 note", explicit pinning test) so the next implementer doesn't re-trip the same wire | #85 |
| TR-0003 logged | `meta-agent-arch-doc-reviewer`'s `memory-tier-mismatch` rule fired on `memory: project` + `tier: read|reason` agents (7 affected on master). Two interpretations possible (read-inject vs write-access); registry entry documents both with a remediation plan rather than a unilateral mass-fix | #88 |
| Pre-existing `bootstrap_smoke` test breakage repaired | `test_real_tree_passes_all_13` and the `"1/13"` literal in `TestMainCLIShape` were stale from Phase 1; surfaced when this PR's full pytest invocation included `scripts/tests/`. Bundled as Tier-1 silent fixes | this PR |
| Pre-existing `Popen` resource leak in #18 | `telemetry-concurrent-safe` left stdout/stderr pipes uncollected; pytest's unraisable-exception collector flagged it. Tier-1 silent fix: redirect to `DEVNULL` since the assertion only inspects returncode + telemetry files | this PR |

None of these widened the **exit gate** — the 28 assertions remain exactly as specified in `phase-3-language-profiles-and-scanners.md`. Each is documented in its PR description and (for the durable lessons) in auto-memory.

## Carry-forward to Phase 4+

### Deferred from Phase 3

- **`fullstack.json` composite profile** — needs `detect_language` refactor; not a Phase 3 deliverable per the stream 1 deferral note.
- **Full execution-side migration support** — `db-migration-planner` ships skeleton only (contract + schema). The migration-applier write-tier agents that consume the plan land Phase 4+.
- **Full review-side breaking-change support** — `api-breaking-change-analyzer` ships skeleton only. The API stack reviewers that gate merges + propose deprecation timelines land Phase 6+.
- **Cwd-aware multi-stack detection** — carry-forward from Phase 2; Phase 3 did not revisit it.

### Tier-3 closed during phase

None. TR-0003 (memory-tier-mismatch on read/reason agents) remains OPEN; resolution requires framework-owner clarification of `memory: project` semantics in CC plugin frontmatter, then either a rule narrowing or a sweep PR.

### Lessons accreted to auto-memory (durable across sessions)

- **Reason-tier analyst pattern is now mature.** Three identical-shape analysts shipped (architecture-reconstructor, migration-planner, breaking-change-analyzer) using the same `inputs[]` + `summary.<>_status` four-way enum + open-vocab `kind` + bounded enums + `evidence: minItems 1` template. Phase 4+ telemetry analysts can be templated from any of the three.
- **`memory: project` semantics on read/reason-tier agents is genuinely ambiguous** in CC plugin frontmatter (TR-0003). Until clarified, the working pattern is `memory: project` to match the established 7+ agents on master.
- **Always run `uv run pytest`, not `uv run pytest hooks/tests/`**, for validation footers. The narrower invocation hides breakage in `scripts/tests/`. Two stale tests in `test_bootstrap_smoke.py` had been failing since the Phase 1→2 transition because Phase 2's footer-validation didn't include `scripts/tests/` — a discipline gap in the validation footer protocol.

## Dogfooding summary

Every commit on master from here is subject to the Phase 1+2 enforcement plus Phase 3's structural checks: every new scanner agent file is verified for tier consistency at smoke time; every new report schema must self-validate against the meta-schema and accept a minimal positive example. The 28-assertion smoke runs under one minute and anchors the framework's "every assertion is a contract you can lose" discipline.

Phase 3's value proposition — *the framework can ingest brownfield code as data without re-deriving its shape on every reviewer invocation* — is realised. Phase 4's closed-loop infrastructure (telemetry, incident retrospective, quality scorer) now has structured scanner outputs to consume; what remains is to build the analysts that aggregate them across runs.
