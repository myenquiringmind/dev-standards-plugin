---
name: dev-workflow
description: |
  Enforces best practice development workflow for any code task. Triggers on: feature implementation, bug fixes, refactoring, code changes, debugging, testing, and any development work. Ensures DRY/SOLID principles, comprehensive testing, validation, proper git commits, and structured planning with TLDR summaries.
---

# Development Workflow

## Core Principle

```
Investigate → Plan → Implement → Test → Validate → Commit
```

Never skip steps. The most common failures come from implementing without understanding.

## Quick Reference

| Task | Command | Subagent |
|------|---------|----------|
| Create plan | `/plan` | - |
| Fix a bug | `/fix` | `@investigator` |
| Validate changes | `/validate` | - |
| Code review | `/review` | `@code-reviewer` |
| Write tests | - | `@test-writer` |
| Update docs | - | `@doc-writer` |

## Workflow by Task Type

### Bug Fix
1. Delegate to `@investigator` for root cause analysis
2. `/plan` the fix with TLDR
3. Implement on feature branch
4. `/validate` all changes
5. Commit with `fix(scope): description`

### New Feature
1. `/plan` with requirements breakdown
2. Implement incrementally
3. Delegate `@test-writer` for coverage
4. `/review` before completion
5. `/validate` and commit

### Refactoring
1. Ensure tests exist first (delegate `@test-writer` if not)
2. `/plan` the refactoring approach
3. Make small, incremental changes
4. Run tests after each change
5. `/validate` behavior unchanged

## Code Quality Standards

### DRY (Don't Repeat Yourself)
- Extract to function when pattern appears 3+ times
- Create shared utilities for cross-module patterns
- Use constants for magic numbers/strings

### SOLID Principles
- **S**ingle Responsibility: One function = one purpose
- **O**pen/Closed: Extend behavior without modifying existing code
- **L**iskov Substitution: Subtypes must be substitutable
- **I**nterface Segregation: Small, focused interfaces
- **D**ependency Inversion: Depend on abstractions

### Error Handling
```
- Handle ALL error cases explicitly
- Fail fast with clear error messages
- Log errors with context for debugging
- Don't swallow exceptions silently
```

## Git Commit Format

```
type(scope): brief description

- Detail about what changed
- Why it was changed
- Any breaking changes
```

**Types**: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`

## Context Management

### When to /compact
- After completing a major milestone
- Before starting unrelated work
- When context exceeds ~50% (feeling sluggish)
- After 15+ tool calls in a session

### When to Delegate to Subagents
- Independent analysis tasks
- Parallel work opportunities
- Specialized reviews (security, docs)
- Tasks that would clutter main context

## Response Format

### TLDR (Always Include for Plans)
```
## TLDR
- **Problem**: [one sentence]
- **Solution**: [one sentence]
- **Steps**: [3-7 items]
- **Validation**: [how we verify]
```

### Completion Report
```
## Complete

### Summary
[What was done]

### Validation
- Tests: ✅/❌
- Lint: ✅/❌
- Environment: ✅/❌

### Commit
[hash and message]
```

## Anti-Patterns (Never Do These)

❌ Implement without investigating first
❌ Fix symptoms instead of root causes
❌ Skip validation ("it should work")
❌ Mark complete before tests pass
❌ Leave TODO placeholders in plans
❌ Make assumptions without verification
❌ Edit directly on main/master branch
