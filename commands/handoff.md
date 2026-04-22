---
context: none
model: haiku
allowed-tools: Bash, Read, Write, Edit, Glob
argument-hint: [optional note about why you're handing off]
description: Write a fresh session-state file and update the MEMORY.md index, then signal readiness for /clear.
---

# /handoff — prepare a clean session handoff

Execute the handoff protocol from `.claude/rules/session-lifecycle.md`. Your job is to leave the next session a complete, portable picture of where this session landed.

The canonical steps (reproduced from `HANDOFF_STEPS` in `hooks/_hook_shared.py`):

1. **Commit current work** — run `git status`. If there are uncommitted staged changes and they form a coherent objective, commit them. If they are partial, `[WIP]` commit them with a `Next session first:` footer line per `.claude/rules/stewardship-ratchet.md`.
2. **Update session memory** — write a `session_state_<YYYY-MM-DD>_<slug>.md` file to the auto-memory directory with: what was done, what remains, current git state, any decisions made.
3. **Note the current branch and commit hash** — include `git rev-parse --abbrev-ref HEAD` and `git rev-parse --short HEAD` in the memory file.
4. **List the next objective and its acceptance criteria** — be concrete. "Continue work" is not an objective. "Implement `commands/validate.md` per Phase 1 spec, acceptance: frontmatter present, phase-gap question resolved in the prompt" is an objective.
5. **Signal ready for /clear** — print `Handoff complete. Safe to /clear.` as the last line of your reply.

## Mechanics

- **Memory directory.** Find it by running `uv run python -c "from hooks._session_state_common import get_memory_dir; from hooks._hook_shared import get_project_dir; print(get_memory_dir(get_project_dir()))"`. Do not hard-code the path.
- **File naming.** New session-state files follow `session_state_<YYYY-MM-DD>_<slug>.md`. The slug is a 2-to-4-word kebab-case description of the session's focus (e.g. `handoff-command`, `validate-phase-gap-decision`).
- **Frontmatter.** Every memory file is a real memory (per the auto-memory system described in your system prompt). Use the `type: project` frontmatter with a one-line `description` that the next session can read from `MEMORY.md`.
- **MEMORY.md index.** Add a one-line pointer to the new file at the top of the "Session state" cluster. Mark any older session-state entries as **Superseded** with a `--` suffix so the next session can trust the freshest one.

## Minimum content for the new session-state file

Always include these sections, even if some are empty:

- `### What shipped this session` — PRs opened/merged, commits landed, tier-3 items closed.
- `### Repo state at handoff` — branch, ahead/behind master, test count, last validation-footer timestamp.
- `### Design decisions captured this session` — any architectural choice made (or explicitly deferred) that the next session should not re-derive.
- `### Outstanding work` — split by branch or by tier (tier-3 todo-registry items, tier-2 sidecar candidates).
- `### Resume procedure for next session` — numbered steps: read this file, check PR status, sync master, refresh marketplace clone (`git -C "$USERPROFILE/.claude/plugins/marketplaces/<owner>" pull origin master`), apply the branch-pickup protocol, then start the next objective.
- `### Key reference files` — paths the next session will need to re-read (Phase spec, rules, schemas).

## Do not

- Do not run `/clear` yourself. That is the user's call.
- Do not compress unresolved threads into "will sort out later" hand-waves. If a decision was deferred, say so explicitly and name the blocker.
- Do not write the session-state into `docs/` or into the repo tree. It belongs in the auto-memory directory, which is outside the repo.
- Do not skip the validation footer lookup. Include the last commit's `Validated:` line verbatim so the next session can trust the branch without re-running the check suite.

## Final check

Before printing `Handoff complete`, verify:

- [ ] A new session-state file exists at the resolved memory path.
- [ ] `MEMORY.md` has a fresh one-line pointer to it.
- [ ] Older session-state entries in `MEMORY.md` are marked superseded.
- [ ] The next objective is specific enough that an empty-context agent could pick it up.

If the user passed `$ARGUMENTS`, treat that note as the narrative frame for "what shipped this session" — weave it into the session-state file's opening paragraph.
