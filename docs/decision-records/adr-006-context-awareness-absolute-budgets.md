# ADR-006: Context Awareness with Guideline Budgets

**Status:** Accepted
**Date:** 2026-04-11
**Deciders:** Planning session (Appendix H amendment)

## Context

Large language models have a U-shaped attention curve: strong at the beginning and end of context, weak in the middle. This is the "lost in the middle" (LITM) phenomenon. Anthropic's expansion of Opus 4.6 to 1M tokens does not help — it makes LITM worse by widening the middle where attention fails.

Relative thresholds (70% / 85% / 95% of the model's max context) are the wrong primitive: if the model's max changes unilaterally, relative thresholds silently become useless. "95% of 1M" is 950K tokens — LITM-guaranteed failure.

The user challenged: "the assumption here is that we should be breaking all projects into small bite sized chunks... perhaps they can be guideline values, but they are not hard constraints are they?"

## Decision

**One hard constraint: never enter Claude Code's auto-compaction zone.** Compaction is guaranteed context loss. The framework forces `/handoff` at 75% of the compaction threshold (~62% of the active model's window) — a dynamic cut computed at session start by `hooks/_hook_shared.compute_hard_cut()`.

**Everything else is a guideline, not an enforced limit.** Token budgets (40K comfort, 60K soft warn, 80K attention ceiling) inform `meta-session-planner`'s task-sizing logic. They do not produce exit-2 blocks. The planner decomposes large tasks into bite-sized chunks aligned with git-commit boundaries.

The principle: **as small as possible, as large as necessary, smaller is always preferable.**

## Consequences

- **The only mechanically enforced limit is the dynamic hard cut.** `context_budget.py` exits 2 when the session reaches the cut; the user must run `/handoff`.
- **Guidelines are inputs to the session planner**, not hooks. The planner uses them to recommend decomposition but does not block work that exceeds a guideline.
- **Git-commit discipline** is the corrective: if a session produces more than one commit's worth of work, the planner flags it for retrospective analysis.
- **Compaction is forbidden, not "a safety net."** The framework design assumes compaction never fires. If it does, something is wrong.
- **Rolling summarizer** fires at the 60K guideline as a defensive measure: compress older turns, keep recent evidence near the attention hotspot.

## Alternatives considered

- **Fixed absolute limits** (40K/60K/80K/100K as hard exit-2 blocks). Initially proposed. Rejected by user: arbitrary hard cuts interrupt legitimate work. The honest answer is "we can't know the right number until we're doing the work; the planner should decide, not a fixed threshold."
- **Relative percentage limits** (70%/85%/95% of model max). Rejected: silently expand when the model's window changes. "95% of 1M" = 950K = LITM-guaranteed.
- **No limits; rely on CC's compaction.** Rejected: compaction is guaranteed context loss. It's the failure mode, not the safety net.

## References

- Canonical plan Appendix H §H.1 (Context Awareness)
- `@docs/architecture/principles/context-awareness.md` — the detailed principle
- Liu et al., "Lost in the Middle: How Language Models Use Long Contexts" (2023) — the LITM research
