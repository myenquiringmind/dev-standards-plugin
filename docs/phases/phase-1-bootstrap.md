# Phase 1 — Bootstrap Spike

**Duration:** 3 weeks
**Prerequisite:** Phase 0 merged to master
**Exit gate:** `scripts/bootstrap-smoke.py` passes 13 assertions

Phase 1 delivers the minimum viable self-hosting lifecycle — the ~46-file set after which `dev-standards-plugin` validates its own commits using its own hooks, agents, and stamp gate. This is the **locked scope contract**. Additions require Phase 0 re-scope, not Phase 1 slip.

## Scope contract — ~46 files

### Shared modules (5)

- `hooks/_os_safe.py` — atomic write, portalocker lock, safe_join, normalize_path, temp lifecycle (Windows-critical)
- `hooks/_hook_shared.py` — validation step tuples, `compute_hard_cut()`, cache intervals, budgets, project dir helper, branch reader, `read_hook_input()`
- `hooks/_session_state_common.py` — `write_session_state()`, `extract_from_transcript()`, memory dir resolver, todo extraction
- `hooks/stamp_validation.py` — stamp writer for 5 gate categories (schema-validated, branch-specific, 15-min TTL)
- `hooks/write_agent_memory.py` — path-safe memory writer; stdin content, `--agent <name>`, `--append`

### Core hooks (17)

**Session lifecycle:**
- `session_start.py` — reinject state, restore todos
- `session_end.py` — save state
- `pre_compact.py` — preserve state before compaction
- `post_compact.py` — verify compaction, cleanup stale state
- `session_checkpoint.py` — auto-save every 5 edits / 15 min / phase transition

**Branch + commit gate:**
- `create_feature_branch.py` — auto-cut `feat/<slug>` from protected branches
- `branch_protection.py` — block Edit/Write on protected branches
- `pre_commit_cli_gate.py` — stamp enforcement on `git commit` + secret scan on staged diff

**Edit-time discipline:**
- `post_edit_lint.py` — language-aware lint after Edit/Write
- `post_auto_format.py` — language-aware format
- `post_edit_doc_size.py` — block markdown files >200 lines
- `pre_write_secret_scan.py` — regex secret scanner (AWS/GitHub/OpenAI/Anthropic + forbidden filenames)

**Context + security:**
- `context_budget.py` — read `.context_pct`, enforce dynamic hard cut, exit 2 on force handoff
- `statusline.py` — publish context % and absolute token estimate
- `session_start_gitignore_audit.py` — validate .gitignore covers critical patterns
- `dangerous_command_block.py` — block destructive Bash
- `post_tool_failure.py` — telemetry seed (minimum viable)

### Core commands (3)

- `/validate` — detect language → CLI checks → subagent review → stamp write
- `/handoff` — write MEMORY.md + session-state.md
- `/setup` — detect language, invoke `discover-setup-wizard`, write `.language_profile.json`

### Core agents (10)

- `meta-agent-scaffolder` (auto-fixer, worktree, write) — scaffolds remaining agents in later phases
- `meta-graph-registry-validator` (blocking, reason) — validates registry matches disk on every commit
- `meta-command-composition-reviewer` (blocking, reason) — prevents duplicated command responsibilities
- `validation-objective-verifier` (blocking, reason) — blocks scope drift on every commit
- `validation-completion-verifier` (blocking, reason) — blocks "done" claims without evidence
- `discover-project-state-classifier` (read-reason, sonnet) — classifies project as greenfield/growing-green/brownfield
- `closed-loop-transcript-todo-extractor` (read-reason-write, haiku) — watches SubagentStop, extracts deferred items to session-state.md
- `meta-session-planner` (blocking, reason, opus) — sizes every significant command against budgets, decomposes if needed
- `closed-loop-context-rolling-summarizer` (background, haiku) — fires at 60K soft warn, compresses older turns
- `discover-setup-wizard` (read-reason, sonnet) — interactive project configuration for first `/setup` run

### Schemas (6, delivered in Phase 0 or Phase 1)

- `schemas/graph-registry.schema.json` (Phase 0)
- `schemas/stamp.schema.json` (Phase 0)
- `schemas/agent-frontmatter.schema.json` (Phase 0, includes `tier` field)
- `schemas/profile.schema.json` (Phase 0)
- `schemas/reports/project-state.schema.json` (Phase 1)
- `schemas/reports/transcript-todo-extraction.schema.json` (Phase 1)

### Language profiles (2)

- `config/profiles/python.json` — minimum Python profile for linting the plugin's own hooks
- `config/profiles/javascript.json` — minimum JS profile for the existing `lib/`

### Tooling scripts (2)

- `scripts/build-graph-registry.py` — aggregates per-component manifests into `config/graph-registry.json`
- `scripts/bootstrap-smoke.py` — the Phase 1 exit gate test (13 assertions)

### Config file (1)

- `config/doc-size-limits.json` — per-pattern size limits consumed by `post_edit_doc_size.py`

## Phase 1 exit gate — 13 non-negotiable assertions

`scripts/bootstrap-smoke.py` asserts all of the following. Phase 1 does not exit until every assertion passes:

1. `/validate` runs cleanly against the bootstrap's own code
2. A deliberate scope violation (diff outside stated objective) is blocked by `validation-objective-verifier`
3. A commit without a stamp is blocked by `pre_commit_cli_gate.py` (exit 2)
4. A commit with a valid, fresh, branch-matched stamp succeeds
5. A stamp older than 15 minutes blocks a commit attempt
6. A `[WIP]` commit bypasses the gate
7. A `.git/MERGE_HEAD` bypass works during conflict resolution
8. `write_agent_memory.py --agent ../../etc/passwd` is rejected (path traversal protection)
9. Every bootstrap agent declares a `tier` field consistent with its `tools` allowlist
10. `closed-loop-transcript-todo-extractor` extracts a deferred item from a synthetic transcript
11. `post_edit_doc_size.py` blocks a 201-line markdown file, allows a 150-line one
12. Synthetic context at `compute_hard_cut() + 1` tokens triggers exit 2 on UserPromptSubmit with "run /handoff"
13. `pre_write_secret_scan.py` blocks `AKIA*` pattern; `session_start_gitignore_audit.py` warns on deliberately stripped `.gitignore`

Additional requirements before Phase 2 begins:

- `_os_safe.py` unit tests pass on Windows **and** Unix CI
- `build-graph-registry.py` rebuilds `config/graph-registry.json` from manifests; `meta-graph-registry-validator` passes against the result
- `meta-agent-scaffolder` scaffolds a throwaway agent (`agents/test/throwaway-scaffold-test.md`), validation passes, removed in the same branch

## Phase 1 branches (parallel worktrees)

Eight feature branches, worked in parallel under `C:\Users\jmarks01\Projects\dsp-worktrees\`:

1. `feat/bootstrap-os-safe` — `_os_safe.py` + pytest tests (Windows + Unix CI)
2. `feat/bootstrap-hook-shared` — `_hook_shared.py` + `_session_state_common.py` (depends on 1)
3. `feat/bootstrap-stamp-validation` — `stamp_validation.py` + `write_agent_memory.py` (depends on 2)
4. `feat/bootstrap-hooks-core` — 17 core hooks (depends on 3)
5. `feat/bootstrap-commands-core` — `/validate`, `/handoff`, `/setup` (depends on 3)
6. `feat/bootstrap-agents-core` — 10 meta/validation/discover/closed-loop agents (depends on 3)
7. `feat/bootstrap-profiles` — `python.json`, `javascript.json` + graph registry build script (depends on 2)
8. `feat/bootstrap-smoke` — `bootstrap-smoke.py` exit-gate test (serial, last; depends on 4-7)

## What is explicitly NOT in the bootstrap

Deferred to later phases. Any attempt to add these to Phase 1 is rejected as scope creep:

- Telemetry infrastructure — Phase 4
- Incident log — Phase 4
- Four-tier memory beyond session tier — Phase 4
- Language profiles beyond python + javascript — Phase 3
- MCP servers — Phase 10
- All stack agents (`py-*`, `fe-*`, `db-*`, `api-*`) — Phase 6
- Pattern, anti-pattern, security (full), testing, operate, maintain, deploy agents — Phases 6-10
- **Brownfield scanners** (`codebase-*`, `db-schema-scanner`, `api-contract-extractor`, etc.) — Phase 3
- **Tier-enforcement hooks** (`pre_bash_tier_guard.py`, `pre_tool_use_tier_enforcer.py`) — Phase 2
- `bin/dsp-wt` worktree helper — added at end of Phase 1 only after bootstrap core works without it

## References

- Canonical plan archive: `../decision-records/v2-architecture-planning-session.md` §§D, E, F, G, H
- Principles: `../architecture/principles/bootstrap-first.md`, `context-awareness.md`, `stamps.md`
- Modelling project patterns: Appendix D §D.2 (the ten interlocking mechanisms)
