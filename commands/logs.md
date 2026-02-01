# Logs Command

View Claude Code session logs and activity history.

## Log Location

Logs are stored in the `.claude/logs` directory under your home folder:

| Platform | Path |
|----------|------|
| Windows | `%USERPROFILE%\.claude\logs\session.log` |
| macOS/Linux | `~/.claude/logs/session.log` |

## Log File

The hooks create a single consolidated log file:
- `session.log` - All events: session starts, prompts, tool completions, task completions, compactions

## Usage

### View Recent Activity

**Windows (PowerShell)**:
```powershell
# Last 20 log entries
Get-Content "$env:USERPROFILE\.claude\logs\session.log" -Tail 20

# Today's activity
Get-Content "$env:USERPROFILE\.claude\logs\session.log" | Select-String (Get-Date -Format "yyyy-MM-dd")
```

**macOS/Linux**:
```bash
# Last 20 log entries
tail -20 ~/.claude/logs/session.log

# Today's activity
grep "$(date +%Y-%m-%d)" ~/.claude/logs/session.log
```

### View by Event Type

**Windows (PowerShell)**:
```powershell
# All session starts
Get-Content "$env:USERPROFILE\.claude\logs\session.log" | Select-String "SESSION_START"

# All task completions
Get-Content "$env:USERPROFILE\.claude\logs\session.log" | Select-String "TASK_COMPLETE"

# All compactions
Get-Content "$env:USERPROFILE\.claude\logs\session.log" | Select-String "COMPACT"

# All prompts
Get-Content "$env:USERPROFILE\.claude\logs\session.log" | Select-String "PROMPT"
```

**macOS/Linux**:
```bash
grep "SESSION_START" ~/.claude/logs/session.log
grep "TASK_COMPLETE" ~/.claude/logs/session.log
grep "COMPACT" ~/.claude/logs/session.log
grep "PROMPT" ~/.claude/logs/session.log
```

### View by Project

**Windows (PowerShell)**:
```powershell
Get-Content "$env:USERPROFILE\.claude\logs\session.log" | Select-String "C:\\path\\to\\project"
```

**macOS/Linux**:
```bash
grep "/path/to/project" ~/.claude/logs/session.log
```

## Output Format

```markdown
## Session Log

### Recent Activity (last 24h)
| Time | Event | Location |
|------|-------|----------|
| [timestamp] | SESSION_START | [path] |
| [timestamp] | PROMPT | |
| [timestamp] | TOOL_COMPLETE | |
| [timestamp] | TASK_COMPLETE | |

### Summary
- Sessions started: X
- Prompts submitted: Y
- Tasks completed: Z
- Compactions: N

### Projects Worked On
- /path/to/project1 (X sessions)
- /path/to/project2 (Y sessions)
```

## Log Event Types

| Event | Description | When Logged |
|-------|-------------|-------------|
| `SESSION_START` | New Claude Code session | SessionStart hook |
| `PROMPT` | User submitted a prompt | UserPromptSubmit hook |
| `TOOL_COMPLETE` | Tool finished executing | PostToolUse hook |
| `TASK_COMPLETE` | Claude finished responding | Stop hook |
| `COMPACT` | Context was compacted | PreCompact hook |

## Log Management

### Archive/Clear Logs

**Windows (PowerShell)**:
```powershell
$logPath = "$env:USERPROFILE\.claude\logs\session.log"
if (Test-Path $logPath) {
    # Archive current log
    $archivePath = "$env:USERPROFILE\.claude\logs\session-$(Get-Date -Format 'yyyy-MM-dd').log.bak"
    Move-Item $logPath $archivePath -Force
}
```

**macOS/Linux**:
```bash
# Keep last 7 days
find ~/.claude/logs -name "*.log" -mtime +7 -delete

# Rotate current log
mv ~/.claude/logs/session.log ~/.claude/logs/session.log.bak
```

### Disable Logging

To disable logging, remove or comment out the logging hooks in your hooks configuration.
The logging hooks are:
- SessionStart (SESSION_START logging)
- UserPromptSubmit (PROMPT logging)
- PostToolUse (TOOL_COMPLETE logging)
- Stop (TASK_COMPLETE logging)
- PreCompact (COMPACT logging)

## Privacy Note

Logs are stored locally on your machine and are not sent anywhere.
Log entries contain timestamps, event types, and working directory paths.
They do not contain the content of your prompts or Claude's responses.
