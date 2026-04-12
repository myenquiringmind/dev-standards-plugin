# Validation Stamps — 3+ Stamp Model

The framework enforces a **5-stamp validation gate model** at commit time. Stamps are the mechanical proof that validation ran and passed. Without a valid, fresh, branch-matched stamp, `git commit` is blocked by `hooks/pre_commit_cli_gate.py`.

## The five stamps

| Stamp file | Gate category | When required |
|---|---|---|
| `.validation_stamp` | code | Python or JavaScript source files staged |
| `.frontend_validation_stamp` | frontend | Frontend (React/TS) files staged under `frontend/` or similar |
| `.agent_validation_stamp` | agent | Files under `.claude/`, `agents/`, `commands/`, `hooks/` staged |
| `.db_validation_stamp` | db | Migration files (`migrations/*.py`, `alembic/versions/*`, etc.) staged |
| `.api_validation_stamp` | api | API route files or OpenAPI specs staged |

**Language-aware multi-gate.** `pre_commit_cli_gate.py` decides *which* stamps are required for a given commit based on which files are staged. Touch only Python → only `.validation_stamp` required. Touch `.claude/` too → also `.agent_validation_stamp`. Automatic, no explicit routing.

## Stamp contents

Every stamp is JSON validated by `schemas/stamp.schema.json`:

```json
{
  "timestamp": "2026-04-11T10:00:00Z",
  "branch": "feat/bootstrap-os-safe",
  "steps": ["ruff-check", "ruff-format", "mypy-strict", "pytest", "py-solid-dry-reviewer", "..."],
  "ttl_seconds": 900,
  "version": "1.0.0",
  "gate": "code",
  "plugin_commit": "abc1234"
}
```

- **`timestamp`** — when the stamp was written. Combined with `ttl_seconds` to determine freshness.
- **`branch`** — the git branch the stamp was written on. Branch switch invalidates the stamp.
- **`steps`** — ordered list of validation step names that passed. Must match the canonical step tuple for this gate in `hooks/_hook_shared.py`.
- **`ttl_seconds`** — fixed at 900 (15 minutes). Hard-coded per Modelling precedent; prevents arbitrary extension.
- **`gate`** — which gate category this stamp represents.
- **`plugin_commit`** — git SHA of the installed plugin that produced this stamp. Enables drift detection between the installed plugin and the worktree being validated.

## Invalidation

A stamp is invalid if any of the following:

- **Age > 15 minutes** (TTL exceeded)
- **Branch changed** (detected via `.git/HEAD`)
- **Steps don't match** the canonical tuple for that gate in `_hook_shared.py`
- **File missing or unreadable** for one of the required gates

Invalid stamps produce exit 2 on `git commit` with a message explaining which stamp failed and why.

## Bypasses (the only two)

The pre-commit gate is mechanically enforced with no human override except:

1. **`[WIP]` in the commit message** — emergency handoff escape hatch. Used when context is near the hard cut and the user needs to save and restart.
2. **`.git/MERGE_HEAD` exists** — merge-in-progress. Conflict resolution commits are exempt because the committer isn't producing new work, just resolving conflicts.

**No other bypasses.** `--no-verify` does not help because the gate lives in CC's PreToolUse hook, not in git's commit-msg hook. Compensating controls at Phase 2 ensure `--no-verify` is ignored.

## Canonical step tuples

Single source of truth in `hooks/_hook_shared.py`:

```python
PY_VALIDATION_STEPS = (
    "ruff-check", "ruff-format", "mypy-strict", "pytest",
    "objective-verifier", "py-solid-dry-reviewer",
    "py-security-reviewer", "py-doc-checker",
    "py-arch-doc-reviewer", "py-code-simplifier",
    "py-tdd-process-reviewer",
)

FE_VALIDATION_STEPS = (
    "eslint", "tsc-strict", "vitest",
    "fe-code-simplifier", "fe-security-reviewer",
    "fe-doc-checker", "fe-component-reviewer",
)

AGENT_VALIDATION_STEPS = (
    "meta-agent-arch-doc-reviewer",
    "meta-command-composition-reviewer",
)

DB_VALIDATION_STEPS = ("db-schema-reviewer", "db-migration-safety-reviewer")

API_VALIDATION_STEPS = ("api-contract-reviewer", "api-type-boundary-reviewer")
```

Adding a new step requires updating **one** tuple. Every command (`/validate`, `/validate-agents`) and every hook (`pre_commit_cli_gate`, `stamp_validation.py`) references the tuple by name.

## Writing a stamp

Stamps are written by `hooks/stamp_validation.py` after all steps in a gate pass:

```
python hooks/stamp_validation.py --gate code
python hooks/stamp_validation.py --gate agent
python hooks/stamp_validation.py --gate frontend
```

The script reads the canonical step tuple, writes the JSON stamp to the gate's file, and the stamp is valid for 15 minutes on the current branch.

## Reading a stamp

`hooks/pre_commit_cli_gate.py` reads stamps on every `git commit` attempt:

1. Determine which gates are required based on staged files
2. For each required gate, read the corresponding stamp file
3. Validate against `schemas/stamp.schema.json`
4. Check freshness, branch match, step consistency
5. If any required stamp fails → exit 2 with a specific error
6. If all pass → exit 0, commit proceeds

## Dogfooding

Every commit to `dev-standards-plugin` itself passes through this gate from Phase 1 exit onwards. The framework is its own most demanding user.
