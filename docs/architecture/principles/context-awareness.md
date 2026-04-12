# Context Awareness

Large language models have a U-shaped attention curve: strong at the beginning and end of context, weak in the middle. This is the **lost-in-the-middle (LITM)** phenomenon documented in Liu et al., "Lost in the Middle: How Language Models Use Long Contexts" (2023). Larger context windows make LITM **worse**, not better — they widen the middle where attention fails.

The framework defends against LITM with four mechanisms: **guideline budgets, a dynamic hard cut, a session planner, and a rolling summarizer.**

## The 1M trap

Anthropic's decision to expand Opus 4.6 to 1M tokens does not help long-session work. A 1M session with 900K in the middle is effectively unreliable for anything placed there. Relative thresholds (70%/85%/95% of the active model's max) silently expand when the window does — "95% of 1M" is 950K tokens of LITM-guaranteed failure.

The framework uses **absolute** values, not relative ones, and frames most of them as **guidelines** that inform the session planner, not hard blocks that interrupt work.

## One hard constraint: never compact

Claude Code auto-compacts at ~83.5% of the active model's window. Compaction is **guaranteed context loss in the middle** and is forbidden as a safety mechanism.

**The only hard constraint:** `/handoff` is forced before CC compaction fires. `hooks/_hook_shared.py` exposes `compute_hard_cut()` which returns **75% of the compaction threshold** — about **62% of the active model's window** — as the framework's hard cut. This is dynamic: it depends on which model is active at runtime.

| Active model | Window | CC compaction fires at | Framework hard cut |
|---|---|---|---|
| Sonnet 200K | 200K | ~167K | **~125K** |
| Opus 200K | 200K | ~167K | **~125K** |
| Opus 1M | 1M | ~835K | ~625K nominal (but LITM is catastrophic well before here) |

`hooks/context_budget.py` computes the hard cut at session start, monitors the running token count (via `statusline.py`), and exits 2 on UserPromptSubmit when the cut is reached. The user cannot work further until `/handoff` runs. Compaction is **forbidden**, not avoided.

## Guidelines — informational, not enforced

Because LITM degrades attention quality well below the model's nominal capacity, the framework carries **guideline values** that `meta-session-planner` uses when sizing and decomposing work:

| Guideline | Typical tokens | Meaning for the planner |
|---|---|---|
| Comfort | 40K | Preferred task size — attention strongest, cheapest to debug, smallest meaningful commit |
| Soft warn | 60K | Plan a natural handoff point in the next few turns |
| Attention ceiling | 80K | LITM effects noticeable; planner strongly prefers decomposition, does not block |
| Dynamic hard cut | compute_hard_cut() | The one real block; forces `/handoff` |

Guidelines are **not hooks that block work**. They are inputs to the planner's task-sizing logic. The principle: "as small as possible, as large as necessary, smaller is always preferable." Git commits are the natural unit — each task should fit a reasonable commit-sized chunk of work.

## Agent-driven session chunking: `meta-session-planner`

A blocking bootstrap agent invoked at the start of every significant command (`/tdd`, `/scaffold`, `/fix`, `/debug`, `/refactor`, `/design`, `/research`, `/pattern`, `/document`, `/incident`, `/maintain`). The planner:

1. Reads the stated objective and the current session state
2. Estimates the token cost of the proposed work
3. Compares against the phase's guideline budget and the remaining session budget
4. If too large, decomposes into 2-4 sub-tasks with explicit validate + handoff checkpoints
5. Emits the plan to `session-state.md` as the Task Progress list

Commands that skip `meta-session-planner` are blocked by the composition reviewer — you cannot start significant work without going through the planner.

## Rolling summarizer: `closed-loop-context-rolling-summarizer`

Pulled from Phase 4 into the bootstrap. Fires at the 60K guideline (soft warn). Compresses older conversation turns into a structured summary block placed immediately before the current turn — **near the attention hotspot, away from the LITM zone**.

Preserves verbatim:

- All CLAUDE.md content (re-read from disk by CC automatically)
- The last 5 user messages
- The last 5 tool results
- Any structured agent verdict in the last 20 turns
- The current objective from session-state.md

Compresses everything older into a structured summary with sections: Decisions made, Actions taken, Open threads, Known errors, Current state.

## Session checkpoints

`hooks/session_checkpoint.py` (PostToolUse on Edit/Write) writes `session-state.md` every 5 qualifying events, every 15 minutes, or on every phase transition. Avoids the "session crashed mid-work, all state lost" failure mode that occurs when session state only updates on SessionEnd/PreCompact/explicit handoff.

## The statusline

`hooks/statusline.py` is the plumbing: it continuously writes the current token count (estimated from the transcript) and current phase to `.claude/.context_pct`. Every other context-aware hook reads this cache.

## Ten Modelling mechanisms + one new primitive

Context awareness is mechanism #11 — the one the Modelling project didn't have because single-session work below 200K didn't need it. With 1M-window models and long-running framework development, it's non-negotiable.

See `@docs/architecture/principles/bootstrap-first.md` for the ten original mechanisms.

## What this is NOT

- **Not a cap on total work.** A project can take 100 sessions; each session is bounded. Work accumulates via git commits and project-tier memory, not via one giant session.
- **Not an excuse for bad decomposition.** The planner decomposes; the user doesn't hand-roll "small sessions" by eyeballing token counts.
- **Not reliance on compaction.** If the framework ever depends on compaction surviving context, the framework has already failed. Compaction is the failure mode.
