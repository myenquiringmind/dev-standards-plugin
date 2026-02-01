# Fix Command

Execute a complete bug fix workflow with investigation, implementation, and validation.

## Workflow Phases

### Phase 1: Investigation
```
Delegate to @investigator if complex, otherwise:
1. Reproduce the issue
2. Read relevant code, logs, config
3. Identify root cause (not just symptoms)
4. Document findings
```

### Phase 2: Planning
```
1. Use /plan to create implementation plan
2. Identify all affected files
3. Consider side effects and regressions
4. Plan test coverage for the fix
```

### Phase 3: Implementation
```
1. Create feature branch if on main/master
2. Implement fix following DRY/SOLID
3. Add/update tests (delegate @test-writer if extensive)
4. Update documentation if needed
5. Run linter and fix any issues
```

### Phase 4: Validation
```
1. Run full test suite → must pass
2. Run linter → must be clean
3. Verify fix resolves original issue
4. Check for regressions in related areas
5. Verify changes are active in target environment
```

### Phase 5: Commit
```
1. Stage changes: git add -A
2. Commit with descriptive message:
   fix(scope): brief description

   - What was broken
   - What caused it
   - How it was fixed
```

## Completion Report

```markdown
## Fix Complete

### Summary
[What was fixed and how]

### Root Cause
[What was actually wrong]

### Changes
| File | Change |
|------|--------|
| `path` | [modification] |

### Validation
- Tests: ✅ X/Y passing
- Lint: ✅ Clean
- Manual: ✅ [verification performed]

### Commit
`abc1234` fix(scope): description
```

## Important Rules

- ❌ Do NOT mark complete until validation passes
- ❌ Do NOT skip the investigation phase
- ✅ Use /compact after completion if context is cluttered
- ✅ Delegate to subagents for parallel work
