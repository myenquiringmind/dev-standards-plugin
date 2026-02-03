# Changelog

All notable changes to the dev-standards plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.4.0] - 2026-02-03

### Added
- **Git workflow integration for orchestrator**:
  - Automatic branch creation (`feat/orchestrator-<domain>-<timestamp>`)
  - Phase commits with conventional commit messages
  - Rollback points at checkpoint phases (design, build)
  - PR finalization option on completion
- `gitMode` parameter for orchestrator: `auto`, `manual`, `disabled`
- Orchestrator state persistence across sessions (`tmp/.orchestrator-state.json`)
- Additional domain agents: `@housekeeping-standards`, `@naming-standards`
- Handoff orchestration with cycle detection
- Checkpoint approval protocol (approve/modify/reject)

### Changed
- Orchestrator refuses to run on protected branches
- State persistence includes git workflow tracking
- PostToolUse hooks track changed files during orchestrator workflow

### Fixed
- Cleanup for `tmpclaude-*` temp files in hooks
- Plugin.json schema compliance

## [1.3.0] - 2026-02-01

### Added
- **Orchestrator + Domain Agents Architecture**: New agent pattern for comprehensive standards enforcement
  - `@standards-orchestrator`: Workflow coordinator that dispatches to domain agents
  - 7 domain agents, each handling all workflow phases (Design → Validate → Build → Test → Validate):
    - `@logging-standards`: Logging best practices
    - `@error-standards`: Error handling patterns
    - `@type-standards`: JSDoc/TypeScript type annotations
    - `@lint-standards`: ESLint/Ruff configuration
    - `@test-standards`: Test coverage and patterns
    - `@validation-standards`: Input validation and security
    - `@git-standards`: Conventional commits and branch protection
- **Modular library structure**: Reorganized lib/ into focused modules
  - `lib/core/`: Platform detection, config, command execution
  - `lib/venv/`: Virtual environment management
  - `lib/git/`: Git operations
  - `lib/logging/`: Session logging with debug support
  - `lib/validation/`: Security validation
  - `lib/tools/`: Formatter/linter/typechecker execution
  - `lib/version/`: Version checking
- **Security improvements**:
  - Command injection prevention via `escapeShellArg()`
  - Package name validation before installation
  - stdin size limits
- **Debug logging**: Set `DEBUG=true` for verbose troubleshooting output
- **Comprehensive JSDoc**: All functions have @param, @returns, @example annotations

### Changed
- Refactored `@code-reviewer` to delegate to domain agents
- Merged `@test-writer` into `@test-standards`
- Updated `.gitignore` with Python artifacts (.venv, __pycache__, etc.)
- Updated `CONTRIBUTING.md` with architecture overview and debug docs
- Version bump from 1.2.0 to 1.3.0 across all files

### Removed
- `@test-writer` agent (merged into `@test-standards`)
- Duplicate venv.js and run-python-tool.js (consolidated into lib/venv/)

## [1.2.0] - 2025-02-01

### Added
- **Automatic venv creation**: Creates `.venv` on first Python file edit using `uv` (preferred) or `python -m venv` (fallback)
- **Venv-aware Python tools**: ruff, mypy now automatically run through the project's venv
- **Auto-install plugin dependencies**: ruff and mypy installed into venv when needed
- **Version checking**: Checks for plugin updates on session start (cached 24h)
- **Shared utilities module**: `lib/utils.js` for DRY/SOLID compliance
- **requirements.txt**: Python dependencies manifest (ruff>=0.1.0, mypy>=1.0.0)
- New tests for venv utilities and version checking (25 tests)

### Changed
- Refactored all hooks to use shared `lib/utils.js` module
- SessionStart now checks for plugin updates (non-blocking)
- Updated `/setup` command with venv creation instructions

## [1.1.0] - 2025-01-20

### Added
- **Type checking hooks**: Automatic TypeScript (`tsc --noEmit`) and Python (`mypy`) type checking on file save
- **Lint-on-save hooks**: Automatic ESLint and Ruff checking with warning output
- **Session logging**: All prompts, tool usage, and completions logged to `~/.claude/logs/`
- **UserPromptSubmit hook**: Tracks when prompts are submitted
- `/typecheck` command: On-demand type checking across project
- `/logs` command: View session logs and activity
- Updated Stop hook to verify type/lint status before completion

### Changed
- Hooks now output warnings to stderr instead of blocking (non-breaking)
- Improved error message formatting for type/lint issues

## [1.0.0] - 2025-01-15

### Added
- Initial release
- **Branch protection**: Blocks edits to main/master/production branches
- **Dangerous command blocking**: Prevents destructive shell commands
- **Auto-formatting**: Prettier, Ruff, gofmt, rustfmt on file save
- **Validation checkpoint**: Stop hook verifies tests and environment
- **Subagent summaries**: SubagentStop hook requires concise summaries
- **Context logging**: PreCompact logs compaction events
- `/plan` command with TLDR + verbose output
- `/fix` command for complete bug fix workflow
- `/validate` command for comprehensive verification
- `/review` command for code review
- `/setup` command for project initialization
- `@investigator` agent for root cause analysis
- `@code-reviewer` agent for quality review
- `@test-writer` agent for test creation
- `@doc-writer` agent for documentation
- `dev-workflow` skill for code task guidance

## [Unreleased]

### Planned
- Security scanning hook (detect secrets in code)
- Dependency vulnerability checking
- Performance profiling hooks
- Integration with GitHub Actions / CI
