# Changelog

All notable changes to the dev-standards plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2025-02-01

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
