---
context: fork
model: sonnet
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent
argument-hint: (no arguments)
description: First-run project configuration. Classifies the project state, runs the interactive wizard, writes .language_profile.json and config/user-config.json.
phase: discover
---

# /setup — configure the framework for this project

Run once at project start. Composes two Phase 1 agents — `discover-project-state-classifier` and `discover-setup-wizard` — and writes the two config files the rest of the framework reads at runtime.

This command is idempotent in the **refuse** sense, not the **overwrite** sense: re-running it on an already-configured project surfaces the existing config and exits 0 without changes. Re-configuration is a deliberate act (remove the files, then re-run) — never a silent re-wiring.

## Procedure

1. **Check for existing configuration.** If `.language_profile.json` or `config/user-config.json` already exists at the project root, print:

   ```
   [setup] already configured:
     - .language_profile.json
     - config/user-config.json
   Remove these files (or /setup --force once that lands) to re-run.
   ```

   Exit 0. Do not proceed. This is a contract with the user: `/setup` does not overwrite.

2. **Classify the project state.** Invoke `discover-project-state-classifier` via the `Agent` tool. The agent scans the working directory and emits a JSON report matching `schemas/reports/project-state.schema.json`:
   - `classification`: `greenfield` | `growing-green` | `brownfield`
   - `confidence`: `high` | `medium` | `low`
   - `signals`: source/test file counts, CI detection, lockfiles, git age, languages detected

   Surface the report's `classification` + `confidence` to the user in a one-line summary:

   ```
   [setup] detected: <classification> (confidence: <confidence>)
   ```

3. **Run the wizard.** Invoke `discover-setup-wizard` via the `Agent` tool. Pass the classifier's report on stdin (or as a JSON fixture file — the wizard accepts either). The wizard:
   - Asks 3-6 questions via `AskUserQuestion` (language profiles, feature packs, commit-gate strictness; optional confirmation if classifier `confidence: low`).
   - Validates user answers against available profiles and packs.
   - Writes `.language_profile.json` and `config/user-config.json` via `hooks._os_safe.atomic_write`.
   - Emits a `Setup complete — <N> profiles active, <M> packs enabled.` line.

4. **Confirm.** Read the two written files back and show a summary to the user:

   ```
   [setup] .language_profile.json:
     language: python
     overrides: (none)
   [setup] config/user-config.json:
     activePacks: [python, patterns, security, document]
   [setup] strictness: strict
   [setup] done. Run /validate next.
   ```

   Do not modify either file in this final step — the wizard is the sole writer. Your job is to display, not mutate.

## Error paths

- **Classifier returns an error** (corrupted git, unreadable files, OSError). Surface the error and exit 1. Do not fall back to defaults — a classifier error means the wizard cannot pick reasonable defaults, and silently proceeding would misconfigure the project.
- **Wizard returns an error** (user cancelled, invalid answer unfixable). Surface the error and exit 1. Files may or may not have been partially written; print a recovery hint naming the exact files to check / remove.
- **Wizard writes only one of the two files.** Print a warning: "config partially written — remove `<written file>` and re-run /setup". Exit 1. Do not leave the project in a half-configured state.

## Do not

- Do not skip the classifier. The wizard's question defaults come from the classifier report; skipping to the wizard means asking the user questions whose defaults are guesses. Classifier → wizard is the pipeline; keep it ordered.
- Do not prompt for secrets. The wizard does not ask for API keys, endpoints, or credentials. Those belong in local-only files outside the framework's config tree.
- Do not write to any file the wizard does not explicitly claim to write. `/setup` orchestrates the wizard; it is not itself a config writer.
- Do not run long-running tasks first. If a slow scan (graph-registry rebuild, full project walk) is ever needed here, invoke `meta-session-planner` — but Phase 1 setup is fast enough that the planner adds no value. Phase 3+ revisit.

## Final check

Before the done line, verify:
- [ ] `.language_profile.json` exists and is valid JSON.
- [ ] `config/user-config.json` exists and contains an `activePacks` array.
- [ ] Neither file contains a secret (quick regex scan: `sk-`, `AKIA`, `-----BEGIN`).
- [ ] The wizard reported `Setup complete`.

If any box is unchecked, print an error and exit 1 — do not declare `/setup` done when the output is inconsistent.

## Phase 1 note

The Phase 1 wizard offers python, javascript, or "none" for language profiles; later phases add more. The pack list the wizard exposes is the set that has at least one agent implemented today — not the full 12-pack catalog declared in `schemas/agent-frontmatter.schema.json`. The wizard reads that inventory at runtime, so this command does not need to be updated as packs come online; the wizard is the single source of truth for \"what can the user enable right now\".
