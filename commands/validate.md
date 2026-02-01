# Validate Command

Perform comprehensive validation that changes are correct and active.

## Validation Checklist

### 1. Code Quality
```bash
# Run linter (detect which one is configured)
npm run lint || yarn lint || pnpm lint ||
ruff check . || pylint . ||
golangci-lint run ||
cargo clippy
```
- [ ] Linter passes with no errors
- [ ] No type errors (TypeScript/mypy/etc.)
- [ ] No debug statements left (console.log, print, etc.)

### 2. Tests
```bash
# Run tests (detect which framework)
npm test || yarn test || pnpm test ||
pytest || python -m pytest ||
go test ./... ||
cargo test
```
- [ ] All existing tests pass
- [ ] New code has test coverage
- [ ] Tests are meaningful (not just coverage theater)

### 3. Functionality
- [ ] Feature/fix works as specified
- [ ] Edge cases handled
- [ ] Error cases handled gracefully
- [ ] No regressions in related functionality

### 4. Environment
- [ ] Changes work in target environment (not just locally)
- [ ] Container rebuilt if Dockerfile changed
- [ ] Services restarted if config changed
- [ ] Database migrations applied if needed

### 5. Documentation
- [ ] Code is self-documenting or has comments
- [ ] README updated if user-facing changes
- [ ] API docs updated if endpoints changed

## Output Format

```markdown
## Validation Report

| Check | Status | Details |
|-------|--------|---------|
| Lint | ✅/❌ | [output summary] |
| Tests | ✅/❌ | X/Y passing |
| Functionality | ✅/❌ | [verification method] |
| Environment | ✅/❌ | [what was checked] |
| Documentation | ✅/❌ | [status] |

### Issues Found
1. [issue and recommended action]

### Overall: [VALID | NEEDS_ATTENTION | BLOCKED]
```

## Important

⚠️ Actually RUN the commands - do not assume things pass.
⚠️ Check the target environment - "works locally" is not sufficient.
