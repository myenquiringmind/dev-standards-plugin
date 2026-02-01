---
name: orchestrate
description: |
  Execute the standards orchestrator with phase sequencing, checkpoints, and handoffs.
  Run development standards across domains (logging, error, type, lint, test, validation, git, housekeeping, naming) with enforced workflow phases: Design -> Validate Design -> Build -> Test -> Validate.
---

# Orchestrate Skill

Execute the standards orchestrator runtime to apply development standards systematically.

## Invocation

```
/orchestrate domain=<domain> [phase=<phase>]
```

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `domain` | Yes | Domain to orchestrate. Options: `logging`, `error`, `type`, `lint`, `test`, `validation`, `git`, `housekeeping`, `naming`, `all` |
| `phase` | No | Specific phase to start from. Options: `design`, `validate-design`, `build`, `test`, `validate` |

## Examples

```bash
# Run all phases for git standards
/orchestrate domain=git

# Run all phases for all domains
/orchestrate domain=all

# Run only design phase for logging
/orchestrate domain=logging phase=design
```

## Workflow Phases

The orchestrator executes these phases in sequence:

1. **Design** - Analyze current state, propose improvements
2. **Validate Design** - Review proposal for completeness and conflicts
3. **Build** - Implement the approved design
4. **Test** - Write and run tests for implementation
5. **Validate** - Final verification that everything works

### Checkpoints

After **design** and **build** phases, execution pauses for user approval:

- **Approve**: Type `approve`, `yes`, `proceed`, or `lgtm` to continue
- **Modify**: Provide feedback to re-run the current phase
- **Reject**: Type `reject` or `rollback` to stop execution

## Domain Agents

Each domain has a dedicated agent with specific expertise:

| Domain | Agent | Expertise |
|--------|-------|-----------|
| `logging` | `@logging-standards` | Structured logging, log levels, debug mode |
| `error` | `@error-standards` | Try/catch patterns, error types, stack traces |
| `type` | `@type-standards` | JSDoc types, TypeScript, mypy |
| `lint` | `@lint-standards` | ESLint, ruff, auto-fix, rule config |
| `test` | `@test-standards` | Unit/integration tests, coverage, mocking |
| `validation` | `@validation-standards` | Input validation, sanitization, security |
| `git` | `@git-standards` | Conventional commits, branch naming |
| `housekeeping` | `@housekeeping-standards` | Project layout, temp dirs, clutter |
| `naming` | `@naming-standards` | File/function naming conventions |

## Handoffs

When one agent's work requires another agent (e.g., new error handling needs logging), handoffs are tracked:

```
@error-standards (build) -> @logging-standards: Add logging to catch blocks
@logging-standards (build) -> @test-standards: Add test coverage
```

## CLI Commands

The orchestrator can also be controlled via CLI:

```bash
# Initialize
node lib/orchestrator/cli.js init domain=git

# Check status
node lib/orchestrator/cli.js status

# Advance to next phase
node lib/orchestrator/cli.js advance

# Handle checkpoint
node lib/orchestrator/cli.js checkpoint approve
node lib/orchestrator/cli.js checkpoint reject "Need more tests"

# Get current agent prompt
node lib/orchestrator/cli.js prompt

# View progress
node lib/orchestrator/cli.js progress

# Manage handoffs
node lib/orchestrator/cli.js handoff status
node lib/orchestrator/cli.js handoff register '{"to":"test-standards","reason":"Add tests"}'

# Reset
node lib/orchestrator/cli.js reset
```

## State Persistence

Orchestrator state is saved to `tmp/.orchestrator-state.json` and persists across sessions:

- Current domain and phase
- Completed phases with timestamps
- Pending handoffs
- Checkpoint status
- Execution history

## When to Use This Skill

Use `/orchestrate` when you want to:

1. **Apply standards systematically** - Not ad-hoc, but with proper phases
2. **Get user approval at key points** - Checkpoints ensure you agree with changes
3. **Track dependencies** - Handoffs ensure nothing is forgotten
4. **Audit the process** - History shows exactly what happened

## Example Session

```
User: /orchestrate domain=git

Claude: Initializing orchestrator for domain: git
        Phase: design
        Loading @git-standards context...

        [Executes design phase, proposes changes]

        ## Checkpoint: design Complete
        **Agent**: @git-standards
        **Phase**: design
        **Status**: Awaiting user approval

        ### Changes Proposed
        - Add conventional commit validation
        - Add pre-commit hook for message format
        - Block AI co-authoring in commits

        User Action Required:
        - [ ] Approve and proceed
        - [ ] Request modifications
        - [ ] Reject and rollback

User: approve

Claude: Checkpoint approved. Advancing to: validate-design
        ...
```

## Integration with Hooks

The orchestrator integrates with plugin hooks:

- **PreToolUse**: Blocks edits when checkpoint is pending
- **PostToolUse**: Tracks changes made during build phase

This ensures the workflow cannot be bypassed accidentally.
