# Multi-Branch Coordination

How-to for agents (and humans) working across multiple interlocking branches. Architectural rationale lives in [ADR-007](../decision-records/adr-007-git-as-ground-truth-and-multi-branch-coordination.md); behavioral rule in [`stewardship-ratchet.md`](../../.claude/rules/stewardship-ratchet.md). This guide is the practical step-by-step.

## When to use multi-branch

Use multi-branch when work naturally splits into **independent PRs with cross-references** — the archetypal case is a feature that requires changes in code, docs, and rules that would otherwise bloat a single PR beyond reviewability. Don't use multi-branch for work that fits comfortably on one branch.

Signals that multi-branch is warranted:

- Changes span multiple architectural layers (code + docs + rules)
- Different review domains (runtime code vs. prose)
- Cross-references would be cleaner as commits than as single-branch history
- Reviewers benefit from seeing the pieces in isolation

Signals that single-branch is enough:

- One commit does the job
- Changes are tightly coupled and cannot be understood separately
- No meaningful cross-references

## Before cutting a branch

Base-branch is a deliberate choice, not a default. Run `gh pr list` first. For each open PR that touches files you will touch, decide:

- **Rebase off it** if your work depends on its content (cross-reference DAG; see below).
- **Wait for it to land** if you can — the smallest delta to master is always cheapest.
- **Cut from master and accept rebase-on-merge** if the work is semantically independent (the contention is purely textual — see [Implicit shared-resource contention](#implicit-shared-resource-contention)).

State the chosen base in the PR description if it is not `master`.

## Worktree setup

**Convention:** sibling directories to the main repo, named `<repo>.<slug>`. Example:

```
C:/Users/jmarks01/Projects/
├── dev-standards-plugin/                       (master)
├── dev-standards-plugin.shared-modules/        (feat/phase-0b-shared-modules)
├── dev-standards-plugin.stewardship/           (feat/phase-0b-stewardship)
└── dev-standards-plugin.rules/                 (feat/phase-0b-rules)
```

Create a worktree:

```bash
git worktree add ../dev-standards-plugin.<slug> -b feat/<slug> master
cd ../dev-standards-plugin.<slug>
```

Remove a merged worktree:

```bash
git worktree remove ../dev-standards-plugin.<slug>
git branch -d feat/<slug>
```

**Why sibling directories:** session memory slugs naturally disambiguate on absolute path, so each worktree has its own memory dir. No manual per-worktree configuration.

**Windows note:** paths must use forward slashes in commands (not backslashes). Worktrees + antivirus + long paths occasionally stumble — if `git worktree add` reports a permission error, retry once.

## Validation footer

Every commit ends with this block (see [ADR-007](../decision-records/adr-007-git-as-ground-truth-and-multi-branch-coordination.md)):

```
Validated: ruff-check ✅  ruff-format ✅  mypy-strict ✅  pytest N/N ✅
At: <ISO-8601 UTC timestamp>  Model: <model id>
```

**Generating the timestamp:**

```bash
TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
```

**WIP variant** — failures explicit, next-action line required:

```
Validated: ruff-check ✅  mypy-strict ❌(2 errors)  pytest 85/87 ✅
Known-broken: hooks/foo.py:42 (type mismatch); hooks/tests/test_foo.py (2 failures)
Next session first: repair before continuing objective X
```

The footer is consumed by the **branch-pickup protocol** below. Inconsistent or missing footers force the next agent to re-run validation from scratch.

## Branch-pickup protocol

When a session inherits an in-flight branch (new session, agent crash, human handoff):

1. `git log -1 --format=%B` — read the last commit's footer.
   - **If HEAD is a merge commit** (e.g. GitHub's `Merge pull request …`), the merge commit does not carry the footer — it lives on the last non-merge ancestor. Read that instead:
     ```bash
     git log --no-merges -1 --format=%B | tail -5
     ```
     `--no-merges -1` is preferred over `--first-parent -1` because criss-cross merges can leave the first-parent pointing at a stale footer; `--no-merges` always returns the most recent commit that *could* carry one.
2. **Footer present, recent, all ✅** → trust, skip revalidation, proceed with new work.
3. **Footer missing, stale, or has any ❌** → run full module-scope validation first. Classify surfaced issues via graduated response in `stewardship-ratchet.md`.
4. `git status` — if orphaned uncommitted work exists:
   - Coherent + salvageable → WIP-commit **before** touching anything new.
   - Incoherent or unclear → tier-4 escalation to user.
5. Only then start new work.

## Cross-references between branches

When a commit on one branch references a commit on another, name the branch and hash explicitly in the commit message. Example:

```
docs(todo-registry): bootstrap the persistent deferred-work ledger

First entry TR-0001 is CLOSED — it records the B3 mypy-strict debt
and the sidecar fix (commit cd58b86 on feat/phase-0b-shared-modules).
```

When a PR body needs to reference another PR that isn't yet merged, use `#<NNN>` for PRs in the same repo, or a full URL for external.

Every TR close must reference the commit that closed it:

```
Closes: TR-0001
```

## PR body template

PR bodies must be **regenerable from git state**. The template:

```markdown
## Summary

<1–3 bullets: what this branch delivers, at what layer of the stack>

## TRs touched

- <TR-ID>: <status at PR open> — <short description>

## Cross-branch dependencies

- <related branch name> (PR #NNN if open) — <one-line relationship>

## Validation footer from HEAD

```
<paste the footer from git log -1>
```

## Test plan

- [ ] <manual check 1>
- [ ] <manual check 2>
```

A future coordinator agent will generate this from `git log`, the registry, and local state alone — no hand-written context required.

## Merge order from cross-references

When multiple PRs ship together, merge order follows the cross-reference DAG:

1. Branch that **produces** a referenced artifact merges first.
2. Branch that **documents** the artifact merges after.
3. Branch that **references** a documented artifact merges last.

For the Phase 0b triangle:

```
shared-modules  (produces commit cd58b86 / TR-0001 fix)
      ↓
stewardship     (documents the fix in the registry)
      ↓
rules           (references both — stewardship-ratchet.md cites the registry;
                 session-lifecycle.md cites stewardship-ratchet.md)
```

Merge order: shared-modules → stewardship → rules.

If the DAG is ambiguous (two branches mutually reference each other), that is a tier-4 escalation — it probably should have been one branch.

## Implicit shared-resource contention

Some files are merge-fragile: every change targets the same insertion neighborhood — top-level keys in JSON registries, ordered tuples, alphabetical lookup tables. `hooks/hooks.json` and `config/graph-registry.json` are live examples. Two PRs adding different entries are *semantically independent* but *textually contend* on the same anchor lines, and conflict resolution can silently drop one side.

Discipline:

- **Declare contention in the PR body** under "Cross-branch dependencies": "touches `hooks.json` alongside #N." Reviewers then sequence merges deliberately.
- **Default to FIFO merge order.** Oldest open first; each merge gives the next a fresh base, and rebasing the next surfaces conflicts at the author's desk where they have full context.
- **Audit after merge.** Run a short shell check on shared registries (e.g., every `hooks/*.py` registered in `hooks.json`?) — catches dropped registrations within minutes rather than at the next event-fire.
- **Genuinely unavoidable**: two PRs editing the same array (e.g., extending `PostToolUse Edit|Write|MultiEdit`). No convention fixes this — the array is the contended resource. Sequence by hand.

## TR discipline through the PR lifecycle

- A PR that creates a TR leaves the TR status as `OPEN` in the same commit that introduces it.
- A PR that closes a TR updates the TR file's status to `CLOSED` with the closing commit's SHA, and moves the TR from the registry README's `## Open` section to `## Recently closed`.
- A PR must not merge with any blocking `OPEN` TRs that cite it as the intended closer — the registry's future enforcement hook (Phase D) will check this. Discipline-enforced until then.

## What this guide does not cover

- **When to write an ADR vs a rule vs a guide** — see `@docs/decision-records/README.md`.
- **Hook conventions (Phase D enforcement of footers)** — see `@hooks/CLAUDE.md`.
- **The graduated response schema** — see `@.claude/rules/stewardship-ratchet.md`.
- **Stamp validation (session-scoped complement to footers)** — see `@docs/architecture/principles/stamps.md`.
