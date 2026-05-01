# TR-0002: Standardize `uv` across framework outputs + add uv-env management agents

- **Discovered:** 2026-04-17, commit `03bcb86` on `master` (uv-adoption survey during power-failure resume session; requested by user)
- **Tier:** 3 (cross-cutting across commands, agent-facing docs, hooks guide, and agent catalog; scope includes net-new agents and is not mechanically obvious)
- **Description:**
  `uv` is the plugin's dev environment of record — Phase 0 lockdown committed `uv venv` and `pyproject.toml` (see `docs/phases/phase-0-architecture-lockdown.md:88`), and `uv.lock` pins every runtime dependency (`docs/architecture/principles/security.md:64`). But adoption across the framework's *outputs* is inconsistent. Two distinct gaps:

  **Gap 1 — Documentation inconsistency.** Files that invoke Python tooling bare instead of via `uv run`:
  - `commands/typecheck.md:26,29` — `mypy . --ignore-missing-imports`, `ruff check .`
  - `commands/validate.md:11,23` — `ruff check .`, `pytest`, `python -m pytest`
  - `docs/guides/getting-started.md:32` — `.venv/Scripts/python.exe -m pytest tests/schemas/`
  - `hooks/CLAUDE.md:56` — `.venv/Scripts/python.exe -m pytest hooks/tests/`
  - `docs/architecture/lifecycle/validate.md:21–24` — canonical validation table uses bare `ruff`/`mypy`/`pytest`
  - `agents/validation-standards.md:274,282` — example code shows `pip install ${name}` (advisory, but the advisory itself should prefer `uv pip install`)

  Inconsistency produces three costs: (a) users following different docs get different guidance; (b) bare invocations silently pick up the wrong Python when run outside the venv; (c) the framework fails to model the tooling standard it promotes.

  **Gap 2 — Agent catalog gap.** No agent in the catalog manages a project's `uv` environment lifecycle (create venv, sync, add/remove deps, recreate, diagnose drift). This is a missing capability for user projects — not just the plugin itself. Users who adopt the framework get no agent help for the very tooling the framework standardizes on.

- **Remediation plan:**

  **Sub-plan 1 (docs) — single branch, single commit.** Rewrite bare tool invocations to `uv run …` (or `uv pip install` for the pip examples) across the 6 files enumerated above. Scope is mechanical find-and-replace with light editorial judgement where surrounding prose needs tweaking. Confirm idempotence by re-running the uv-adoption grep at PR open: `rg -n "^\s*(ruff|mypy|pytest|pip install)" commands/ docs/ hooks/CLAUDE.md agents/validation-standards.md`. Each remaining hit should be a code block demonstrating a non-uv alternative deliberately, or a `uv run`-prefixed line.

  **Sub-plan 2 (agents) — separate branch, separate PR, waits on Phase 2 agent scaffolder.** Add three agents to the catalog, naming per PSF prefixes in `.claude/rules/agent-frontmatter.md`:
  - `operate-uv-env-initializer` — create or recreate a project venv, run `uv sync`, verify tool resolution. Tier: write (creates files in user project). Model: sonnet. Idempotent.
  - `operate-uv-dep-manager` — `uv add` / `uv remove` / `uv lock --upgrade` with validation that the venv still syncs and project tests still collect. Tier: write. Model: sonnet.
  - `maintain-uv-env-doctor` — diagnose drift between `pyproject.toml`, `uv.lock`, and the active venv (stale locks, unresolved deps, mismatched Python minor); propose repair plan without executing. Tier: reason (read-only diagnostic). Model: sonnet.

  These three agents need the `meta-agent-scaffolder` (Phase 2) to author cleanly — creating agents by hand before the scaffolder lands violates the bootstrap-first principle (`docs/architecture/principles/bootstrap-first.md`). Sub-plan 2 is therefore blocked on Phase 2 exit.

  **Decision — leave validation-tuple constants in `hooks/_hook_shared.py:51–62` unchanged.** The `PY_VALIDATION_STEPS` tuple uses symbolic step names (`"ruff-check"`, `"mypy-strict"`, etc.), not command strings. The orchestrator prefixes `uv run` at invocation time. Changing the constants to include `uv run` would conflate two concerns (step identity vs. invocation) and regress the abstraction. Noted here so this isn't relitigated in the sub-plan 1 PR.

- **Blocks:** nothing immediately (advisory, cross-cutting cleanup). Sub-plan 1 can ride alongside Phase C or Phase D work. Sub-plan 2 is blocked on Phase 2 agent scaffolder.

- **Status:** IN_PROGRESS (sub-plan 1 CLOSED in commit `9948f25` via PR #21; sub-plan 2 OPEN, **unblocked since Phase 1**, deferred to a future phase pending agent-catalog priorities)

## Sub-plan 1 resolution

Sub-plan 1 resolved in commit `9948f25` on `docs/tr-0002-uv-run-framework-outputs` (merged via PR #21, merge commit `fbe7a90`). All six files enumerated in Gap 1 now route Python tooling through `uv run` (or `uv pip install` for the agents/validation-standards.md advisory example):

- `commands/typecheck.md` — Python type-check, lint, fallback lint, and Ruff auto-fix all `uv run`-prefixed
- `commands/validate.md` — lint and test chains drop bare `pytest`/`python -m pytest` fallback, use `uv run pytest` / `uv run ruff check` / `uv run pylint`
- `docs/guides/getting-started.md` — schema verification steps use `uv run pytest` and `uv run python` instead of `.venv/Scripts/python.exe`
- `hooks/CLAUDE.md` — test invocation rewritten from `.venv/Scripts/python.exe -m pytest` to `uv run pytest`, and the preamble says "Run from the project root" instead of "Run from .venv"
- `docs/architecture/lifecycle/validate.md` — Python gate table shows `uv run ruff check`, `uv run ruff format --check`, `uv run mypy --strict`, `uv run pytest`
- `agents/validation-standards.md` — example code uses `uv pip install` in both the before-and-after rectifications

Verification: `rg -nE "^\s*(ruff|mypy|pytest|pylint|pip install)" commands/ docs/guides/ docs/architecture/lifecycle/validate.md agents/validation-standards.md` returns nothing outside `uv run`/`uv pip` contexts.

Sub-plan 2 (agents) remains **OPEN** but is **unblocked**. The original blocker — `meta-agent-scaffolder` — actually shipped in **Phase 1** (PR #31, merge commit `d1ddef3`), not Phase 2 as the original plan text claimed. Sub-plan 2 has been unblocked since Phase 1 close; building the three `operate-uv-*` / `maintain-uv-*` agents was not picked up during Phase 2 because the Phase 2 hook layer took priority. Defer to Phase 3+ pending agent-catalog priorities (sub-plan 2 sits adjacent to Phase 3's brownfield scanner work — they may share a planning pass).
