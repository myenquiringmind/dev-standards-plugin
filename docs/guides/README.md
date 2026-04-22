# How-To Guides

Task-oriented documentation for specific goals. Each guide answers "I want to do X — what are the steps?"

## Available guides

| Guide | For whom | Status |
|---|---|---|
| [Getting started](./getting-started.md) | New contributors to `dev-standards-plugin` | Available |
| [Multi-branch coordination](./multi-branch-coordination.md) | Agents and humans working across interlocking PRs | Available |
| [Wiring up the statusline](./statusline-wiring.md) | Users enabling the context-percentage status line | Available |
| Developing a new agent | Contributors adding agents | Stub (Phase 2+) |
| Developing a new hook | Contributors adding hooks | Stub (Phase 2+) |
| Running validation | Users and contributors | Stub (Phase 1+) |
| Installing the plugin | End users | Stub (Phase 11) |
| Troubleshooting | Users and contributors | Stub (Phase 6+) |

## Why most guides are stubs

Phase 0 is architecture lockdown. The framework itself doesn't exist yet — there's nothing to "how-to" against. Guides are written when the features they describe are operational:

- "Developing a new agent" requires `meta-agent-scaffolder` and the `/new-agent` command (Phase 1 bootstrap)
- "Running validation" requires `/validate` and the stamp model (Phase 1 bootstrap)
- "Installing the plugin" requires a public, documented release (Phase 11)

Each guide is authored as part of the phase that delivers the feature. Until then, the canonical plan archive (`docs/decision-records/v2-architecture-planning-session.md`) and the phase specs (`docs/phases/`) are the references.

## Guide conventions

1. **One guide per task.** "Developing a new agent" and "developing a new hook" are separate guides even though the workflow is similar.
2. **≤200 lines per guide** (enforced by `hooks/post_edit_doc_size.py` from Phase 1 exit).
3. **Prerequisites first.** Start with "Before you begin, you need: ..."
4. **Numbered steps.** Every guide is a numbered procedure, not a prose essay.
5. **Verify at the end.** Last step is always "Verify it worked by ..."
6. **Link to principles, don't duplicate.** If the guide touches a principle (PSF, stamps, R/R/W), link to `docs/architecture/principles/<name>.md`. Don't repeat the principle's content.
