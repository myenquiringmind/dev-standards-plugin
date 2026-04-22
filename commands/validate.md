---
context: fork
model: sonnet
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent
argument-hint: [optional gate: code | frontend | agent | db | api | all]
description: Run CLI checks, invoke blocking validation agents, write stamps for every applicable gate. The keystone producer for pre_commit_cli_gate.
phase: validate
---

# /validate — run validation gates and stamp

Execute the validation protocol. Produces one or more stamp files that `pre_commit_cli_gate.py` consumes on `git commit`. A stamp is branch-specific and lives 15 minutes.

The canonical step tuples for each gate are the single source of truth in `hooks/_hook_shared.py` — `PY_VALIDATION_STEPS`, `FE_VALIDATION_STEPS`, `AGENT_VALIDATION_STEPS`. Do not duplicate them here; read them at runtime.

## Procedure

1. **Detect applicable gates.** Run `git diff --cached --name-only`. If nothing is staged, run `git diff --name-only` against the working tree. Classify files:
   - `*.py` → **code** gate
   - `*.ts` / `*.tsx` / `*.js` / `*.jsx` / `*.mjs` / `*.cjs` / `*.vue` / `*.svelte` / `*.css` / `*.scss` → **frontend** gate
   - `agents/**/*.md` → **agent** gate
   - `**/migrations/*.sql` → **db** gate
   - `api/**/*.{yaml,yml,json}` or any `openapi.*` → **api** gate

   If `$ARGUMENTS` names a specific gate, only validate that gate. If `$ARGUMENTS` is `all`, validate every applicable gate even when no files in the diff trigger it.

2. **For each required gate, run the CLI steps in order.** Every step is named in the canonical tuple; run the exact-named tool. Record pass/fail and elapsed time for each.

   - **code** (`PY_VALIDATION_STEPS`):
     - `ruff-check` → `uv run ruff check hooks/ scripts/`
     - `ruff-format` → `uv run ruff format --check hooks/ scripts/`
     - `mypy-strict` → `uv run mypy --strict hooks/ scripts/`
     - `pytest` → `uv run pytest`
   - **frontend** (`FE_VALIDATION_STEPS`):
     - `eslint` → `npm run lint` (or `pnpm lint` / `yarn lint` as configured)
     - `tsc-strict` → `npx tsc --noEmit --strict`
     - `vitest` → `npx vitest run`
   - **agent** gate has no CLI steps; the agent-specific step is invoked in step 3.
   - **db** / **api** gates have no Phase 1 CLI steps (empty canonical tuple in `pre_commit_cli_gate._CANONICAL_STEPS`); write the stamp with the detected steps from the diff.

   If any CLI step fails, surface the tool's output and **stop** for that gate — do not invoke the reviewer agents. A CLI-failed gate produces no stamp.

3. **Invoke the blocking reviewer agents.** Via the `Agent` tool. The agents themselves read the current branch, staged diff, and `<memory>/session-state.md`:
   - Every gate: `validation-objective-verifier` → must return `status: pass`.
   - Every gate: `validation-completion-verifier` → must return `status: pass`.
   - **agent** gate additionally: `meta-command-composition-reviewer` (only if `commands/` or `agents/` changed).

   If any agent returns `status: fail`, surface the error codes and the agent's `detail` / `path` fields. Do not write the stamp for that gate.

4. **Write the stamp.** Invoke `uv run python -m hooks.stamp_validation --gate <gate> --step <step1> --step <step2> ...`. Pass every canonical step name that ran green. The CLI handles schema validation and branch detection; if it exits non-zero, surface the error and **do not** declare the gate passed.

5. **Report.** One clear line per gate:

   ```
   [validate] code      ✅ stamp written (5 steps, 12.3s)
   [validate] agent     ✅ stamp written (1 step, 0.8s)
   [validate] frontend   — skipped (no matching files)
   [validate] db        ❌ gate failed: objective-verifier returned drift on hooks/foo.py
   ```

   End with a validation footer in the shape `.claude/rules/stewardship-ratchet.md` defines. If every required gate passed, the next `git commit` will clear `pre_commit_cli_gate.py` without a `[WIP]` marker.

## Do not

- Do not write a stamp for a gate whose CLI or agent steps failed. A red stamp is a worse failure mode than a missing stamp — the commit gate would accept the red stamp as evidence and let broken work land.
- Do not accept `--no-verify` or any hook-skipping shortcut. `/validate` exists because the hooks are the source of truth; undermining them defeats the whole framework.
- Do not re-run a step that already passed in the same session unless the files it covers have changed. Spending CI time on known-green work is noise; surface the cached result from the existing stamp (check the `timestamp` freshness — within 15 minutes and same branch is reusable).
- Do not validate against the working tree if a staged diff exists. The stamp must cover the *committable* set, not the superset. If the author wants working-tree validation, they omit the stage (`git reset HEAD .` first).
- Do not pass `$ARGUMENTS` through blindly. Accept only the five gate names plus `all`; anything else is a single-line usage error and exit 0 (do not attempt partial validation on an unknown gate).

## Final check

Before reporting success, verify for each gate you claimed to validate:
- [ ] All CLI steps ran and exited zero (not "probably passed").
- [ ] All required agent verdicts returned `status: pass`.
- [ ] `hooks/stamp_validation.py` exited zero and the stamp file exists.
- [ ] The stamp's `branch` field matches `git rev-parse --abbrev-ref HEAD`.

If any box is unchecked, the gate has not passed. Report it as failed, do not declare completion.

## Phase 1 note

Phase 1 canonical tuples are the *narrowed* set — see `hooks/_hook_shared.py` docstring on `PY_VALIDATION_STEPS`. The Phase-6 stack agents (`py-solid-dry-reviewer` etc.) are not yet canonical; do not invoke them. They will be added to the tuples and to this command's step 3 as they land in later phases. `/validate` must keep the invocation list in sync with the tuples — a hard-coded list that drifts from `_hook_shared.py` is a bug.
