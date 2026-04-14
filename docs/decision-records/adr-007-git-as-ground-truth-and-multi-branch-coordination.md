# ADR-007: Git as Ground Truth and Multi-Branch Coordination

**Status:** Accepted
**Date:** 2026-04-14
**Deciders:** Planning session (post-B3 reflection)

## Context

Three existing principles imply — but do not state — that git is the framework's sole source of truth for state:

- `stamps.md` — validation stamps carry `branch` and `plugin_commit` fields; branch switch invalidates the stamp; commits are gated on stamp freshness. The stamp's *reason for existing* is that git is authoritative.
- `bootstrap-first.md` — from Phase 2, every commit passes through the framework's own gate; worktree discipline applies; the installed plugin is the known-good master copy. The *process itself* assumes git is authoritative.
- `dogfooding.md` — the framework's own construction passes through its own gates. That guarantee collapses the moment state lives outside git.

Phase 0b exposed the gap. A single objective ("encode stewardship + Competence Ratchet") produced three interlocking branches with cross-references:

- `feat/phase-0b-shared-modules` (hooks + TR-0001 fix)
- `feat/phase-0b-stewardship` (todo registry referencing the fix commit)
- `feat/phase-0b-rules` (rule referencing the registry and the fix)

Coordination between them was **ad-hoc**: manual checkouts, manually-composed PR bodies, merge order derived by mental simulation. No deterministic mechanism existed for reading the branches' state, computing their dependency graph, or producing PR artifacts that can be regenerated from git alone.

User requirement: "a clear deterministic way of managing our git interface so that we do not find ourselves in ambiguous territory."

## Decision

Make **Git as Ground Truth** explicit, and define the deterministic coordination protocol that follows from it. Four interlocking commitments:

### 1. Git is the sole source of truth for state

- If it's not in a commit, a ref, a branch, or a tracked file, it does not exist from the framework's perspective.
- Session memory, conversation state, transient analysis are **derivative**. Useful, never authoritative.
- Anything the framework needs to survive a crash, a `/clear`, or an agent handoff must land in git before the session ends.

### 2. Validation footer on every commit

Every commit ends with a footer that records the validation state at the moment the commit was created:

```
Validated: ruff-check ✅  ruff-format ✅  mypy-strict ✅  pytest N/N ✅
At: <ISO-8601 UTC timestamp>  Model: <model id>
```

WIP commits carry the same footer with failures explicit and a `Next session first:` line.

Footers and stamps complement each other: stamps are **session-scoped** (15-min TTL, gate commit creation); footers are **commit-scoped** (permanent, inform future sessions). Same signal, different time horizons.

### 3. Branch-pickup protocol

A session inheriting an in-flight branch reads the last commit's footer to decide whether to trust validation or re-run it. Full protocol lives in [`stewardship-ratchet.md`](../../.claude/rules/stewardship-ratchet.md); the how-to for applying it sits in [`docs/guides/multi-branch-coordination.md`](../guides/multi-branch-coordination.md).

### 4. Multi-branch coordination via cross-references

When work naturally splits into multiple interlocking PRs:

- **One worktree per concurrent branch** — see the guide for naming convention.
- **Cross-references land in commit messages and PR bodies**, not external trackers.
- **Merge order is derivable** from the cross-reference graph — no human ordering required.
- **Every TR in `docs/todo-registry/` referenced by a PR is either CLOSED or explicitly not-blocking** before merge.
- **PR bodies are regenerable from git state** — the coordinator (human or, later, agent) can rebuild them without external inputs.

## Consequences

**Becomes required:**

- Every commit has a validation footer. Enforced by discipline now; by `hooks/pre_commit_validation_footer.py` in Phase D; by `pre-commit` framework at the git-layer in Phase 1+.
- Every branch targeted at master gets a PR whose body references the relevant TRs and cross-branches.
- Worktrees are the standard substrate for concurrent branch work (from Phase 2 onwards; the principle is codified now so Phase 0b–Phase 1 work inherits the convention even without enforcement).

**Becomes easier:**

- Agent handoff: the next session reads `git log -1` and knows the trust state.
- PR review: reviewers see the validation footer inline, not buried in CI logs.
- Recovery: every branch tells its own story via footer + commit messages, regardless of session memory.
- Deferred work audit: `docs/todo-registry/` + commit references form a complete audit trail.

**Becomes harder:**

- Commits without footers are non-conformant. Retrofitting old commits is out of scope — footers apply from this ADR forward.
- Agents that try to carry state in memory or conversation (rather than committing it) violate the stance.
- `--no-verify` and other bypass mechanisms must be deliberately designed against. Stamps already handle this via the CC PreToolUse hook layer; the validation-footer hook will mirror the pattern.

**Stays the same:**

- Stamp model (`stamps.md`) is unchanged — stamps remain session-scoped, footers are the commit-scoped complement.
- PSF is unchanged — the enforcement mechanisms graduate through the primitives (Rule → Hook) as the bootstrap matures.
- Phase boundaries are unchanged — the principle lands in Phase 0b but is enforced incrementally.

## Alternatives considered

- **New architectural principle (`git-as-truth.md`).** Rejected — the principles README caps the set at ten and requires an ADR explaining why the existing ones are insufficient. Stamps + bootstrap-first + dogfooding already imply the stance; this ADR formalizes it without inflating the principle count.
- **Ad-hoc coordination, no ADR.** Rejected — Phase 0b proved the ambiguity is real and will recur every time work spans branches. Without explicit determinism we waste tokens on re-derivation and risk divergent conventions.
- **Build a full PR coordination agent now.** Rejected — that's Phase 1+ work (judgment layer). The rule and convention land first; the agent reads them later.

## References

- `@docs/architecture/principles/stamps.md` — session-scoped validation, complementary to footers
- `@docs/architecture/principles/bootstrap-first.md` — worktree discipline (pre-existing)
- `@docs/architecture/principles/dogfooding.md` — the stance this ADR formalizes
- `@.claude/rules/stewardship-ratchet.md` — behavioral rule (branch-pickup protocol, footer convention)
- `@docs/guides/multi-branch-coordination.md` — practical how-to
- `@docs/todo-registry/README.md` — deferred-work ledger that this ADR makes load-bearing
