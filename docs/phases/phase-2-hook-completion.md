# Phase 2 — Hook Completion

**Duration:** 2 weeks
**Prerequisite:** Phase 1 exit report merged; `bootstrap_smoke.py` 13/13 passing on master.
**Exit gate:** every hook in `docs/architecture/components/hooks.md` exists, is registered in `hooks.json`, has a pytest test file, and the extended `bootstrap_smoke.py` passes on master.

Phase 2 completes the hook layer — the deterministic enforcement rung of the Primitive Selection Framework. Phase 1 shipped 17 core hooks to make the framework self-host. Phase 2 adds the remaining ~19 hook files to bring the coverage to the full 42-event / 23-file catalog in `docs/architecture/components/hooks.md`.

## Phase 2 pre-work (already shipped)

Landing ahead of the formal Phase 2 kickoff:

- **`meta-agent-arch-doc-reviewer`** (PR #47) — agent body-structure reviewer + first tuple growth (`AGENT_VALIDATION_STEPS` 1 → 2 items). Demonstrates the narrow-now-grow-later maintenance path works end-to-end.

## Scope contract — ~21 files

### Shared modules (3 new)

- `hooks/_telemetry.py` — JSONL emission, batching, rotation. Consumed by `post_tool_failure`, `stop_failure`, and every hook that wants to record a non-blocking event.
- `hooks/_incident.py` — ULID generation, incident schema, append-only writer. Consumed by `stop_failure` and future Phase 4 observability hooks.
- `hooks/_graph.py` — Graph registry loader, query helpers, topological sort. Consumed by `file_changed`, `config_change`, and any hook that walks component relationships.

### New hooks by CC event (19 files)

**Session lifecycle:**
- `detect_language.py` — SessionStart. Writes `.language_profile.json` if absent; re-runs language detection on a cold start.
- `version_check.py` — SessionStart. 24-hour cached check for plugin updates against the marketplace clone.

**Prompt-time:**
- `phase_transition.py` — UserPromptSubmit. Detects objective-lifecycle phase changes (OBJECTIVE → GAP → DESIGN etc.) for session-state.md `## Current Phase`.

**Pre-tool guards:**
- `pre_tool_use_tier_enforcer.py` — PreToolUse Edit|Write|NotebookEdit. Blocks Edit/Write tool calls from `read` / `reason` tier subagents. Complements the schema's static `allOf` check.
- `pre_bash_tier_guard.py` — PreToolUse Bash. Gates Bash commands for R-tier agents to the read-only subset (`git status`, `ls`, `cat`, `grep`, `jq`, etc.).
- `checkpoint_gate.py` — PreToolUse Bash. Orchestrator checkpoint enforcement — long-running subagents that skip checkpointing are blocked.

**Post-tool feedback:**
- `post_track_changed_files.py` — PostToolUse Edit|Write|MultiEdit. Appends to an in-session changed-files log the orchestrator reads.
- `post_temp_file_cleanup.py` — PostToolUse Edit|Write|MultiEdit. Removes orphaned `tmpclaude-*` files older than 5 minutes.

**Stop lifecycle:**
- `stop_validation.py` — Stop. Blocks the Stop event when there are uncommitted changes that do not have a `[WIP]` commit staged.
- `stop_failure.py` — StopFailure. Writes an incident record (ULID-keyed) to the incident log. Uses `_incident.py`.

**Subagent lifecycle:**
- `subagent_start.py` — SubagentStart. Cost-budget tracker + timeout cascade propagator.

**Task / graph:**
- `task_created.py` — TaskCreated. Bridges a CC task to the session-state task-progress graph.
- `task_completed.py` — TaskCompleted. Feeds closed-loop quality scoring (consumed by Phase 4's `closed-loop-quality-scorer`).

**Config / workspace:**
- `file_changed.py` — FileChanged. Watches `config/graph-registry.json`, `config/profiles/*.json`; triggers re-validation when they drift.
- `worktree_lifecycle.py` — WorktreeCreate + WorktreeRemove. Stamps per-worktree profile on create; tears down stamps + caches on remove.
- `config_change.py` — ConfigChange. Atomic reload of profiles + graph registry + plugin manifest.
- `cwd_changed.py` — CwdChanged. Re-runs language detection when the CC cwd shifts (monorepo navigation).
- `instructions_loaded.py` — InstructionsLoaded. Audits which CLAUDE.md / rules loaded; emits telemetry.
- `permission_denied.py` — PermissionDenied. Feedback loop for auto mode — records denied tool calls for later review.

### Test coverage

Every hook gets a `hooks/tests/test_<name>.py` with the five-test discipline from Phase 1:
1. Happy path exit 0.
2. Block path exit 2.
3. Stdout/stderr content.
4. `_os_safe` usage for all disk writes.
5. Event-specific contract (schema validation for telemetry hooks; side-effect verification for stateful hooks).

Total new test files: ~21 (hooks + shared modules).

### hooks.json updates

Every new hook is registered in the appropriate event handler block. The Phase 1 shim pattern (`uv run python -m hooks.<name>`, explicit timeouts) carries forward unchanged.

## Phase 2 exit gate — extended smoke test

`scripts/bootstrap_smoke.py` grows from 13 to ~21 assertions. New assertions cover:

- **Tier-enforcement hooks** — `pre_tool_use_tier_enforcer` blocks Edit from a read-tier fixture; `pre_bash_tier_guard` rejects `rm` from a reason-tier fixture.
- **Stop-validation hook** — uncommitted changes on protected branch → stop blocks until WIP or commit.
- **Incident record** — `stop_failure` produces a ULID-keyed record in the configured incident log path.
- **Telemetry emission** — `_telemetry.py` batches and rotates a JSONL file without corrupting prior entries under concurrent writes.
- **Tuple growth path** — `meta-agent-arch-doc-reviewer` (already shipped) blocks a fixture agent file with a missing `## Procedure` section.
- **CI harness** — a single invocation of `scripts/live_integration_smoke.py` (new, Phase 2) exercises assertions 1, 2, 10 from Phase 1 with real subagent invocations. Deferred to end-of-phase once the remaining hooks land.

Full-suite targets: 500+ pytest tests, smoke 21/21, ruff/mypy-strict/pytest all clean.

## Phase 2 branches (parallel work)

Five feature branches, similar layout to Phase 1:

1. `feat/phase-2-shared-modules` — `_telemetry.py`, `_incident.py`, `_graph.py` + tests (depends only on `_os_safe.py` which already exists).
2. `feat/phase-2-tier-enforcement` — `pre_tool_use_tier_enforcer.py`, `pre_bash_tier_guard.py`, `checkpoint_gate.py` (depends on 1).
3. `feat/phase-2-stop-lifecycle` — `stop_validation.py`, `stop_failure.py` (depends on 1).
4. `feat/phase-2-subagent-workspace` — `subagent_start.py`, `task_created.py`, `task_completed.py`, `file_changed.py`, `worktree_lifecycle.py`, `config_change.py`, `cwd_changed.py` (depends on 1).
5. `feat/phase-2-session-misc` — `detect_language.py`, `version_check.py`, `phase_transition.py`, `post_track_changed_files.py`, `post_temp_file_cleanup.py`, `instructions_loaded.py`, `permission_denied.py` (depends on 1).

Each branch lands as a series of small PRs, same cadence as Phase 1.

## What is explicitly NOT in Phase 2

Deferred to later phases. Rejected as scope creep if raised in Phase 2:

- **Language profiles beyond python + javascript** — Phase 3.
- **Brownfield scanners** (`codebase-*`, `db-schema-scanner`, `api-contract-extractor`) — Phase 3.
- **Telemetry analysis agents** (`closed-loop-quality-scorer`, etc.) — Phase 4.
- **Full 4-tier memory beyond session tier** — Phase 4.
- **Stack agents** (`py-*`, `fe-*`, `db-*`, `api-*`) — Phase 6.
- **Pattern / anti-pattern / security / testing / operate / maintain / deploy agents** — Phases 6-10.
- **MCP servers** — Phase 10.
- **New commands beyond what `/validate` already composes** — Phase 6 adds `/scaffold`, `/tdd`, `/fix`, `/debug`.

## References

- Hook catalog: `docs/architecture/components/hooks.md`
- Canonical plan archive: `docs/decision-records/v2-architecture-planning-session.md` §§ E, F
- Phase 1 exit report: `docs/phases/phase-1-exit-report.md`
- Narrow-now-grow-later: `hooks/_hook_shared.py` tuple-block docstring
- Tier model: `docs/architecture/principles/rrw-tiering.md`
