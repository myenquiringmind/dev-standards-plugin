# Getting Started

You're a new contributor to `dev-standards-plugin`. This guide gets you oriented and ready to make your first contribution.

## Prerequisites

- **Git** installed and configured with your identity
- **Python 3.13+** installed (the plugin's hooks and shared modules are Python)
- **uv** (Python package manager) — install from [docs.astral.sh/uv](https://docs.astral.sh/uv)
- **Node.js ≥18** (the plugin's existing `lib/` is JavaScript)
- **Claude Code** installed and working in your terminal or IDE

## 1. Clone the repo

```bash
git clone https://github.com/myenquiringmind/dev-standards-plugin.git
cd dev-standards-plugin
```

## 2. Set up the Python environment

```bash
uv venv .venv --python 3.13
uv sync --group dev
```

This creates a `.venv/` directory (gitignored) with all development dependencies: jsonschema, pytest, portalocker, ruff, mypy, hypothesis.

## 3. Verify the schemas

```bash
.venv/Scripts/python.exe -m pytest tests/schemas/   # when available
# Or for Phase 0 verification:
.venv/Scripts/python.exe tmp/verify-phase-0.py       # if the throwaway verifier exists
```

## 4. Set up Node.js (for the existing `lib/`)

```bash
npm install
```

## 5. Read the architecture orientation

Start with `CLAUDE.md` at the repo root. It tells you where everything is. Then read 3-4 of the principles in `docs/architecture/principles/`:

- **Start here:** `dogfooding.md` — the meta-principle
- **Then:** `psf.md` — where new logic lives
- **Then:** `bootstrap-first.md` — the sequencing principle
- **Then:** `stamps.md` — the mechanical enforcement model

Each file is <200 lines and takes a few minutes.

## 6. Understand the branching model

From Phase 1 exit onwards:

- **Never commit to `master` directly.** Branch protection blocks this.
- **Create a feature branch:** `git checkout -b feat/<category>-<slug> master`
- **Work on your feature.** The plugin's own hooks gate your work (lint, format, secret scan).
- **Run `/validate`** to get a stamp.
- **Commit.** The pre-commit gate checks the stamp. Without a valid stamp, commit is blocked.
- **Open a PR** against `master`. The PR is reviewed by the framework's own agents.
- **Merge.** The feature branch is deleted after merge.

For parallel work, use worktrees:

```bash
git worktree add C:/Users/<you>/Projects/dsp-worktrees/feat-<slug> -b feat/<slug> master
```

See `@docs/architecture/principles/bootstrap-first.md` §"Worktree discipline" for the full workflow.

## 7. Understand what you can and cannot do (pre-bootstrap)

If Phase 1 is not yet complete (the bootstrap isn't live), commits are pre-bootstrap and exempt from the gate. You can commit freely. Once Phase 1 exits, every commit is gated.

To check if the bootstrap is live: look for `hooks/pre_commit_cli_gate.py`. If it exists and is registered in `hooks/hooks.json`, the gate is live.

## 8. Understand the documentation hierarchy

All documentation lives in `docs/` following the Diataxis taxonomy:

| You want to... | Go to... |
|---|---|
| Understand a concept | `docs/architecture/principles/` |
| See the implementation roadmap | `docs/phases/` |
| Understand a past decision | `docs/decision-records/` |
| Do a specific task | `docs/guides/` (you're here) |
| Find a component's spec | `docs/architecture/components/` (populated as components land) |

Every doc file is ≤200 lines (enforced by `hooks/post_edit_doc_size.py` from Phase 1 exit).

## 9. Your first contribution

The most useful first contribution depends on the current phase:

- **Phase 0 (architecture lockdown):** review the principles in `docs/architecture/principles/` for clarity, accuracy, and completeness. Propose edits via PR.
- **Phase 1 (bootstrap):** pick a `feat/bootstrap-*` branch that interests you. Implement the specified hook, agent, or shared module. See `docs/phases/phase-1-bootstrap.md` for the scope contract.
- **Phase 2+:** use `/new-agent` or `/new-hook` to scaffold a new component. The scaffolder enforces frontmatter, naming, and graph registry updates.

## 10. Where to get help

- Architecture questions → `docs/architecture/principles/`
- Phase-specific questions → `docs/phases/phase-N-*.md`
- Decision history → `docs/decision-records/`
- The canonical planning session → `docs/decision-records/v2-architecture-planning-session.md` (long; use search)

For issues or bugs, file a GitHub issue on the repo. For discussion, use the repo's discussion tab (once enabled).

## What to read next

- `@docs/architecture/principles/dogfooding.md` — why the framework builds itself
- `@docs/phases/phase-1-bootstrap.md` — the bootstrap contract (if you're contributing to Phase 1)
- `@docs/architecture/principles/rrw-tiering.md` — how agents are specialized (relevant once you're building agents)
