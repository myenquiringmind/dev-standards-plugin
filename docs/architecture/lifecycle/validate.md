# Validate Phase

**"Is this code actually good? Prove it mechanically."**

The validate phase runs the multi-language, multi-gate validation pipeline that produces stamps. Without a valid stamp, `git commit` is blocked. This is the framework's core enforcement mechanism.

## Trigger

`/validate` (auto-invoked at end of `/tdd`, `/refactor`; manually before commit).

## Flow

### Step 0: Auto-detect

`detect_language.py` reads staged files → determines which gates to run.

### Python gate (11 steps)

| Step | Agent/tool | Type | Blocking? |
|---|---|---|---|
| 1 | `uv run ruff check` | CLI | Yes |
| 2 | `uv run ruff format --check` | CLI | Yes |
| 3 | `uv run mypy --strict` | CLI | Yes |
| 4 | `uv run pytest` | CLI | Yes |
| 5 | `validation-objective-verifier` | Agent (reason) | **Yes — blocks scope drift** |
| 6 | `py-solid-dry-reviewer` | Agent (write) | Yes |
| 7 | `py-security-reviewer` | Agent (write) | Yes |
| 8 | `py-doc-checker` | Agent (write, auto-fixer) | Auto-fixes; if files changed, re-run steps 1-4 once |
| 9 | `py-arch-doc-reviewer` | Agent (write) | Yes |
| 10 | `py-code-simplifier` | Agent (write) | Yes |
| 11 | `py-tdd-process-reviewer` | Agent (reason) | Advisory only |

If all pass: `stamp_validation.py --gate code` writes `.validation_stamp`.

### Frontend gate (7 steps)

| Step | Agent/tool | Type | Blocking? |
|---|---|---|---|
| 1 | `eslint` | CLI | Yes |
| 2 | `tsc --strict` | CLI | Yes |
| 3 | `vitest` | CLI | Yes |
| 4 | `fe-code-simplifier` | Agent | Yes |
| 5 | `fe-security-reviewer` | Agent | Yes |
| 6 | `fe-doc-checker` | Agent (auto-fixer) | Auto-fixes; re-run 1-3 once |
| 7 | `fe-component-reviewer` | Agent | Advisory only |

If all pass: writes `.frontend_validation_stamp`.

### Agent gate (2 steps)

| Step | Agent | Blocking? |
|---|---|---|
| 1 | `meta-agent-arch-doc-reviewer` | Yes |
| 2 | `meta-command-composition-reviewer` | Yes |

If all pass: writes `.agent_validation_stamp`.

### Database gate (2 steps)

| Step | Agent | Blocking? |
|---|---|---|
| 1 | `db-schema-reviewer` | Yes |
| 2 | `db-migration-safety-reviewer` | Yes |

If all pass: writes `.db_validation_stamp`.

### API gate (2 steps)

| Step | Agent | Blocking? |
|---|---|---|
| 1 | `api-contract-reviewer` | Yes |
| 2 | `api-type-boundary-reviewer` | Yes |

If all pass: writes `.api_validation_stamp`.

### Cross-cutting (every validate run)

- `testing-pyramid-enforcer` (blocking)
- `testing-coverage-per-layer-reviewer` (blocking)
- `security-secret-scanner` (blocking)
- `security-sast-runner` (blocking)
- `security-license-compliance` (blocking)
- `validation-completion-verifier` (blocking — no "done" claims without evidence)

## The commit gate

On `git commit`, `pre_commit_cli_gate.py` checks:

1. Which gates are required (based on staged files)
2. For each required gate: read the stamp, validate against `schemas/stamp.schema.json`
3. Check: fresh (<15 min), branch matches, steps match canonical tuple
4. If any fail → exit 2 with specific error
5. If all pass → exit 0, commit proceeds

**Only bypasses:** `[WIP]` in commit message, `.git/MERGE_HEAD` exists.

## Re-validation cycle

Auto-fixer agents (`py-doc-checker`, `fe-doc-checker`) can modify files. If they do, CLI checks re-run **once** (max 1 cycle per gate). Prevents runaway but catches regressions introduced by the fix.

## Telemetry

Every agent invocation produces a telemetry record (agent name, latency, verdict, confidence). Feeds `closed-loop-quality-scorer` for retrospective analysis.

## Interactions

- **Invoked by:** develop phase (`/tdd`, `/refactor`), user (`/validate`), deploy phase (`/release`)
- **Produces:** validation stamps consumed by `pre_commit_cli_gate.py`
- **Reads:** `_hook_shared.py` canonical step tuples (single source of truth)
- **Feeds:** telemetry → incident log → retrospective analyst → principles
