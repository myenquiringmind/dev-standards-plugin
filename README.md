# Dev Standards Plugin for Claude Code

Enforce consistent development standards across all your projects with automated hooks, specialized agents, workflow commands, and best-practice skills.

## TLDR

```bash
# Add this repo as a marketplace (one-time)
/plugin marketplace add myenquiringmind/dev-standards-plugin

# Install in any project
/plugin install dev-standards@myenquiringmind

# That's it! Standards now enforced automatically.
```

## What You Get

### Automatic Hooks
| Hook | What It Does |
|------|--------------|
| SessionStart | Loads git status + TODO context, logs session, **checks for updates** |
| UserPromptSubmit | Logs prompts for session history |
| PreToolUse | Blocks dangerous commands, protects main branch |
| PostToolUse | Auto-formats, **type checks**, **lints**, logs activity, **venv-aware** |
| Stop | Validation checkpoint (tests, types, lint) |
| SubagentStop | Ensures subagents provide summaries |

### Python Venv Support
- **Auto-creates** `.venv` on first Python file edit
- Uses **uv** (preferred) or `python -m venv` (fallback)
- **Auto-installs** plugin tools (ruff, mypy) into project venv
- All Python hooks run through the project's venv

### Specialized Agents
| Agent | Purpose | Invoke |
|-------|---------|--------|
| `@investigator` | Deep root cause analysis | Complex bugs |
| `@code-reviewer` | Quality & security review | Before commits |
| `@test-writer` | Comprehensive test coverage | New features |
| `@doc-writer` | Documentation updates | API changes |

### Workflow Commands
| Command | Purpose |
|---------|---------|
| `/plan` | Create structured implementation plan with TLDR |
| `/fix` | Complete bug fix workflow |
| `/validate` | Comprehensive validation checklist |
| `/review` | Code review with quality gates |
| `/setup` | Initialize project configuration |
| `/typecheck` | On-demand type checking + linting |
| `/logs` | View session activity and history |

### Skills
| Skill | Triggers On |
|-------|-------------|
| `dev-workflow` | Any code task - features, fixes, refactoring |

## Installation

### Option 1: Claude Code Plugin (Recommended)

**Step 1**: Host this repo on GitHub (public or private)

```bash
# Fork or clone this repo
git clone https://github.com/myenquiringmind/dev-standards-plugin
cd dev-standards-plugin

# Customize if needed, then push to your org
git remote set-url origin https://github.com/YOUR_ORG/dev-standards-plugin
git push -u origin main
```

**Step 2**: Add as marketplace in Claude Code

```
/plugin marketplace add YOUR_ORG/dev-standards-plugin
```

**Step 3**: Install in any project

```
/plugin install dev-standards@myenquiringmind
```

### Option 2: Git Submodule (Alternative)

**macOS/Linux:**
```bash
# Add as submodule
git submodule add https://github.com/myenquiringmind/dev-standards-plugin .claude-standards

# Symlink components
ln -s .claude-standards/hooks/hooks.json .claude/hooks.json
ln -s .claude-standards/agents .claude/agents
ln -s .claude-standards/commands .claude/commands
ln -s .claude-standards/skills .claude/skills
```

**Windows (PowerShell):**
```powershell
# Add as submodule
git submodule add https://github.com/myenquiringmind/dev-standards-plugin .claude-standards

# Copy components (symlinks require admin on Windows)
Copy-Item .claude-standards\hooks\hooks.json .claude\hooks.json
Copy-Item -Recurse .claude-standards\agents .claude\agents
Copy-Item -Recurse .claude-standards\commands .claude\commands
Copy-Item -Recurse .claude-standards\skills .claude\skills
```

### Option 3: Direct Copy

**macOS/Linux:**
```bash
# Clone and copy
git clone https://github.com/myenquiringmind/dev-standards-plugin /tmp/standards
cp -r /tmp/standards/hooks /tmp/standards/agents /tmp/standards/commands /tmp/standards/skills .claude/
```

**Windows (PowerShell):**
```powershell
# Clone and copy
git clone https://github.com/myenquiringmind/dev-standards-plugin $env:TEMP\standards
Copy-Item -Recurse "$env:TEMP\standards\hooks","$env:TEMP\standards\agents","$env:TEMP\standards\commands","$env:TEMP\standards\skills" .\.claude\
```

## Cross-Platform Support

This plugin is fully cross-platform and works on:
- **Windows** (PowerShell, CMD)
- **macOS** (zsh, bash)
- **Linux** (bash, zsh)

All hooks use Node.js for cross-platform compatibility. No bash-specific commands are used.

## Usage

Once installed, standards are enforced automatically. Here's how the workflow looks:

### Example: Fixing a Bug

```
You: "The login is timing out after 30 seconds"

Claude:
1. [SessionStart hook loads git status]
2. [dev-workflow skill activates]
3. "I'll investigate this. Delegating to @investigator..."

@investigator:
4. Reproduces issue
5. Traces to auth service
6. Returns: "Root cause: Token refresh not awaited"

Claude:
7. Creates /plan with TLDR
8. Implements fix on feature branch
9. [PostToolUse hook auto-formats]
10. Delegates to @test-writer for coverage
11. Runs /validate
12. [Stop hook verifies all checks pass]
13. Commits: "fix(auth): await token refresh before timeout check"
```

### Example: New Feature

```
You: "Add rate limiting to the API"

Claude:
1. /plan with TLDR + detailed steps
2. Implements incrementally
3. @test-writer creates test coverage
4. @code-reviewer checks for issues
5. /validate ensures everything works
6. Commits with feat(api): add rate limiting
```

## Customization

### Adding Project-Specific Standards

Create a `CLAUDE.md` in your project root:

```markdown
# MyProject

## Quick Reference
- **Test**: `npm run test`
- **Lint**: `npm run lint`
- **Build**: `npm run build`

## Project-Specific Rules
- Always use TypeScript strict mode
- API responses must use the ResponseWrapper type
- Database queries must use the query builder, never raw SQL
```

### Modifying Hooks

Edit `hooks/hooks.json` or create `.claude/settings.local.json` for project-specific overrides:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "your-custom-formatter.sh",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

### Configuring Protected Branches

Edit `config/defaults.json` to customize protected branches:

```json
{
  "protectedBranches": ["main", "master", "production", "release/*"]
}
```

### Adding Custom Agents

Create `.claude/agents/your-agent.md`:

```markdown
# Your Agent Name

You are specialized for [purpose].

## Responsibilities
- [what it does]

## Output Format
[expected output]
```

## Architecture

```
dev-standards-plugin/
├── .claude-plugin/
│   ├── plugin.json          # Plugin manifest (v1.2.0)
│   └── marketplace.json     # Marketplace catalog
├── config/
│   └── defaults.json        # Configurable defaults
├── hooks/
│   └── hooks.json           # Automatic enforcement (format, type, lint, log)
├── lib/
│   ├── utils.js             # Shared utilities (venv, git, tools)
│   ├── venv.js              # Venv-specific utilities
│   └── hook-runner.js       # Unified hook entry point
├── agents/
│   ├── investigator.md      # Root cause analysis
│   ├── code-reviewer.md     # Quality review
│   ├── test-writer.md       # Test creation
│   └── doc-writer.md        # Documentation
├── commands/
│   ├── plan.md              # /plan
│   ├── fix.md               # /fix
│   ├── validate.md          # /validate
│   ├── review.md            # /review
│   ├── setup.md             # /setup
│   ├── typecheck.md         # /typecheck
│   └── logs.md              # /logs
├── skills/
│   └── dev-workflow/
│       └── SKILL.md         # Core workflow skill
├── templates/
│   └── CLAUDE.md.template   # Project starter template
├── tests/
│   ├── hooks.test.js        # Structure & schema tests (50 tests)
│   ├── test-venv.js         # Venv utilities tests (25 tests)
│   ├── test-content.js      # Content validation tests (46 tests)
│   └── test-hooks-live.js   # Live functional tests (19 tests)
├── schemas/
│   └── hooks.schema.json    # JSON Schema for validation
├── scripts/
│   └── validate-hooks.js    # Hook validation script
├── CHANGELOG.md             # Version history
├── CONTRIBUTING.md          # Maintenance guide
├── LICENSE                  # MIT License
└── README.md
```

## Testing the Plugin

Run the full test suite (140 tests):

```bash
node tests/hooks.test.js      # Structure & schema (50 tests)
node tests/test-venv.js       # Venv utilities (25 tests)
node tests/test-content.js    # Content validation (46 tests)
node tests/test-hooks-live.js # Live functional (19 tests)
```

Validate hooks.json schema:

```bash
node scripts/validate-hooks.js
```

## Update Checking

The plugin automatically checks for updates on session start:
- Queries GitHub releases (non-blocking, cached for 24 hours)
- If a newer version is available, displays a notice:
  ```
  [dev-standards] Update available: 1.2.0 -> 1.3.0 (https://github.com/myenquiringmind/dev-standards-plugin/releases)
  ```
- Never blocks or interrupts your workflow

To manually update:
```bash
cd /path/to/plugin
git pull origin main
```

## Why This Approach Works

1. **Automatic Enforcement**: Hooks run without you asking - no forgotten standards
2. **Parallel Work**: Subagents handle independent tasks without polluting context
3. **Consistent Workflows**: Commands ensure the same quality process every time
4. **Shared Knowledge**: Skills carry domain expertise across sessions
5. **Easy Distribution**: Plugin system makes it one command to install anywhere
6. **Cross-Platform**: Works on Windows, macOS, and Linux
7. **Self-Updating Awareness**: Notifies you when updates are available

## Contributing

1. Fork the repo
2. Make your changes
3. Run `node tests/hooks.test.js` to verify
4. Submit a PR

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

## License

MIT - Use freely, attribution appreciated. See [LICENSE](LICENSE) for details.
