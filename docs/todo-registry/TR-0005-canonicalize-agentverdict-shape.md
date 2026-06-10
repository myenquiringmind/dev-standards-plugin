# TR-0005: canonicalize the AgentVerdict output shape across all agents

- **Discovered:** 2026-06-05, on `feat/phase-5-validation-cluster` (surfaced while authoring the Phase 5 retrofit agents)
- **Tier:** 3 (cross-cutting — affects every agent that returns a verdict; needs one canonical shape decided before a sweep)
- **Description:** Three AgentVerdict shapes now coexist in the framework:
  1. **Shipped validation agents** (`validation-objective-verifier`, `validation-completion-verifier`) emit `{agent, status, errors, classifications}`. The `/validate` stamp flow (`pre_commit_cli_gate` + the validate skill) keys on `status: "pass"`, so these cannot change shape without updating the gate.
  2. **The Phase 5 spec's retrofit contract** (`docs/phases/phase-5-core-agent-refactor.md`) mandates `{ok, reason, confidence, evidence}` — the planning-session AgentVerdict, whose new field is `confidence`.
  3. **The Phase 5 validation-cluster agents** (this branch: `validation-code-reviewer`, `validation-standards-reviewer`, `validation-lint-reviewer`, `validation-type-safety-reviewer`) emit `{agent, status, confidence, findings}` — a deliberate reconciliation that adds the spec-required `confidence` to the existing `{agent, status, …}` family without breaking the gate.

  These are mutually compatible enough to ship (the cluster agents are not stamp-gate consumers, so their shape does not feed `/validate`), but three shapes for one contract is drift. The Phase 5 live-verdict smoke check (stream 5) and any future verdict consumer need one canonical shape.
- **Remediation plan:**
  1. Pick the canonical AgentVerdict shape. Recommended: `{agent, status, confidence, findings}` (gate-compatible — `status` is preserved; `findings` generalises `errors`; `confidence` satisfies the planning-session requirement). Map `ok → status`, `evidence → findings`.
  2. Author `schemas/contracts/agent-verdict.schema.json` pinning it. (Phase 5 deliberately deferred this — see the spec's "NOT in Phase 5".)
  3. Update the two shipped validation agents to add `confidence` (additive — keeps `status`, so the gate is unaffected).
  4. Amend the Phase 5 spec's retrofit-contract wording from `{ok, reason, confidence, evidence}` to the canonical shape, so later streams retrofit against it.
  5. Point the stream-5 live-verdict smoke check at the committed schema.
- **Blocks:** none (advisory — all three shapes are functional today). Should be resolved before the Phase 5 stream-5 exit gate so the live check validates against a committed schema rather than an inline shape.
- **Status:** RESOLVED (2026-06-10, Phase 5 stream 5 / exit gate)
- **Resolution:** `schemas/contracts/agent-verdict.schema.json` pins the canonical `{agent, status, confidence, findings}` shape (remediation steps 1–2). The Phase 5 spec's retrofit-contract wording was amended to match (step 4). The stream-5 live-verdict smoke check now validates a real `validation-standards-reviewer` response against the committed schema (step 5). **Step 3 deliberately narrowed:** the two Phase 1 scope-verifiers (`validation-objective-verifier`, `validation-completion-verifier`) keep their richer `{agent, status, errors, classifications}` variant rather than gaining `confidence` — that variant feeds `/validate`'s stamp flow (which keys only on `status`), so modifying these gate-feeding agents is unnecessary and higher-risk than the value warrants. The canonical schema is scoped to the verdict family (the 13 retrofit agents + future reviewers/analysts); the verifiers are documented as a sanctioned variant in the schema's `description`. Rationale recorded in `docs/phases/phase-5-exit-report.md`.
