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

#### Core Agents
| Agent | Purpose | When to Use |
|-------|---------|-------------|
| `@investigator` | Deep root cause analysis | Complex bugs, unknown failures |
| `@code-reviewer` | Quality & security review | Before commits, PR reviews |
| `@doc-writer` | Documentation updates | API changes, new features |

#### Domain Standards Agents (v1.3.0+)
| Agent | Domain | Expertise |
|-------|--------|-----------|
| `@standards-orchestrator` | Workflow | Coordinates domain agents through phases |
| `@logging-standards` | Logging | Structured logging, log levels, debug mode |
| `@error-standards` | Errors | Exception handling, error types, recovery |
| `@type-standards` | Types | JSDoc types, TypeScript, mypy |
| `@lint-standards` | Linting | ESLint, ruff, code style, auto-fix |
| `@test-standards` | Testing | Unit/integration tests, coverage, mocking |
| `@validation-standards` | Validation | Input validation, sanitization, security |
| `@git-standards` | Git | Conventional commits, branch naming, .gitignore |
| `@housekeeping-standards` | Hygiene | Project layout, temp dirs, cleanup |
| `@naming-standards` | Naming | File/function/class naming conventions |

> **Note**: `@test-writer` was merged into `@test-standards` in v1.3.0

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
| `orchestrate` | Standards enforcement via `/orchestrate domain=<domain>` |

## Orchestrator Workflow (v1.3.0+)

The orchestrator provides systematic standards enforcement with checkpoints and handoffs.

### Invocation

```bash
/orchestrate domain=git           # Single domain
/orchestrate domain=all           # All domains (dependency-sorted)
/orchestrate domain=logging phase=design  # Start from specific phase
```

### Workflow Phases

```
Design → Validate Design → Build → Test → Validate
```

| Phase | Purpose |
|-------|---------|
| **Design** | Analyze current state, propose improvements |
| **Validate Design** | Review proposal for completeness and conflicts |
| **Build** | Implement the approved design |
| **Test** | Write and run tests for implementation |
| **Validate** | Final verification that everything works |

### Checkpoint Protocol

After **design** and **build** phases, execution pauses for user approval:

- **Approve**: Type `approve`, `yes`, `proceed`, or `lgtm` to continue
- **Modify**: Provide feedback to re-run the current phase
- **Reject**: Type `reject` or `rollback` to stop execution

### Git Integration (v1.4.0)

When the orchestrator runs:

1. **Branch Creation**: Auto-creates `feat/orchestrator-<domain>-<timestamp>`
2. **Phase Commits**: Each phase completion triggers a commit
3. **Rollback Points**: Checkpoints create rollback commits
4. **PR Finalization**: Option to create PR on completion

```bash
/orchestrate domain=git gitMode=auto     # Default - automatic commits
/orchestrate domain=git gitMode=manual   # Manual commit control
/orchestrate domain=git gitMode=disabled # No git operations
```

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
10. Delegates to @test-standards for coverage
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
3. @test-standards creates test coverage
4. @code-reviewer checks for issues
5. /validate ensures everything works
6. Commits with feat(api): add rate limiting
```

### Example: Using the Orchestrator

```
You: "/orchestrate domain=git"

Claude:
1. [Creates branch feat/orchestrator-git-1738600000]
2. [Enters DESIGN phase]
3. Analyzes current git standards...

## Checkpoint: Design Complete
**Agent**: @git-standards
**Status**: Awaiting approval

### Changes Proposed
- Add conventional commit validation
- Update .gitignore with security patterns

User Action Required:
- Approve and proceed
- Request modifications
- Reject and rollback

You: "approve"

Claude:
4. [Commits design, advances to validate-design]
5. [Continues through Build → Test → Validate]
6. [Final commit and optional PR creation]
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
│   ├── plugin.json          # Plugin manifest (v1.4.0)
│   └── marketplace.json     # Marketplace catalog
├── config/
│   └── defaults.json        # Protected branches, formatters, linters
├── hooks/
│   └── hooks.json           # Automatic enforcement (9 hook types)
├── lib/
│   ├── core/                # Platform detection, config, execution
│   │   ├── index.js, platform.js, config.js, exec.js
│   ├── venv/                # Virtual environment management
│   ├── git/                 # Git operations (branch, commit, PR)
│   ├── logging/             # Session logging, debug support
│   ├── validation/          # Input validation, security
│   ├── tools/               # Formatter/linter/typechecker execution
│   ├── version/             # Version checking, cache management
│   ├── errors/              # Standardized error handling
│   ├── orchestrator/        # Orchestrator runtime (v1.3.0+)
│   │   ├── index.js         # State machine, phase management
│   │   ├── checkpoint.js    # User approval protocol
│   │   ├── handoff.js       # Agent handoff tracking
│   │   ├── cli.js           # CLI commands
│   │   └── parser.js        # Parameter parsing
│   ├── hook-runner.js       # Unified hook entry point
│   └── utils.js             # Backward-compatible exports
├── agents/
│   ├── standards-orchestrator.md  # Workflow coordinator
│   ├── investigator.md, code-reviewer.md, doc-writer.md
│   ├── logging-standards.md, error-standards.md
│   ├── type-standards.md, lint-standards.md, test-standards.md
│   ├── validation-standards.md, git-standards.md
│   ├── housekeeping-standards.md, naming-standards.md
├── commands/
│   ├── plan.md, fix.md, validate.md, review.md
│   ├── setup.md, typecheck.md, logs.md
├── skills/
│   ├── dev-workflow/SKILL.md
│   └── orchestrate/SKILL.md      # Orchestrator skill (v1.3.0+)
├── templates/, tests/, schemas/, scripts/
├── CHANGELOG.md, CONTRIBUTING.md, LICENSE, README.md
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
  [dev-standards] Update available: 1.3.0 -> 1.4.0 (https://github.com/myenquiringmind/dev-standards-plugin/releases)
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
8. **Systematic Standards**: Orchestrator ensures all quality domains are addressed with checkpoints

## Contributing

1. Fork the repo
2. Make your changes
3. Run `node tests/hooks.test.js` to verify
4. Submit a PR

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

## License

MIT - Use freely, attribution appreciated. See [LICENSE](LICENSE) for details.
