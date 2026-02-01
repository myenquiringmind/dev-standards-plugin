# Maintaining the Dev Standards Plugin

This guide explains how to improve, update, and maintain the plugin over time.

## Quick Reference

| To Add | Location | Example |
|--------|----------|---------|
| Automatic behavior | `hooks/hooks.json` | Auto-format, type check |
| Workflow command | `commands/*.md` | `/typecheck`, `/deploy` |
| Specialized worker | `agents/*.md` | `@security-reviewer` |
| Domain knowledge | `skills/*/SKILL.md` | Testing patterns |

## Workflow for Changes

### 1. Make Changes Locally

```bash
cd /path/to/dev-standards-plugin

# Create a branch for your changes
git checkout -b feature/add-logging

# Make your changes
# ... edit files ...

# Test in a real project (see Testing section below)
```

### 2. Update Version & Changelog

Edit `hooks/hooks.json` `_meta` section:
```json
{
  "_meta": {
    "version": "1.2.0",
    "changelog": [
      "1.0.0 - Initial release",
      "1.1.0 - Added type checking",
      "1.2.0 - Your new feature"
    ]
  }
}
```

Update `CHANGELOG.md` with details.

### 3. Test Changes

```bash
# In a test project
cd /path/to/test-project

# Reinstall plugin
/plugin uninstall dev-standards@your-org-standards
/plugin install dev-standards@your-org-standards

# Or for local testing, symlink directly
ln -sf /path/to/dev-standards-plugin/.claude/* .claude/
```

### 4. Push & Release

```bash
git add .
git commit -m "feat: add logging hooks"
git push origin feature/add-logging

# Create PR, review, merge to main
# Projects update with: /plugin update dev-standards@your-org-standards
```

## Adding New Features

### Adding a Hook

Edit `hooks/hooks.json`:

```json
{
  "PostToolUse": [
    // ... existing hooks ...
    {
      "matcher": "Write",
      "hooks": [
        {
          "type": "command",
          "command": "your-script-here.sh",
          "timeout": 10
        }
      ],
      "description": "What this hook does"
    }
  ]
}
```

**Hook Types:**
- `command` - Run a shell command
- `prompt` - Ask Claude to evaluate something

**Hook Events:**
- `SessionStart` - Session begins
- `UserPromptSubmit` - User sends a message
- `PreToolUse` - Before tool runs (can block)
- `PostToolUse` - After tool runs
- `Stop` - Claude finishes responding
- `SubagentStop` - Subagent finishes
- `PreCompact` - Before context compaction

### Adding a Command

Create `commands/your-command.md`:

```markdown
# Your Command Name

Brief description of what this command does.

## Instructions

[What Claude should do when this command is invoked]

## Output Format

[Expected output structure]
```

Update `plugin.json` to register it:
```json
{
  "components": {
    "commands": [
      "commands/your-command.md"
    ]
  }
}
```

### Adding an Agent

Create `agents/your-agent.md`:

```markdown
# Your Agent Name

You are a specialized agent for [purpose].

## Responsibilities
- [What it does]

## Output Format
[Expected output structure]

## Constraints
- [Boundaries]
```

Update `plugin.json`:
```json
{
  "components": {
    "agents": [
      "agents/your-agent.md"
    ]
  }
}
```

### Adding a Skill

Create `skills/your-skill/SKILL.md`:

```markdown
---
name: your-skill
description: |
  When this skill triggers and what it provides.
  Include trigger keywords.
---

# Skill Name

[Instructions and domain knowledge]
```

Update `plugin.json`:
```json
{
  "components": {
    "skills": [
      "skills/your-skill"
    ]
  }
}
```

## Testing Changes

### Manual Testing

1. Install plugin in a test project
2. Trigger the feature you're testing
3. Verify expected behavior

### Testing Hooks

```bash
# Check hook is registered
cat .claude/settings.json | jq '.hooks'

# Watch log output during hook execution
tail -f ~/.claude/logs/session.log
```

### Testing Commands

```
# In Claude Code
/your-command

# Verify output matches expected format
```

### Testing Agents

```
# In Claude Code
Ask Claude: "Delegate this task to @your-agent"

# Verify agent behavior
```

## Common Patterns

### Hook: Run Script and Report Errors

```json
{
  "type": "command",
  "command": "bash -c 'output=$(your-check.sh 2>&1); if [ $? -ne 0 ]; then echo \"[Check Failed] $output\" >&2; fi'",
  "timeout": 10
}
```

### Hook: Block Based on Condition

```json
{
  "type": "command", 
  "command": "bash -c 'if [[ condition ]]; then echo \"{\\\"decision\\\":\\\"block\\\",\\\"reason\\\":\\\"Why blocked\\\"}\" && exit 0; fi'"
}
```

### Hook: Modify Tool Input (PreToolUse only)

```json
{
  "type": "command",
  "command": "node -e \"let d='';process.stdin.on('data',c=>d+=c);process.stdin.on('end',()=>{const i=JSON.parse(d);i.tool_input.modified=true;console.log(JSON.stringify(i))})\""
}
```

## Troubleshooting

### Hook Not Firing

1. Check matcher regex: `"matcher": "Edit|Write"` must match tool name
2. Check JSON syntax: Validate `hooks.json` is valid JSON
3. Check timeout: Increase if hook needs more time
4. Check logs: `tail ~/.claude/logs/session.log`

### Command Not Found

1. Verify file exists in `commands/`
2. Verify registered in `plugin.json`
3. Reinstall plugin: `/plugin uninstall` then `/plugin install`

### Agent Not Working

1. Remember: Agent file content is a **system prompt**, not user prompt
2. Use `@agent-name` syntax to invoke
3. Agent must be registered in `plugin.json`

## Ideas for Future Improvements

- [ ] Security scanning (detect hardcoded secrets)
- [ ] Dependency vulnerability checking
- [ ] Performance profiling hooks
- [ ] Custom project templates
- [ ] Integration test runner
- [ ] Deployment automation
- [ ] Code coverage tracking
- [ ] Metrics dashboard
