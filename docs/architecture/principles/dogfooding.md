# Dogfooding

The framework uses its own agents, commands, hooks, and gates to build itself. This is not optional — it is a design requirement and a test: **if you can't do it via the framework, the framework is missing something.**

## The principle

Every architectural rule is applied to the framework's own construction. Rules the framework doesn't hold itself to aren't real rules — they're aspirations the framework hasn't earned.

Practically:

- The framework's own agent files pass through `meta-agent-arch-doc-reviewer`
- The framework's own commits pass through `pre_commit_cli_gate.py`
- The framework's own code is linted by the profile it ships (ruff/mypy for Python)
- The framework's own documentation obeys the `post_edit_doc_size.py` ≤200-line limit
- The framework's own agents are scaffolded by `meta-agent-scaffolder` (from Phase 2 onwards)
- The framework's own hooks are scaffolded by `meta-hook-scaffolder`
- The framework's own rules are validated by `meta-rule-validator` against `agent-frontmatter.schema.json`

## The test

Any proposed architectural rule must pass the dogfooding test: *can we apply this rule to the framework's own construction today?*

If the answer is "not yet," the rule is deferred until the framework can. If the answer is "no, ever," the rule is rejected — it's an aspiration, not an architecture.

## Worked example: the monolithic plan

During Phase 0 of `dev-standards-plugin` v2, the architecture plan was authored as a single 3300-line file (`cozy-doodling-church.md`) in the user's plan directory, referenced from a 120-line repo README as "the canonical plan." An agent asking "what does the stamp model say?" would have loaded the entire plan file to find the answer — 25-30K tokens, 25-50% of the smaller per-phase context budgets, consumed before any work began.

**The failure:** this violated four of the plan's own principles simultaneously:

- **PSF** — rules should be cheap and path-scoped. A 3300-line monolith is neither.
- **Four-tier memory** — runtime references should live in project tier with scoped loading. The plan lived in the user's home directory as a single blob, loaded in full.
- **Per-phase context budgets** — budgets of 40K-120K tokens were designed. A 25K-token document eats 25-50% of those budgets before any work starts.
- **Selective loading** — agents should load only what they need. There was no mechanism to load partial content from the plan.

The plan was context-hostile. The framework was preaching context-awareness discipline in a document that failed the discipline.

**The fix:** decompose the plan into the `docs/architecture/principles/` + `docs/phases/` + `docs/decision-records/` hierarchy following the Diataxis taxonomy. Each file ≤200 lines. Size limit mechanically enforced by `hooks/post_edit_doc_size.py` from Phase 1 exit onwards. Composition via `@include` from CLAUDE.md files. The canonical plan file becomes an archived decision record in git, never loaded at runtime.

**The lesson:** every architectural principle must be applied to the architecture artifact itself. If the documentation structure violates the framework's own rules, those rules aren't yet internalized.

**The dogfooding save:** the verifier for the foundational schemas caught a missing `codebase` prefix in `agent-frontmatter.schema.json` on its first run — a bug that would have shipped in Phase 0 and broken Phase 3 scanner creation silently. Without the verifier (which is itself a small dogfooding artifact), we would have debugged this weeks later.

## The recursive virtue

Because the framework builds itself through its own gates, every failure of the framework to enforce its rules on itself is immediately visible. The framework cannot accumulate technical debt that bypasses its own safety mechanisms — any such bypass would be caught by the framework's own agents during commit.

This is the strongest form of correctness assurance we can build: not "we tested it," but "we shipped with it, through it, using it, in a repo that is itself a target of the framework." The framework is its own most demanding user.

## Anti-pattern: dogfooding theatre

It is tempting to claim dogfooding while quietly bypassing the gates. Classic anti-patterns:

- **Skipping the gate with `[WIP]` for convenience.** The bypass exists for emergency handoff, not routine work. `[WIP]` commits during normal development are a smell; retrospective analysis flags them.
- **Amending commits to sneak past the gate.** Amending a commit that failed validation doesn't make it validated. The gate runs on every commit attempt, including amends.
- **Running `--no-verify`.** Git's bypass flag doesn't help — the gate is in CC's PreToolUse hook, not git's commit-msg hook.
- **Working in a worktree outside the plugin's supervision.** Developing in a worktree that isn't gated by the installed plugin is a deliberate opt-out of dogfooding. It leaves no trace in telemetry.

All four are detectable. `closed-loop-incident-retrospective-analyst` flags patterns of bypass in its weekly review. Consistent bypass is an architectural issue that needs addressing, not a workflow shortcut.

## Why this is the most important principle

The other principles (PSF, memory tiers, stamps, R/R/W, etc.) are load-bearing but replaceable. Dogfooding is load-bearing and **irreplaceable**: without it, the framework has no feedback loop. It becomes a linter that lints other people's code but not its own. That's the failure mode every development framework eventually falls into, and it's the one this framework is explicitly designed to avoid.
