# Todo Registry

This directory is the project's **persistent, git-tracked ledger of deferred work**. It is the tier-3 destination in the [graduated response schema](../../.claude/rules/stewardship-ratchet.md) — the place where non-trivial deferrals go so they are not lost across sessions.

## Why this exists

The Competence Ratchet principle says: when an agent identifies a deficiency, that deficiency transitions from unconscious to conscious incompetence and cannot be overlooked. But not every identified issue can be fixed in the current session — some require investigation, cross-cutting changes, or scope expansion. Those deferrals need a durable, auditable home.

The registry provides that home. Every entry records *what* was identified, *when*, *by whom* (which commit surfaced it), *what tier* of response was chosen, and *what remediation plan* applies.

This registry lives in `docs/` (project tier, git-tracked, public) rather than in memory (session tier, private) because the plugin is public and deferred work is part of the contract with users.

## Layout

One file per entry, named `TR-NNNN-<kebab-case-slug>.md`. TR-IDs are monotonically assigned — if the highest existing ID is TR-0042, the next new entry is TR-0043, whether or not earlier IDs are CLOSED.

The index is this README's `## Open` and `## Recently closed` sections. Keep them current — agents check the index to find work to pick up.

## Entry schema

Every file starts with this exact structure:

```markdown
# TR-NNNN: <one-line summary>

- **Discovered:** YYYY-MM-DD, commit <hash> (context — which objective surfaced this)
- **Tier:** <1|2|3|4> (and any tier override with reason)
- **Description:** what's broken, where, why it matters
- **Remediation plan:** concrete path to resolution
- **Blocks:** list of work blocked by this, or "none (advisory)"
- **Status:** OPEN | IN_PROGRESS | CLOSED (commit/PR reference)
```

Entry files are ≤200 lines per `docs/` size discipline. If an entry needs more context than fits, it's probably a tier-4 escalation, not a tier-3 deferral.

## Lifecycle

1. **Creation.** An agent encountering a tier-3 issue adds a new file here with `Status: OPEN`, and adds an `## Open` line to this README.
2. **Claim.** When an agent starts work on an open entry, they update its status to `IN_PROGRESS` and note the branch/session.
3. **Close.** When the fix commit lands, the agent updates the entry's status to `CLOSED` with the commit hash (or PR number once merged), and moves the README line from `## Open` to `## Recently closed`.
4. **Archive.** When `## Recently closed` exceeds ~10 entries, the oldest closed entries are trimmed from this index (the files remain — they stay as a permanent audit trail).

Closed entries are never deleted. They document the evolution of the codebase.

## Commit convention for registry changes

PRs or commits that close a TR must reference its ID in the footer, mirroring how GitHub issues are referenced:

```
Closes: TR-0042
```

A future hook (Phase D or later) will validate: no PR merges with unresolved blocking TRs.

## Index

### Open

- [TR-0002](TR-0002-standardize-uv-across-framework-outputs.md) — standardize `uv run` across framework outputs and add uv-env management agents (`operate-uv-env-initializer`, `operate-uv-dep-manager`, `maintain-uv-env-doctor`)

### Recently closed

- [TR-0001](TR-0001-repair-mypy-strict-errors-in-os-safe-tests.md) — mypy --strict errors in `hooks/tests/test__os_safe.py` (closed by commit `cd58b86` on `feat/phase-0b-shared-modules`)
