# Phase 0b — Exit Report

Phase 0b delivered the self-hosting bootstrap for the `dev-standards-plugin`: rules, shared Python modules, language profiles, twelve lifecycle hooks, and the `hooks.json` shim that wires them into Claude Code. This report records the gate results and the carry-forward work.

## What shipped

| Sub-phase | Deliverables | PR |
|---|---|---|
| A — Rules | 5 rules (`session-lifecycle`, `anti-rationalization`, `hook-development`, `agent-frontmatter`, `security-internal`) | #11 |
| A′ — Stewardship | `stewardship-ratchet.md` + ADR-007 + multi-branch-coordination guide + todo-registry bootstrap | #10 |
| B — Shared modules | `_os_safe.py`, `_hook_shared.py`, `_session_state_common.py` | #9 |
| C — Language profiles | `config/profiles/python.json`, `config/profiles/javascript.json` | #14 |
| D1 — Session boundary hooks | `session_start`, `session_end`, `pre_compact`, `post_compact` | #15 |
| D2 — Prompt-time hooks | `create_feature_branch`, `context_budget` | #16 |
| D3 — Pre-write guards | `branch_protection`, `pre_write_secret_scan`, `dangerous_command_block` | #17 |
| D4 — Post-write feedback | `post_edit_lint`, `post_auto_format` + `_profiles` shared module | #18 |
| D5 — Failure logging | `post_tool_failure` | #19 |
| D6 — hooks.json shim | v1.4 node → v2.0 Python shim (12 hooks registered) | #20 |
| Sidecars | Branch-pickup merge-commit clarification (#12), TR-0002 registry entry (#13), `$schema` meta-key on profile schema (#14), `SessionEnd`/`PostCompact` on hooks schema (#20), TR-0002 sub-plan 1 docs cleanup (#21) | — |

Twenty-one PRs landed across this phase.

## Mechanical gate results

Every gate in the original Phase 0b exit checklist was run from master HEAD. Results:

| # | Gate | Command | Result |
|---|---|---|---|
| E1 | `_os_safe.py` tests | `uv run pytest hooks/tests/test__os_safe.py` | ✅ 27/27 |
| E2 | `_hook_shared.py` tests | `uv run pytest hooks/tests/test__hook_shared.py` | ✅ 30/30 |
| E3 | `_session_state_common.py` tests | `uv run pytest hooks/tests/test__session_state_common.py` | ✅ 30/30 |
| E4a | `hooks.json` schema validity | `jsonschema Draft7Validator` against `schemas/hooks.schema.json` | ✅ |
| E4b | 12 hooks registered | Extracted from `hooks.json` command strings | ✅ exactly 12 |
| E9 | Rules in `.claude/rules/` | `ls .claude/rules/` | ✅ 6 (see note) |
| E10 | Full hook test suite | `uv run pytest hooks/tests/` | ✅ 250/250 |
| E11 | PRs merged to master | 21 PRs across the phase | ✅ |

**Note on E9:** the original plan asked for 5 rule files; we have 6. The +1 is `stewardship-ratchet.md`, added mid-phase as the formalisation of the Competence Ratchet and graduated-response schema. This was an intentional in-phase scope expansion — recorded here rather than hidden as a deviation.

## Integration gates — pending CC reload

Gates E5–E8 test the live hook wiring. The CC session that built Phase 0b was started with the v1.4 `hooks.json` already loaded, so the new Python shim does not take effect until CC is restarted against this master. These require manual verification by the user after reload:

| # | Gate | Manual test |
|---|---|---|
| E5 | Editing a `.py` file triggers lint + format | Edit any `.py` file on a feature branch; stderr should show `[post_edit_lint]` / `[post_auto_format]` output from the new hooks (not the legacy v1.4 node wrappers). |
| E6 | Edit on `master` blocked | On `master`, attempt `Edit` or `Write` via the CC tool; expect exit 2 with `[branch_protection] refusing Edit on protected branch 'master'`. |
| E7 | Secret pattern blocked | Write a file containing `AKIAIOSFODNN7EXAMPLE` (fake AWS key); expect exit 2 with `[secret_scan] refusing Write — detected AWS access key ID pattern`. |
| E8 | `session_start` restores prior state | Write a file to `<memory>/session-state.md`, start a new session, confirm the preamble "Resuming work from the prior session" appears as `additionalContext` and the file is renamed to `session-state.md.injected`. |

The test procedure for each is repeatable and auditable. Results from the user's first post-reload session should be logged back into this report (append a `## Live verification` section with dates and pass/fail per gate).

## Carried forward

### Open registry entries

- **TR-0002 (IN_PROGRESS)** — sub-plan 1 (docs cleanup) landed via PR #21. Sub-plan 2 (env-management agents `operate-uv-env-initializer`, `operate-uv-dep-manager`, `maintain-uv-env-doctor`) remains OPEN, blocked on the Phase 2 `meta-agent-scaffolder`.

### Deferrals flagged for Phase 1

- **Uncommitted-changes-on-Stop guard.** The v1.4 `hooks.json` blocked session termination when the tree was dirty. D6 dropped this along with the rest of the node-inline hooks; the discipline is worth re-adding as a Python hook in Phase 1 once `session_checkpoint.py` lands. Not tier-3 registered because Phase 1 is the natural home.
- **`statusline.py` + `.context_pct` cache.** `context_budget.py` was written to consume this cache but the producer does not yet exist. In Phase 0b the hook exits 0 silently when the cache is absent; in Phase 1 the producer lands and the advisory-plus-hard-cut becomes live without any config flip.

### Known-good carry-forward

- Every hook commit carries a validation footer. The branch-pickup protocol (`git log --no-merges -1 --format=%B | tail -5`) resolves the footer on master even when HEAD is a merge commit. Verified live at each Phase D merge.

## What Phase 1 inherits

- A bootstrap that can validate itself: the pre-commit gate, stamp writers, and telemetry pipeline can now be built on top of `_os_safe`, `_hook_shared`, and `_session_state_common` rather than re-deriving them.
- A feature-branch discipline enforced at both the rule layer (`session-lifecycle.md`) and the hook layer (`branch_protection.py`).
- A persistent error log (`<memory>/error-log.md`) that will let Phase 1 agents triage historical failures without re-scraping transcripts.
- A registry of deferred work (`docs/todo-registry/`) the next phase can continue to grow.

## Exit declaration

All mechanical gates pass on master `fbe7a90` (the commit before this report; the report merge itself will advance master to a new tip). Integration gates E5–E8 require a CC reload and are the user's first post-reload verification task. With those confirmed, **Phase 0b exits and Phase 1 may begin**.
