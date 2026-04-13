# Session Lifecycle

This rule governs how every agent works in this repo. Follow it from the first prompt to the last commit.

## The Objective Lifecycle

Every unit of work follows these 7 steps. No exceptions, no shortcuts.

### 1. OBJECTIVE

State what you are building, why, and the acceptance criteria. Be specific. "Write _hook_shared.py" is a task. "Provide uniform hook input parsing, branch detection, and threshold computation so all 12 hooks share common primitives" is an objective. Acceptance criteria are testable conditions — not "it works" but "tests pass, mypy clean, read_hook_input parses valid and invalid JSON."

### 2. GAP

Analyse the current state. What exists? What's missing? What do you need to read before designing? Read the relevant files — don't assume you know what's in them. Check git status. Check what's committed vs uncommitted. If a prior session left work in progress, understand where it stopped and why.

### 3. DESIGN

Decide how to build it. What patterns to follow? What existing code to reuse? What decisions need making? For non-trivial work, state the design explicitly before writing code. For small changes, a sentence is enough. The point is: think before typing.

### 4. IMPLEMENT

Write the code. Follow the conventions in `hooks/CLAUDE.md` for hook code. Use `_os_safe` for all file I/O. Keep files focused — one hook per file, one concern per module.

### 5. VALIDATE

Run the full check suite **deliberately, as a distinct step**:

```
uv run ruff check <files>
uv run ruff format --check <files>
uv run mypy <files>
uv run pytest <test_files> -v
```

Do not scatter validation across implementation. Do not claim validation passed without actually running it. Verify each acceptance criterion from step 1.

### 6. COMMIT

If the objective is complete and validation passes: commit with a descriptive message.

If context pressure makes LITM a real risk but the objective isn't complete: **WIP commit**.

```
git commit -m "[WIP] <what was done and what remains>"
```

WIP commits are context-loss mitigation. They checkpoint progress so the next session can resume rather than re-derive. They are not a substitute for completing the objective — the next session must finish the work and commit properly.

**Never let validated work sit uncommitted.** A crash, a `/clear`, or a compaction event can lose uncommitted work. Commit is the checkpoint.

### 7. REFLECT

After every commit, before starting the next objective — examine the cycle:

- **Process:** Did you follow all 7 steps? If you deviated, why?
- **Surprises:** Anything unexpected? Edge cases, spec gaps, wrong assumptions?
- **Next objective:** Does what you learned change how you approach the next one?
- **Process improvement:** Should this rule be updated?

Reflection produces one of:
- A **feedback memory** (if the learning applies to future sessions)
- An **update to this rule** (if the process itself should change)
- **Nothing** (if the cycle went cleanly — don't fabricate reflection)

## Handoff Protocol

When context usage is high or the session is ending:

1. Commit current work (complete commit or WIP commit — never leave work uncommitted)
2. Update session memory with: what was done, what remains, the current git state, any decisions made
3. Note the current branch and commit hash
4. List the next objective and its acceptance criteria

The next session reads this state and picks up from step 2 (GAP) of the next objective.

## Branch Discipline

- Never commit directly to `master`. Use feature branches under `feat/<category>-<slug>`.
- One objective = one commit on the feature branch (or one WIP + one completion commit if split across sessions).
- Feature branches are merged to master via PR after all objectives on that branch are complete.

## What This Rule Does Not Cover

- **Hook conventions** — see `hooks/CLAUDE.md`
- **Stamp validation** — see `docs/architecture/principles/stamps.md` (Phase 1+)
- **Context budgets** — see `docs/architecture/principles/context-awareness.md`
- **Agent frontmatter** — see `.claude/rules/agent-frontmatter.md`

Those are separate concerns with their own rules and docs. This rule covers the development process — how you work, not what you build.
