# Setup Command

Initialize or verify project configuration for dev-standards plugin.

## What This Does

1. **Checks project structure** for required config
2. **Creates CLAUDE.md** if missing (project memory)
3. **Detects tech stack** and configures appropriate tools
4. **Verifies tooling** is available (linters, test runners, formatters)

## Project Detection

```
Detect and configure based on:
- package.json → Node.js/TypeScript project
- pyproject.toml / requirements.txt → Python project
- go.mod → Go project
- Cargo.toml → Rust project
- Dockerfile → Container-based deployment
```

## CLAUDE.md Template

If CLAUDE.md doesn't exist, create one:

```markdown
# [Project Name]

## Quick Reference
- **Test**: [detected test command]
- **Lint**: [detected lint command]
- **Format**: [detected format command]
- **Build**: [detected build command]

## Project Structure
- `src/` - [description]
- `tests/` - [description]

## Key Conventions
- [coding conventions used]
- [naming conventions]
- [architectural patterns]

## Common Tasks
- [how to add a new feature]
- [how to run locally]
- [how to deploy]
```

## Output

```markdown
## Project Setup Complete

### Detected Stack
- Language: [language]
- Framework: [framework if any]
- Package Manager: [npm/yarn/pip/etc.]

### Configuration
| Tool | Command | Status |
|------|---------|--------|
| Linter | `[cmd]` | ✅/❌ |
| Tests | `[cmd]` | ✅/❌ |
| Formatter | `[cmd]` | ✅/❌ |

### Files Created
- [list of created files]

### Recommendations
- [any missing tools or config to add]
```

## Usage

Run `/setup` in any project to:
- Bootstrap CLAUDE.md with detected config
- Verify dev tools are available
- Get recommendations for missing tooling
