# Phase 2 — Exit Report

Phase 2 completed the hook layer. Every CC lifecycle event in `docs/architecture/components/hooks.md` is now wired to a Python hook with tests, registered in `hooks/hooks.json`, and exercised by the extended `bootstrap_smoke` exit gate. Three new shared modules (`_telemetry`, `_incident`, `_graph`) underpin the new hooks. The framework's deterministic-enforcement rung is feature-complete; LLM-tier consumers (Phase 4 closed-loop scorers, retrospective analysts) now have the durable observability records they need.

## What shipped

| Group | Deliverables | PRs |
|---|---|---|
| Pre-Phase-2 prep | `meta-agent-arch-doc-reviewer` agent + first `AGENT_VALIDATION_STEPS` tuple growth | #47 |
| Phase 2 spec | `docs/phases/phase-2-hook-completion.md` itself | #48 |
| Shared modules | `_telemetry.py`, `_incident.py`, `_graph.py` | #49, #50, #51 |
| Tier enforcement | `pre_tool_use_tier_enforcer`, `pre_bash_tier_guard`, `checkpoint_gate` | #52, #53, #54 |
| Stop lifecycle | `stop_validation`, `stop_failure` | #55, #56 |
| Subagent / workspace | `task_created`, `task_completed`, `file_changed`, `cwd_changed`, `config_change`, `worktree_lifecycle`, `subagent_start` | #57, #58, #59, #67, #68, #69, #70 |
| Session-misc | `post_temp_file_cleanup`, `permission_denied`, `post_track_changed_files`, `detect_language`, `instructions_loaded`, `phase_transition`, `version_check` | #60, #61, #62, #63, #64, #65, #66 |
| Process | Multi-branch coord doc updates (pre-cut PR check + implicit shared-resource discipline) | #72 |
| Repair | Restore `WorktreeCreate` / `WorktreeRemove` registrations dropped during PR #69 merge resolution | #71 |
| Exit gate | `bootstrap_smoke` extended from 13 → 21 assertions | #73 |

28 PRs landed across this phase (#46–#73, with #46 a Phase 1 carry-forward). Two new shared modules joined `_hook_shared`, `_session_state_common`, `_os_safe`: the framework now has six shared modules that hooks compose against.

## Mechanical gate results

`scripts/bootstrap_smoke.py` final run, against master at `faea788` (post-#73):

```
[bootstrap-smoke]  1/21 [PASS] validate-command-present
[bootstrap-smoke]  2/21 [PASS] objective-verifier-present
[bootstrap-smoke]  3/21 [PASS] commit-without-stamp-blocks
[bootstrap-smoke]  4/21 [PASS] valid-stamp-passes
[bootstrap-smoke]  5/21 [PASS] stale-stamp-blocks
[bootstrap-smoke]  6/21 [PASS] wip-bypass
[bootstrap-smoke]  7/21 [PASS] merge-head-bypass
[bootstrap-smoke]  8/21 [PASS] path-traversal-rejected
[bootstrap-smoke]  9/21 [PASS] agent-tier-consistency - checked 11 agents
[bootstrap-smoke] 10/21 [PASS] transcript-todo-extractor-schema
[bootstrap-smoke] 11/21 [PASS] doc-size-limit
[bootstrap-smoke] 12/21 [PASS] context-budget-hard-cut
[bootstrap-smoke] 13/21 [PASS] secret-scan-and-gitignore
[bootstrap-smoke] 14/21 [PASS] tier-enforcer-blocks-edit
[bootstrap-smoke] 15/21 [PASS] bash-tier-guard-blocks-rm
[bootstrap-smoke] 16/21 [PASS] stop-validation-dirty-tree
[bootstrap-smoke] 17/21 [PASS] stop-failure-incident
[bootstrap-smoke] 18/21 [PASS] telemetry-concurrent
[bootstrap-smoke] 19/21 [PASS] tuple-growth-path
[bootstrap-smoke] 20/21 [PASS] checkpoint-gate-stale
[bootstrap-smoke] 21/21 [PASS] secret-scan-staged
[bootstrap-smoke] 21/21 passed - Phase 1+2 exit gate OK
```

Exit gate: **21/21**. Full Python test suite at exit: **799/799**. ruff, ruff-format, mypy-strict, pytest all clean.

**Note on structural checks.** Assertions 1, 2, 10, and 19 are exercised structurally (file-presence + frontmatter + tuple-membership). Live LLM-invocation coverage stays deferred to the Phase 2 carry-forward CI harness (see below) — a standalone Python script cannot drive a Claude Code subagent.

## Scope expansions accepted in-phase

| Change | Why | PR |
|---|---|---|
| `meta-agent-arch-doc-reviewer` shipped as Phase 2 pre-work | Demonstrated the narrow-now-grow-later tuple maintenance path before the wider Phase 2 sweep depended on it | #47 |
| Multi-branch coordination guide grew | PR #69's lost `hooks.json` registrations during merge-conflict resolution surfaced a discipline gap. Two new sections: "Before cutting a branch" and "Implicit shared-resource contention" | #72 |
| Repair PR for dropped registrations | Manual conflict resolution silently dropped two event blocks. The hook landed on disk but was unwired; required a follow-up PR to restore | #71 |

None of these widened the **exit gate** — the 21 assertions remain exactly as specified in `phase-2-hook-completion.md`. Each is documented in its PR description and (for the durable lessons) in auto-memory.

## Carry-forward to Phase 3+

### Deferred from Phase 2

- **`scripts/live_integration_smoke.py`** — CI harness exercising assertions 1, 2, 10 with real subagent invocations. Spec'd in `phase-2-hook-completion.md` § exit gate; explicitly deferred because it needs an LLM-capable runtime, not a local `uv run`. Owns the assertions that `bootstrap_smoke` covers structurally.

### To Phase 3

- **Brownfield scanners** — `db-schema-scanner`, `api-contract-extractor`, `codebase-*` per the canonical plan (`docs/decision-records/v2-architecture-planning-session.md`). Phase 3's primary deliverable.
- **Cwd-aware multi-stack detection** — `detect_language` and `cwd_changed` currently scan markers at the project root only. True monorepo support (`pyproject.toml` in `services/api/` activates the python profile when the user is in that subtree) deferred to Phase 3 when scanner agents formalise multi-stack project layouts.

### Tier-3 closed during phase

- `WorktreeCreate` / `WorktreeRemove` `hooks.json` registrations restored (PR #71) after the PR #69 merge dropped them.
- `_hook_shared.py` accreted four new threshold constants (`CHECKPOINT_STALENESS_THRESHOLD_SECONDS`, `TMP_FILE_AGE_THRESHOLD_SECONDS`, `VERSION_CHECK_INTERVAL_SECONDS`, plus the existing checkpoint cadence) — single source of truth maintained.

### Lessons accreted to auto-memory (durable across sessions)

- `feedback_atomic_write_lock_collision` — `_os_safe.atomic_write` reserves the sidecar lock; an outer `locked_open` on the same path deadlocks (surfaced via PR #57 / `task_created`).
- `feedback_real_failures_over_monkeypatch` — when mypy-strict rejects a stdlib monkey-patch, switch to a real failure mode that triggers the same catch path naturally (surfaced via PR #62 / `post_track_changed_files`).
- `feedback_position_sensitive_registry_merges` — JSON registries lose entries when concurrent PRs anchor at the same line; alphabetical/append-end conventions and a post-merge audit prevent the next regression (surfaced via PR #69 / #71).

## Dogfooding summary

Every commit on master from here is subject to the Phase 1 enforcement plus:

- `pre_tool_use_tier_enforcer` blocking Edit/Write from R-tier subagents.
- `pre_bash_tier_guard` blocking destructive Bash from R-tier subagents.
- `checkpoint_gate` blocking subagent Bash when session-state has gone stale.
- `stop_validation` blocking session Stop with a dirty tree.
- `stop_failure` and `permission_denied` recording ULID-keyed incident files for Phase 4 retrospective analysis.
- `instructions_loaded`, `subagent_start` emitting structured telemetry for the closed-loop quality scorer.
- `task_created` / `task_completed` round-tripping CC's task graph through `session-state.md`.
- `detect_language` + `cwd_changed` + `worktree_lifecycle` keeping `.language_profile.json` accurate across worktree and cwd shifts.
- `config_change` invalidating on-disk caches when watched config files are edited.
- `phase_transition` reflecting objective-lifecycle state in session-state.

Phase 2's value proposition — *the framework instruments itself for closed-loop improvement* — is realised. Phase 4's quality scorer and retrospective analyst now have the records they need; what remains is to build the agents that consume them.
