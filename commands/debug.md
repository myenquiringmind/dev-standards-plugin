---
context: fork
model: sonnet
allowed-tools: Bash, Read, Glob, Grep, Agent
argument-hint: [what is failing — a test name, an error message, or a description]
description: Diagnose a failure to its root cause via a reproduce-then-hypothesise loop. Produces a root-cause report; does not change code.
phase: develop
---

# /debug — diagnose a failure to root cause

Find *why* something fails. `/debug` reproduces the failure deterministically, drives a hypothesis-elimination loop, and reports the root cause with the evidence that pins it. It is **diagnostic only** — it never edits source. Remediation is `/fix` (end-to-end bug fix) or `/tdd` (when the failure is a red test you are about to make green).

The one responsibility here is *explanation*. The moment a fix is written, that is a different command's job. Keeping `/debug` read-only is what makes it composable: `/fix` and `/tdd` consume its report instead of re-deriving it.

## Procedure

1. **Plan.** Invoke `meta-session-planner` first. A deep debug can outrun the session budget; let the planner size it and write the Task Progress list to `session-state.md`. If the planner decomposes the failure into independent threads, debug them in its order.

2. **Reproduce.** Establish a deterministic repro before theorising. Run the failing test (`uv run pytest <node-id> -x`), command, or scenario from `$ARGUMENTS` and capture the exact output. If you cannot reproduce it, say so and stop — an unreproducible failure is a finding, not a root cause. Note any non-determinism (ordering, timing, environment) explicitly.

3. **Delegate analysis.** Hand the repro and captured output to `operate-root-cause-analyst` via the `Agent` tool. It forms competing hypotheses, traces each against the code and the evidence, and eliminates them down to the mechanism — distinguishing the root cause from its symptoms. Give it the failing artifact, the output, and the repro command so it does not re-discover them.

4. **Confirm.** A hypothesis is the root cause only when the evidence forces it: the analyst can point to the line/condition, explain the mechanism, and the repro behaviour matches the explanation. If two hypotheses survive, report both with their discriminating tests rather than guessing.

5. **Report.** Produce a structured root-cause report: the failure, the reproduction, the confirmed mechanism (file:line), the symptoms it was masquerading as, and the *direction* of the fix (not the fix). Append it to `session-state.md` so `/fix` or `/tdd` can pick it up.

6. **Hand off.** Recommend the remediation path — `/fix` for a standalone bug, `/tdd` for a red-test failure. Do not implement the fix.

## Do not

- **Do not edit source.** `/debug` carries no `Edit`/`Write` tools by design. If you find yourself wanting to change code, stop and hand off to `/fix` — that boundary is the command's whole point.
- **Do not claim a root cause without a reproduction.** "It's probably the cache" is a hypothesis, not a diagnosis. If you could not reproduce the failure, report that and the conditions you tried.
- **Do not stop at the symptom.** A `KeyError` is where it surfaced, not why the key is missing. The report names the mechanism, not the exception type.
- **Do not call another command.** Commands compose agents, not commands (`meta-command-composition-reviewer` enforces this). Recommend `/fix` or `/tdd` to the user; do not invoke them.
- **Do not skip `meta-session-planner`.** Skipping the planner on a long-running command is a composition-reviewer block.

## Final check

Before reporting a diagnosis, verify:
- [ ] The failure was reproduced (or its unreproducibility was reported as the finding).
- [ ] The root cause names a concrete mechanism at `file:line`, not a symptom or a guess.
- [ ] The report distinguishes root cause from symptom and states a fix *direction*, not a fix.
- [ ] No source file was modified by this command.

If any box is unchecked, the diagnosis is incomplete — report what is known and what remains, do not declare a root cause found.
