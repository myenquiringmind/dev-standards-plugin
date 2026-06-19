---
context: fork
model: sonnet
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent
argument-hint: [optional gate: code | frontend | agent | db | api | all]
description: Run CLI checks, invoke blocking validation agents, write stamps for every applicable gate. The keystone producer for pre_commit_cli_gate.
phase: validate
fast-command: true
---

# /validate — run validation gates and stamp

Execute the validation protocol. Produces one or more stamp files that `pre_commit_cli_gate.py` consumes on `git commit`. A stamp is branch-specific and lives 15 minutes.

`/validate` declares `fast-command: true`: it is fixed-cost (run the gate's steps, stamp, report) with no fan-out or full-project walk, so it takes the sanctioned rule-3 exemption from `meta-session-planner` (see `commands/CLAUDE.md`). The agents it invokes do their own work; `/validate` itself does not need budget sizing.

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
   - **db** / **api** gates have no Phase 1 CLI steps (empty core set in `pre_commit_cli_gate._CORE_STEPS`); write the stamp with the detected steps from the diff.

   If any CLI step fails, surface the tool's output and **stop** for that gate — do not invoke the reviewer agents. A CLI-failed gate produces no stamp.

3. **Invoke the blocking reviewer agents.** Via the `Agent` tool. The agents themselves read the current branch, staged diff, and `<memory>/session-state.md`. Each reviewer's name is also the canonical *step name* you pass to `stamp_validation` in step 4 — invoke agent `X`, stamp step `X`.
   - Every gate: `validation-objective-verifier` (step `objective-verifier`) → must return `status: pass`.
   - Every gate: `validation-completion-verifier` → must return `status: pass`. (Run on every gate; not yet a canonical tuple step — do not block stamping on its absence from the tuple.)
   - **code** gate — the seven universally-applicable Python reviewers in `PY_PACK_VALIDATION_STEPS` (read them from `_hook_shared.py`; do not hard-code): `py-solid-dry-reviewer`, `py-security-reviewer`, `py-doc-checker`, `py-arch-doc-reviewer`, `py-code-simplifier`, `py-tdd-process-reviewer`, `py-logging-reviewer`. **Run these only when the `python` pack is active** — they are profile-scoped agents, and the gate likewise requires their steps only when the pack is active (`PY_CORE_VALIDATION_STEPS` — the CLI checks + `objective-verifier` — is the pack-independent floor). All return a verdict; `py-tdd-process-reviewer` is advisory (a `fail` is recorded, never blocks).
   - **code** gate — **conditional** Python reviewers, dispatched only when the staged diff warrants and added to the stamp's `--step` list when run (they are deliberately *not* in `PY_VALIDATION_STEPS`):
     - `py-migration-reviewer` — when the diff stages Alembic revisions (`*/versions/*.py` with `revision`/`down_revision`) or Django migrations (`*/migrations/*.py`).
     - `py-api-reviewer` — when the diff stages FastAPI/Django endpoint code (route decorators `@app.`/`@router.`, `APIRouter`, `from fastapi`, `rest_framework`/viewsets, `urls.py`).

     When unsure, invoke them — both scope themselves to their own files and return `status: pass` with no findings on an irrelevant diff, so over-invoking only costs a call.
   - **agent** gate additionally: `meta-command-composition-reviewer` (only if `commands/` or `agents/` changed).

   If any blocking agent returns `status: fail`, surface the error codes and the agent's `detail` / `path` fields. Do not write the stamp for that gate. (`py-tdd-process-reviewer` is advisory: record its verdict, but a `fail` does not withhold the stamp.)

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

## Canonical-tuple note

The canonical tuples in `hooks/_hook_shared.py` are the **single source of truth** for which steps a stamp must contain. Read them at runtime — a hard-coded list in this command that drifts from `_hook_shared.py` is a bug, and `pre_commit_cli_gate` will reject a stamp missing any canonical step.

As of Phase 6 the **code** gate's `PY_VALIDATION_STEPS` carries the seven universally-applicable `py-*` reviewers (listed in step 3) on top of the Phase 1 CLI + `objective-verifier` steps. The two conditional reviewers (`py-migration-reviewer`, `py-api-reviewer`) are dispatched on demand and stamped only when relevant — they are intentionally absent from the tuple (see the `_hook_shared.py` docstring for why). The `fe-*` frontend stack will grow `FE_VALIDATION_STEPS` the same way as it lands.
