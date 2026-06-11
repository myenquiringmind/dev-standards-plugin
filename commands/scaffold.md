---
context: fork
model: sonnet
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent
argument-hint: <module path or name to scaffold>
description: Scaffold a module — a stub file (bodies elided) plus a RED test skeleton, verified failing before /tdd makes it green.
phase: develop
---

# /scaffold — stub + RED test skeleton

Create the starting shape of a module so `/tdd` has something to drive: a stub file whose public interface exists but whose bodies are elided, and a comprehensive test skeleton that **fails** against that stub. The single responsibility is *producing the RED starting state* — `/scaffold` never implements logic. The moment a body does real work, that is `/tdd`'s job.

A scaffold is only done when its tests are RED — every test FAILs, none ERRORs, none PASSes. A test that errors (import/collection) or passes (against an unimplemented stub) is a broken test, not a spec. `scaffold_red_gate.py` enforces this.

## Procedure

1. **Plan.** Invoke `meta-session-planner` first; it sizes the scaffold against the session budget and writes the Task Progress list to `session-state.md`.

2. **Resolve the target.** From `$ARGUMENTS`, determine the module path and the active language profile (read `.language_profile.json`, or run `detect_language` over the target). The profile supplies the test layout (`tests/unit/`, etc.) and the naming conventions.

3. **Validate structure and naming.** If `meta-folder-structure-advisor` and `meta-filename-advisor` are registered, invoke them via the `Agent` tool to confirm the target directory and filenames. Until those advisors land, apply the active profile's `conventions` (file/function/class naming) directly — do not invent a layout the profile does not sanction.

4. **Derive the interface.** Read the module's architecture doc under `docs/architecture/` (or the objective in `session-state.md` if no doc exists). The stub's public surface comes from the intended design, not from guesswork.

5. **Write the stub.** Create the module with its public functions/classes present and fully typed, bodies elided (`...` or `raise NotImplementedError`). No logic. Imports and signatures only — enough for the tests to import and call it.

6. **Write the test skeleton.** Generate tests in the profile's categories — unit, property-based, and deterministic — that assert the *intended* behaviour. They must reference the real stub surface so they FAIL (the stub returns nothing), not ERROR (a missing symbol). Cover the acceptance criteria, not just the happy path.

7. **Assert RED.** Run `uv run python -m hooks.scaffold_red_gate --language <profile> --test <path> [--test ...]`. Exit 0 means RED confirmed. A non-zero exit means the scaffold is broken — tests ERROR (fix imports/symbols), PASS (the stub is too complete or the test is trivial), or none were collected. Repair and re-run, **max 3 attempts**.

8. **Report.** List the scaffolded files, confirm RED, and recommend `/tdd <objective>` as the next step. Do not start implementing.

## Do not

- **Do not implement logic.** Bodies stay elided. If you write a working implementation, you have done `/tdd`'s job and skipped the RED state that makes TDD meaningful.
- **Do not write tests that pass.** A green scaffold is a failed scaffold. The tests are the spec; they must fail until `/tdd` implements the code.
- **Do not let tests ERROR and call it RED.** An import error is not a failing assertion. `scaffold_red_gate` distinguishes them; trust its verdict over a glance at the output.
- **Do not call another command.** Recommend `/tdd` to the user; do not invoke it (`meta-command-composition-reviewer` enforces command-composes-agents, not commands).
- **Do not skip `meta-session-planner` or the RED gate.** Both are load-bearing — the first for budget, the second for correctness.

## Final check

Before reporting success, verify:
- [ ] The stub file exists with a typed public interface and elided bodies — no real logic.
- [ ] The test skeleton imports the real stub surface (tests FAIL, not ERROR).
- [ ] `scaffold_red_gate` exited 0 (RED confirmed) — not assumed from a manual read of the output.
- [ ] The report names the scaffolded files and the `/tdd` hand-off.

If any box is unchecked, the scaffold is not RED-complete — report what remains, do not declare it ready for `/tdd`.
