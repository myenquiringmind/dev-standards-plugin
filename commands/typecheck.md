# Typecheck Command

Run comprehensive type checking and linting across the project.

## What This Does

1. **Detect project type** (TypeScript, Python, Go, etc.)
2. **Run appropriate type checker**
3. **Run linter**
4. **Report all issues**

## Checks by Language

### TypeScript/JavaScript
```bash
# Type checking
npx tsc --noEmit

# Linting
npx eslint . --ext .js,.jsx,.ts,.tsx
```

### Python
```bash
# Type checking
mypy . --ignore-missing-imports

# Linting  
ruff check .

# Or fallback
pylint **/*.py
```

### Go
```bash
# Type checking (part of build)
go build ./...

# Linting
golangci-lint run
```

### Rust
```bash
# Type checking
cargo check

# Linting
cargo clippy
```

## Output Format

```markdown
## Type & Lint Report

### Type Errors
| File | Line | Error |
|------|------|-------|
| `path` | X | [error message] |

### Lint Warnings
| File | Line | Rule | Message |
|------|------|------|---------|
| `path` | X | [rule] | [message] |

### Summary
- Type errors: X
- Lint errors: Y
- Lint warnings: Z

### Status: [CLEAN | HAS_ISSUES]
```

## Quick Fixes

After running, offer to fix auto-fixable issues:

```bash
# ESLint auto-fix
npx eslint . --fix

# Ruff auto-fix
ruff check . --fix

# Prettier format
npx prettier --write .
```

## Usage

- `/typecheck` - Check entire project
- `/typecheck src/` - Check specific directory
- `/typecheck --fix` - Check and auto-fix where possible
