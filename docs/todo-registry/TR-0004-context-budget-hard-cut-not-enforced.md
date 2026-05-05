# TR-0004: context-budget hard cut is principle-only — three concrete bugs prevent enforcement

- **Discovered:** 2026-05-05, session compaction event during PR #94 work (commit 9a2032a master, branch `feat/phase-4-graph-history`).
- **Tier:** 3 (multi-component fix; touches `hooks/statusline.py`, `hooks/_hook_shared.py`, `hooks/context_budget.py`, and rules; no single sidecar can land it cleanly).
- **Description:**
  The principle document `docs/architecture/principles/context-awareness.md` declares: *"Compaction is forbidden. `/handoff` is forced before CC compaction fires. The framework hard cut is 75% of the compaction threshold (~62% of the active model's window)."* That principle is not enforced. The session that surfaced this TR ran past the dynamic cut, into CC's auto-compaction, in violation of `CLAUDE.md`'s "Never enter compaction" rule. Three concrete bugs combine to make the principle inert:

  1. **Cache file never written.** `.claude/.context_pct` is the source of truth `context_budget.py` reads via `read_cached_pct()`. In the failing session's working tree, the file did not exist. `statusline.py` is wired in `hooks.json` and is supposed to write it, but evidently does not (under this CC version, or under this working tree, or under this auth flow — root cause unconfirmed). When the cache is absent, `read_cached_pct()` returns `None` and `context_budget.py` exits 0 silently — the hook is structurally fail-open.

  2. **Threshold contradicts the principle.** `hooks/_hook_shared.py` declares `CRITICAL_CONTEXT_PCT = 95` and `WARN_CONTEXT_PCT = 80`. The principle says the hard cut should be `compute_hard_cut() == 75% of compaction threshold == ~62% of window`. CC auto-compacts at ~83.5% of the window. A 95% critical threshold therefore *cannot* fire before compaction even if the cache existed — by the time pct == 95, compaction has already happened. The constant is wrong by definition relative to the principle.

  3. **Hook ignores its own primitive.** `hooks/_hook_shared.py:compute_hard_cut()` exists — the principle's canonical conversion from "model window" to "hard cut tokens." But `hooks/context_budget.py` does not call it. The hook compares percentages against `CRITICAL_CONTEXT_PCT` instead, side-stepping the model-aware cut. The principle's primitive was built and shipped; the consumer was never wired up.

  **Doc-side gap:** `.claude/rules/session-lifecycle.md` "Handoff Protocol" lists four steps (commit, update memory, note branch/hash, list next objective). It does not require `/clear`. Without `/clear`, an agent that "handed off" stays in the same compacting context, hits the same threshold within the same session, and re-enters the failure mode — exactly what produced this incident.

- **Remediation plan:**
  1. **Doc fix (this PR):** add a "5. Issue `/clear`" step to `session-lifecycle.md` Handoff Protocol; add a paragraph to `context-awareness.md` naming `/clear` as the close-out of the handoff sequence.
  2. **Threshold fix (separate PR):** lower `CRITICAL_CONTEXT_PCT` to a value that fires *before* CC's ~83.5% compaction, derived from `compute_hard_cut()` rather than a percentage constant. Likely shape: introduce `compute_hard_cut_pct(model_window) -> int` and use it in `context_budget.py`. Update `WARN_CONTEXT_PCT` to leave the planner a few-turn cushion before the cut.
  3. **Cache-population fix (separate PR):** confirm whether `statusline.py` is firing and writing `.claude/.context_pct` under current CC. If not, diagnose. If `statusline` is unreliable, add a fallback path: emit `.context_pct` from `session_checkpoint.py` (PostToolUse) or `instructions_loaded.py` (SessionStart) so the cache exists from turn 1. A fail-open hook on a missing cache file is a silent safety regression — it should be at least advisory (warn that monitoring is offline).
  4. **Test coverage:** add `hooks/tests/test_context_budget.py` cases for: cache missing → advisory stderr, not silent; cache at warn → advisory; cache at hard cut → exit 2; integration with `compute_hard_cut()`.
  5. **Audit pass:** grep for other principle-document claims that have no enforcing code. The same pattern (principle says X, hook is silent fail-open under common conditions) likely repeats elsewhere.
- **Blocks:** none directly, but every long-running session is at risk of repeating this incident until step 2 + 3 land. Mark advisory-but-urgent.
- **Status:** OPEN (this PR ships step 1 only — the doc fix; steps 2-5 are deferred to separate PRs).
