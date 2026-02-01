# Setup Command

Initialize or verify project configuration for dev-standards plugin.

## What This Does

1. **Detects project type** (Python, Node.js, Go, Rust)
2. **Creates/verifies venv** for Python projects (using uv if available)
3. **Installs plugin dependencies** (ruff, mypy for Python; prettier, eslint for JS/TS)
4. **Creates CLAUDE.md** if missing (project memory)
5. **Verifies tooling** is available

## Venv Setup (Python Projects)

For Python projects, this command will:

1. Check if `.venv`, `venv`, or `.uv` exists
2. If not, create `.venv` using:
   - `uv venv` (preferred, if uv is installed)
   - `python -m venv` (fallback)
3. Install plugin dependencies into the venv:
   - `ruff` (formatter + linter)
   - `mypy` (type checker)

```bash
# What happens under the hood:
uv venv .venv                    # Create venv
uv pip install ruff mypy         # Install deps
```

## Node.js Setup

For Node.js/TypeScript projects:

```bash
# Installs dev dependencies if not present:
npm install --save-dev prettier eslint typescript
```

## Project Detection

```
Detect and configure based on:
- pyproject.toml / requirements.txt / *.py → Python project
- package.json → Node.js/TypeScript project
- go.mod → Go project
- Cargo.toml → Rust project
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

## Venv
- Location: `.venv/`
- Created with: [uv/python -m venv]
- Dependencies: ruff, mypy

## Key Conventions
- [coding conventions used]
- [naming conventions]
```

## Output

```markdown
## Project Setup Complete

### Detected Stack
- Language: Python
- Package Manager: uv (or pip)
- Venv: .venv/ (created/existing)

### Plugin Dependencies
| Tool | Version | Status |
|------|---------|--------|
| ruff | X.Y.Z | ✅ Installed |
| mypy | X.Y.Z | ✅ Installed |

### Project Dependencies
| Tool | Command | Status |
|------|---------|--------|
| Formatter | `ruff format` | ✅ |
| Linter | `ruff check` | ✅ |
| Type Checker | `mypy` | ✅ |
| Tests | `pytest` | ⚠️ Not detected |

### Files Created
- `.venv/` - Python virtual environment
- `CLAUDE.md` - Project configuration

### Next Steps
- Add `pytest` for testing: `uv pip install pytest`
- Run `/validate` to check project health
```

## Usage

```
/setup                    # Auto-detect and configure
/setup --python           # Force Python project setup
/setup --node             # Force Node.js project setup
/setup --no-venv          # Skip venv creation
```

## Notes

- The venv is created in the project root as `.venv/`
- All Python hooks automatically use this venv
- If uv is not installed, falls back to pip
- Existing venvs are detected and reused
