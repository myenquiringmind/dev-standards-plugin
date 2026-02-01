# Review Command

Perform a comprehensive code review of recent changes or specified files.

## Usage

- `/review` - Review uncommitted changes
- `/review [files]` - Review specific files
- `/review --branch [name]` - Review changes from branch

## Workflow

### 1. Identify Scope
```bash
# Uncommitted changes
git diff --name-only

# Or changes from branch
git diff main...HEAD --name-only
```

### 2. Delegate Review
Delegate to `@code-reviewer` agent with the identified files.

### 3. Optional: Request Tests
If coverage gaps found, delegate to `@test-writer` for test suggestions.

### 4. Summarize Findings

```markdown
## Code Review Summary

### Scope
- Files reviewed: X
- Lines changed: +Y / -Z

### Verdict: [APPROVED | NEEDS_CHANGES]

### Action Items
#### Must Fix (blocking)
- [ ] [issue] in `file:line`

#### Should Fix (non-blocking)
- [ ] [issue] in `file:line`

### Test Coverage
- [assessment of test coverage for changes]

### Ready to Merge: [Yes / No - reasons]
```

## When to Use

- Before creating a PR
- After completing a feature
- When reviewing someone else's code
- Periodic codebase health checks
