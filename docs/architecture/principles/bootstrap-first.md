# Bootstrap-First Sequencing

The framework is built by the framework. Phase 1 delivers a ~46-file minimum viable self-hosting lifecycle. From Phase 2 onwards, every commit to `dev-standards-plugin` passes through `dev-standards-plugin`'s own hooks, agents, and stamp gate. The framework develops itself.

## Why bootstrap-first

The approved architecture has 156 agents, 42 hooks, 28 commands, and 11 implementation phases. A naive sequencing builds everything horizontally — all hooks, then all agents, then all commands — and only becomes usable at the end of Phase 6 (~13 weeks in). That's backwards for a framework whose purpose is dogfooding:

- A framework that cannot enforce its own rules on its own construction is a static linter in disguise
- Every new component built without the framework's own gates is a commit we can't validate with retrospective data
- Retrospective data only starts accumulating when the framework is self-hosting, so starting late means starting blind

The correct sequencing: **build the minimum viable self-hosting lifecycle first; then use it to build everything else, in worktrees, on feature branches, through the framework's own gate.**

## Modelling's ten interlocking mechanisms

The bootstrap implements ten mechanisms from the Modelling project. Nothing less is self-hosting; nothing more is required for the initial bootstrap:

1. **Session state round-trip** — `pre_compact` + `session_end` write `session-state.md`; `session_start` reads it, extracts `- [ ]` / `- [~]` todos, instructs Claude to restore via TodoWrite. Archives to `.injected` (rename, not delete) so a crash during load doesn't lose state.
2. **Transcript parsing for free context** — `extract_from_transcript()` recovers modified_files, errors, recent reasoning from the JSONL transcript.
3. **Auto-feature-branch** — first edit on a protected branch triggers `create_feature_branch.py` to cut `feat/<category>-<slug>`.
4. **Branch protection** — Edit/Write on protected branches blocked by `branch_protection.py` before the tool runs.
5. **Independent validation stamps** with 15-minute TTL, branch-specific. Switching branch or letting time pass invalidates.
6. **Stamp-enforced commit gate** — `pre_commit_cli_gate.py` exits 2 on missing/stale/wrong-branch/wrong-steps stamp. Only bypasses: `[WIP]` prefix, `.git/MERGE_HEAD`.
7. **Language-aware multi-gate** — which stamps are required is determined by which files are staged. No explicit routing.
8. **Auto-fixer re-validation cycle** — capped at 1 cycle to prevent runaway loops.
9. **Persistent agent memory via Bash helper** — read-only agents learn across sessions via `write_agent_memory.py`; path-validated.
10. **Single source of truth for validation steps** — tuples in `_hook_shared.py`, referenced everywhere.

## The bootstrap contract

The bootstrap is a **locked scope contract**: what's in, what's out, what the exit gate looks like. Any addition to the bootstrap requires an explicit architectural decision, not a Phase 1 slip.

**In the bootstrap (Phase 1, ~46 files):**

- 5 shared modules (`_os_safe.py`, `_hook_shared.py`, `_session_state_common.py`, `stamp_validation.py`, `write_agent_memory.py`)
- 17 core hooks (session + compaction + branch protection + stamps + auto-format/lint + context + security + statusline)
- 3 core commands (`/validate`, `/handoff`, `/setup`)
- 10 core agents (meta + validation + transcript extractor + project state classifier + session planner + rolling summarizer + setup wizard)
- 6 schemas (4 foundational + 2 report schemas)
- 2 language profiles (python, javascript)
- 2 tooling scripts (`build-graph-registry.py`, `bootstrap-smoke.py`)
- 1 config file (`doc-size-limits.json`)

**Not in the bootstrap (deferred):**

- Telemetry infrastructure (Phase 4)
- Incident log (Phase 4)
- Four-tier memory beyond session tier (Phase 4)
- Closed-loop agents beyond rolling summarizer (Phase 4/10)
- Language profiles beyond python + javascript (Phase 3)
- MCP servers (Phase 10)
- All stack agents (Phase 6)
- Pattern, anti-pattern, security, testing, operate, maintain, deploy agents (Phases 6-10)
- Documentation beyond the principles, phase 0/1 specs, and foundational ADRs (dogfooded in later phases by `doc-*` agents)

## The exit gate — `bootstrap-smoke.py`

Thirteen non-negotiable assertions. Phase 1 does not exit until `scripts/bootstrap-smoke.py` passes all thirteen. Details in `@docs/phases/phase-1-bootstrap.md`.

Key assertions:

1. `/validate` runs cleanly against the bootstrap's own code
2. Scope violations blocked by `validation-objective-verifier`
3. Commits without stamps blocked by `pre_commit_cli_gate.py`
4. Stale stamps (>15 min) block commits
5. `[WIP]` and `.git/MERGE_HEAD` bypasses work
6. `write_agent_memory.py --agent ../../etc/passwd` rejected (path traversal)
7. Every bootstrap agent declares `tier` consistent with its tools
8. `closed-loop-transcript-todo-extractor` extracts deferred items from a synthetic transcript
9. `post_edit_doc_size.py` blocks a 201-line markdown file
10. Dynamic hard cut blocks new work when synthetic context exceeds the cut
11. `pre_write_secret_scan.py` blocks deliberate secret patterns
12. `session_start_gitignore_audit.py` warns on missing critical gitignore entries
13. `meta-agent-scaffolder` scaffolds a throwaway agent and removes it successfully

## Worktree discipline (from Phase 2)

Once the bootstrap is live, every new component is developed in its own worktree:

```
git worktree add C:/.../dsp-worktrees/feat-<slug> -b feat/<slug> master
cd C:/.../dsp-worktrees/feat-<slug>
# work happens here
/validate    # the installed plugin gates the worktree
git commit   # the gate enforces the stamps
```

The **installed plugin is the known-good master copy**. Worktrees are workspaces for in-progress features. Validation uses the installed master gate to validate code that will eventually replace it. The framework remains stable while it modifies itself.

## Pre-bootstrap exemption

Phase 0 commits and the first pass of Phase 1 commits are **pre-bootstrap**. The gate doesn't exist yet. These commits are explicitly exempt and are recorded in the incident log as historical context once the gate goes live. From Phase 1 exit onwards, **every commit is gated**. No exceptions.
