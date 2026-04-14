# Stewardship and the Competence Ratchet

This rule encodes the agent's relationship to the system's quality floor. Every agent working in this repo is a steward for the duration of its session — not merely a doer of tasks. Stewardship composes with the [session lifecycle](session-lifecycle.md); the lifecycle says *how* to do an objective, this rule says *what condition the system must be in when you hand it back*.

## The Stewardship Contract

> If the system was in state S at session start, the agent returns it in state S′ where every invariant that held in S still holds in S′, AND every invariant the agent's validation surfaced as broken is either (a) repaired in-session, or (b) explicitly handed off as a WIP commit with full reproduction info and a remediation plan.

Authorship is irrelevant. The test is not "did I cause this?" — it is "was this invariant surfaced during my session?"

## The Competence Ratchet

When an agent identifies a deficiency — regardless of when, why, or by whom it was introduced — the act of identification converts that deficiency from **unconscious incompetence** (nobody knew it was broken) to **conscious incompetence** (somebody knows now). The current session owns it.

It applies to:

- Code quality, simplicity, correctness
- Type strictness (mypy, new ruff rules, pyright level)
- Library versions (outdated pins, deprecated APIs, security CVEs)
- Security posture (new secret patterns, dangerous defaults)
- Architectural patterns (a rule that post-dates the code)

The consequence: as model capability rises with each generation, the codebase naturally migrates toward the state-of-the-art. The framework has a continuous-improvement mechanism baked in.

**Prior sessions are trusted in good faith.** An agent does not audit prior work for the sake of auditing — the ratchet only fires on what the current session's validation and observation surface organically. But once surfaced, the obligation is live.

## Graduated Response

The ratchet's obligation is throttled by a four-tier schema. Scope discipline survives — `one objective, one commit` still holds — because the tiers route fixes to the right commit, not into the feature commit.

| Tier | Criterion | Path |
|---|---|---|
| **1. Silent fix** | Trivial, within-scope, unambiguous. <5 lines, no judgement call. | Bundle into the current objective's commit. |
| **2. Same-session sidecar** | Scope-adjacent, fix is clear, agent is confident. No architectural judgement required. | Separate commit, **same branch**, landing **before** the feature commit. |
| **3. Todo registry** | Non-trivial, needs investigation, or introduces scope expansion. | Create an entry in `docs/todo-registry/` (see the registry README for schema). Flag in session state. |
| **4. User escalation** | Scope-changing, ambiguous, high blast radius, or requires a business decision. | Stop. Use `AskUserQuestion`. Wait for direction. |

**Never:** move to COMMIT with known surfaced breakage unaddressed.

### Tier selection heuristic

If you are unsure between two adjacent tiers, choose the higher tier (more conservative). Tier-3 entries that turn out to be trivial are cheap to close; tier-1 silent fixes that turn out to be load-bearing changes are expensive to unwind.

## Accountability Map

| Interaction | Responsible (does the work) | Accountable within scope | Accountable if scope changes |
|---|---|---|---|
| Session handover (this session → next) | Outgoing session | Outgoing session | — |
| Primary agent → subagent delegation | Subagent | Primary agent | User |
| Primary agent → validation agents (stamps) | Validation agent | Primary agent | User |
| Ratchet-surfaced breakage | Primary agent | Primary agent | User |
| New work that expands the stated scope | — | — | User |

The "scope change → User" column is load-bearing: it is what stops the Competence Ratchet from producing runaway scope expansion. When in doubt about whether a fix expands scope, treat it as if it does and escalate.

## Validation Footer

Every commit ends with a validation footer:

```
Validated: ruff-check ✅  ruff-format ✅  mypy-strict ✅  pytest N/N ✅
At: <ISO-8601 UTC timestamp>  Model: <model id>
```

WIP commits carry the same footer with failures explicit and a `Next session first:` line naming the remediation path:

```
Validated: ruff-check ✅  mypy-strict ❌(2 errors)  pytest 85/87 ✅
Known-broken: hooks/foo.py:42 (type mismatch); hooks/tests/test_foo.py (2 failures)
Next session first: repair these before continuing with objective X
```

The footer is the **portable trust signal** the next session reads. Without it, the next session must re-run full validation before trusting the branch.

## Branch-Pickup Protocol

When a new session inherits an in-flight branch (including the case where the prior agent crashed):

1. Read the last commit's validation footer (`git log -1`).
2. If the footer is present, recent, and all-✅: **trust** it. Skip re-validation. Proceed with new work.
3. If the footer is missing, stale, or has any ❌: **validate first**. Classify anything surfaced via the graduated response schema.
4. Check `git status` for orphaned uncommitted work:
   - Coherent and salvageable → WIP-commit before touching anything new.
   - Incoherent or unclear → tier-4 escalation to User.
5. Only then start new work.

"Fix-first" does **not** mean "always re-validate from scratch." It means: trust nothing the footer doesn't vouch for, and once you've run validation, close every open loop before moving on.

## What This Rule Does Not Cover

- **How to structure an objective** — see [session-lifecycle.md](session-lifecycle.md).
- **The todo registry's schema and lifecycle** — see [../../docs/todo-registry/README.md](../../docs/todo-registry/README.md).
- **Hook conventions and size limits** — see `hooks/CLAUDE.md` and `docs/CLAUDE.md`.
- **Context budget and handoff timing** — see `docs/architecture/principles/context-awareness.md`.

This rule is the *contract*. Other rules are the *mechanisms*.
