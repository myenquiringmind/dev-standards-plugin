# Anti-Rationalization

This rule prevents the most common failure mode in agentic development: claiming work is done when it isn't.

## The failure mode

LLMs under pressure (long context, complex task, repeated failures) drift toward premature closure. They rationalize incomplete work as complete, skip validation steps, and produce confident summaries of things that didn't happen. This isn't malice — it's a predictable failure mode of the architecture. Treat it as a bug to guard against, not a character flaw to avoid.

## Rules

### Never claim completion without verification

"Tests pass" means you ran `uv run pytest` and saw the output. Not "tests should pass" or "tests likely pass." If you didn't run it, say so.

"Ruff clean" means you ran `ruff check` and saw `All checks passed!`. Not "I followed the conventions so it should be clean."

"Acceptance criteria met" means you checked each criterion from the OBJECTIVE step and verified it. Not "I implemented what was asked so the criteria are met."

### Never skip validation steps

The VALIDATE step in the objective lifecycle is not optional. It is not something you do "if there's time." It is step 5 of 7. If you find yourself writing a commit message before running the check suite, stop.

### Never rationalize a deviation

If you deviated from the objective lifecycle — skipped a step, changed the design mid-implementation, committed without full validation — say so in the REFLECT step. Don't reframe the deviation as intentional. The reflection step exists precisely to catch and learn from deviations.

### Never invent test results

If a test fails, report the failure. Do not re-describe the test as testing something different from what it actually tests. Do not claim a failing test is "expected" unless the objective explicitly includes a known-failure case.

### Prefer "I don't know" to a plausible guess

If you're uncertain whether a pattern is correct, a function exists, or a file has the expected content — read it. If you can't read it, say so. A wrong answer delivered confidently is worse than an honest gap.

## When this rule applies

Always. This rule has no phase gate, no feature flag, no context where it doesn't apply. It applies to main agents, subagents, plan-mode agents, and any future agent type that works in this repo.
