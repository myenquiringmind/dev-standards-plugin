# Phase 1 — Exit Report

Phase 1 delivered the minimum-viable self-hosting lifecycle: the bootstrap core of hooks, agents, commands, schemas, tooling scripts, and a 13-assertion smoke test. The framework now validates its own commits using its own infrastructure. This report records the gate results and the carry-forward work.

## What shipped

| Branch | Deliverables | PRs |
|---|---|---|
| 3 | `stamp_validation.py` + `write_agent_memory.py` + plugin manifest v2.0.0 | #23, #24 |
| 4 | 5 core hooks (`pre_commit_cli_gate`, `session_checkpoint`, `statusline`, `post_edit_doc_size`, `session_start_gitignore_audit`) + `pre_commit_secret_scan` follow-up | #25, #26, #27, #28, #29 |
| 5 | 3 v2 commands (`/handoff`, `/validate`, `/setup`); v1 legacy `/validate` + `/setup` atomically replaced | #30, #43 |
| 6 | 10 core agents: `meta-agent-scaffolder`, `meta-graph-registry-validator`, `meta-command-composition-reviewer`, `meta-session-planner`, `validation-objective-verifier`, `validation-completion-verifier`, `discover-project-state-classifier`, `discover-setup-wizard`, `closed-loop-transcript-todo-extractor`, `closed-loop-context-rolling-summarizer` | #31-#40 |
| 7 | `scripts/build_graph_registry.py` (node discoverer); 2 language profiles already landed in Phase 0b | #41 |
| 7.5 | Phase-gap decision — canonical tuples in `_hook_shared.py` narrowed to Phase-1-available steps (Path A) | #42 |
| 8 | `scripts/bootstrap_smoke.py` — the 13-assertion exit-gate test | #44 |

22 PRs landed across this phase (#23 through #44). Two schemas shipped under `schemas/reports/`: `project-state.schema.json` (with #36), `transcript-todo-extraction.schema.json` (with #37).

## Mechanical gate results

`scripts/bootstrap_smoke.py` was run from master after every PR in the second half of the phase. Final run, against master at `8ccf2a4` (post-#44):

```
[bootstrap-smoke]  1/13 [PASS] validate-command-present
[bootstrap-smoke]  2/13 [PASS] objective-verifier-present
[bootstrap-smoke]  3/13 [PASS] commit-without-stamp-blocks
[bootstrap-smoke]  4/13 [PASS] valid-stamp-passes
[bootstrap-smoke]  5/13 [PASS] stale-stamp-blocks
[bootstrap-smoke]  6/13 [PASS] wip-bypass
[bootstrap-smoke]  7/13 [PASS] merge-head-bypass
[bootstrap-smoke]  8/13 [PASS] path-traversal-rejected
[bootstrap-smoke]  9/13 [PASS] agent-tier-consistency - checked 10 agents
[bootstrap-smoke] 10/13 [PASS] transcript-todo-extractor-schema
[bootstrap-smoke] 11/13 [PASS] doc-size-limit
[bootstrap-smoke] 12/13 [PASS] context-budget-hard-cut
[bootstrap-smoke] 13/13 [PASS] secret-scan-and-gitignore
[bootstrap-smoke] 13/13 passed - Phase 1 exit gate OK
```

Exit gate: **13/13**. Full Python test suite at exit: **429/429**. Ruff, ruff-format, mypy-strict, pytest all clean.

**Note on structural checks.** Assertions 1, 2, and 10 are exercised *structurally* — the smoke test verifies the command/agent files exist with expected frontmatter and schema references. Full live-LLM integration is deferred to Phase 2's CI harness because a standalone Python script cannot invoke a Claude Code subagent.

## Integration gates — pending live verification

Gates I1–I3 require a CC restart after the marketplace clone refresh. The session that built Phase 1 predates many of the hooks it now ships; the new stamp gate does not take effect until CC reloads.

| # | Gate | Manual test |
|---|---|---|
| I1 | `/validate` produces a stamp end-to-end | Run `/validate code` on a staged Python change; expect one of `.validation_stamp` files written with fresh timestamp + canonical step list |
| I2 | First non-`[WIP]` commit through the stamp gate | With I1's stamp fresh (<15min), attempt `git commit` without `[WIP]`; expect commit to succeed (no hook rejection) |
| I3 | Stamp expiry enforced in the wild | Wait 16 minutes after I1 stamp, retry commit; expect `[pre_commit_cli_gate]` block with stale-stamp error |

The smoke test already exercises equivalent logic in isolation. I1-I3 confirm the end-to-end wiring once the plugin is reloaded.

## Scope expansions accepted in-phase

| Change | Why | PR |
|---|---|---|
| `schemas/reports/` directory first populated | `discover-project-state-classifier` + `closed-loop-transcript-todo-extractor` both produce JSON reports; their schemas land with their respective agents rather than a separate PR | #36, #37 |
| Canonical tuples narrowed to Phase-1 steps | The original tuples listed Phase-6 agents that do not exist yet. Path A (narrow now, grow later) chosen over Path B (`not-yet-implemented` placeholder state) to keep stamps honest | #42 |
| `scripts/` as a Python package | Phase 1 introduced the first Python tooling outside `hooks/`. `scripts/__init__.py` + `scripts/tests/` mirrors the `hooks/` convention | #41 |
| v1 legacy `/validate` + `/setup` removed | Replacing v1 files atomically with v2 replacements (single commit) avoids a window where the framework has no `/validate` | #43 |

None of these widened the **exit gate** — the 13 assertions remain exactly as specified. Each expansion is documented in its PR description and in session-state memory.

## Carry-forward work

### To Phase 2

- **Live-integration CI harness.** Assertions 1, 2, 10 run structurally today. Phase 2 adds a harness that invokes actual subagents (via the SDK or a headless CC session) and asserts their AgentVerdict shape.
- **`meta-agent-arch-doc-reviewer`.** Adds `agent-arch-doc-reviewer` to `AGENT_VALIDATION_STEPS` per the narrow-now-grow-later plan.
- **Remaining 25 hooks** from Phase 2 spec (tier-enforcement hooks, telemetry hooks, etc.).

### Tier-3 closed during phase

- `.gitignore` entries for `.validation_stamp*`, `.context_pct`, `session-state.md.injected` — added in this exit PR after `session_start_gitignore_audit` had its live-firing test.
- `schemas/CLAUDE.md` — refreshed in this exit PR to note `schemas/reports/` now has two entries.

### Tier-3 carried to Phase 2

- `docs/guides/statusline-wiring.md` — how-to for users wiring `statusline.py` into their `~/.claude/settings.json`.
- Legacy v1 command cleanup (`fix.md`, `plan.md`, `review.md`, `typecheck.md`, `logs.md`) — out of Phase 1 scope; replaced atomically alongside their Phase 6 stack-agent replacements.

## Dogfooding summary

The framework is now self-hosting at the mechanical level. Every commit from here on is subject to:

- `branch_protection` blocking direct writes on `master`.
- `pre_write_secret_scan` rejecting known secret patterns.
- `post_edit_doc_size` enforcing the 200-line docs limit.
- `pre_commit_cli_gate` enforcing stamp freshness + canonical-step superset on `git commit`.
- `session_checkpoint` writing periodic state snapshots.
- `statusline` publishing context usage to `.context_pct`.
- `context_budget` forcing `/handoff` before auto-compaction can fire.

Phase 1's value proposition — *the framework validates its own commits* — is realised. The next commit to master not marked `[WIP]` will be the first through the full stamp gate in anger.
