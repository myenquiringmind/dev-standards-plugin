# Hook Catalog

42 hooks across 26 Claude Code lifecycle events. Hooks are deterministic code on lifecycle events — they block when invariants are violated, emit telemetry, and enforce the framework mechanically. See PSF at `@principles/psf.md` (hooks are the second rung).

## By lifecycle event

| Event | Hooks | Phase |
|---|---|---|
| **SessionStart** | `session_start.py` (reinject state, restore todos), `detect_language.py` (write `.language_profile.json`), `version_check.py` (24hr cache), `session_start_gitignore_audit.py` (validate .gitignore) | 1, 2 |
| **SessionEnd** | `session_end.py` (save state) | 1 |
| **UserPromptSubmit** | `context_budget.py` (dynamic hard cut, guideline warns), `create_feature_branch.py` (auto-branch from protected), `phase_transition.py` (detect phase change) | 1, 2 |
| **PreToolUse (Edit\|Write)** | `branch_protection.py` (block on protected), `pre_write_secret_scan.py` (regex secret scanner), `pre_tool_use_tier_enforcer.py` (R/R/W tier gate) | 1, 2 |
| **PreToolUse (Bash)** | `pre_commit_cli_gate.py` (stamp enforcement + staged secret scan), `dangerous_command_block.py` (destructive command guard), `pre_bash_tier_guard.py` (read-only Bash for R-tier agents), `checkpoint_gate.py` (orchestrator checkpoint) | 1, 2 |
| **PostToolUse (Edit\|Write)** | `post_auto_format.py` (language-aware format), `post_edit_lint.py` (language-aware lint), `post_track_changed_files.py` (orchestrator tracking), `post_edit_doc_size.py` (≤200 line enforcement), `post_temp_file_cleanup.py` (tmpclaude-* cleanup) | 1, 2 |
| **PostToolUseFailure** | `post_tool_failure.py` (telemetry seed) | 1 |
| **PreCompact** | `pre_compact.py` (preserve session state) | 1 |
| **PostCompact** | `post_compact.py` (verify, cleanup stale caches) | 1 |
| **Stop** | `stop_validation.py` (block stop with uncommitted changes) | 2 |
| **StopFailure** | `stop_failure.py` (incident record on API error) | 2 |
| **SubagentStart** | `subagent_start.py` (cost-budget tracker, timeout cascade) | 2 |
| **SubagentStop** | `closed-loop-transcript-todo-extractor` via hook type `agent` (deferral extraction) | 1 |
| **TaskCreated** | `task_created.py` (bridge to session-state graph) | 2 |
| **TaskCompleted** | `task_completed.py` (bridge to quality scoring) | 2 |
| **FileChanged** | `file_changed.py` (watch graph-registry.json, profiles; trigger re-validation) | 2 |
| **WorktreeCreate** | `worktree_lifecycle.py` (stamp per-worktree profile, seed memory) | 2 |
| **WorktreeRemove** | `worktree_lifecycle.py` (teardown stamps, cleanup) | 2 |
| **ConfigChange** | `config_change.py` (atomic reload profiles + graph registry) | 2 |
| **CwdChanged** | `cwd_changed.py` (re-run language detection for monorepos) | 2 |
| **InstructionsLoaded** | `instructions_loaded.py` (audit which rules loaded, telemetry) | 2 |
| **PermissionDenied** | `permission_denied.py` (feedback loop for auto mode) | 2 |
| **Notification** | (none currently) | — |

## Shared modules (not hooks, imported by hooks)

| Module | Purpose |
|---|---|
| `_hook_shared.py` | Single source of truth: validation step tuples, `compute_hard_cut()`, `read_hook_input()`, cache intervals, budget dicts |
| `_session_state_common.py` | `write_session_state()`, `extract_from_transcript()`, memory dir resolver, todo extraction |
| `_os_safe.py` | Atomic write, portalocker lock, safe_join, normalize_path, temp lifecycle — mandatory for all disk writes on Windows |
| `_telemetry.py` | JSONL emission, batching, rotation |
| `_incident.py` | ULID generation, incident schema, append-only writer |
| `_graph.py` | Graph registry loader, query helpers, topological sort |

## How hooks interact with other components

```
CC lifecycle event ──fires──> Hook ──reads──> _hook_shared.py (tuples, thresholds)
                                    ──reads──> config/profiles/*.json (language)
                                    ──reads──> .validation_stamp (freshness)
                                    ──writes──> session-state.md (checkpoints)
                                    ──writes──> .claude/.context_pct (statusline)
                                    ──exits 2──> blocks tool call (enforcement)
```

Hooks are composed by commands (indirectly — commands trigger tool calls which fire hooks). Hooks consume schemas (stamp.schema.json for stamp validation). Hooks read profiles. Hooks invoke agents (via `hook type: agent` for SubagentStop).

## Bootstrap vs full

Phase 1 bootstrap ships **17 core hooks**. Phase 2 adds the remaining **25** to complete the full 42.

See `@phases/phase-1-bootstrap.md` for the bootstrap hook list.
