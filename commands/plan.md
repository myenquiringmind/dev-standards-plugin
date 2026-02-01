# Plan Command

Create a comprehensive, validated implementation plan.

## Output Structure

### TLDR (Required - Always First)

```markdown
## TLDR
- **Problem**: [one sentence]
- **Solution**: [one sentence]
- **Steps**:
  1. [step]
  2. [step]
  3. [step]
- **Validation**: [how we verify success]
- **Risk**: [main risk + mitigation]
```

### Verbose Plan (For Complex Tasks)

```markdown
## Detailed Plan

### 1. Investigation Summary
[What was found during analysis]

### 2. Root Cause / Requirements
[The actual problem or need being addressed]

### 3. Implementation Steps
1. **[Step Name]**
   - Files: `path/to/file.ext`
   - Changes: [specific modifications]
   - Commands: `command to run`

2. **[Step Name]**
   ...

### 4. Testing Strategy
- Unit tests: [what to test]
- Integration tests: [what to test]
- Manual verification: [steps]

### 5. Environment Considerations
- Container rebuild required: [yes/no]
- Services to restart: [list]
- Config changes: [list]

### 6. Rollback Plan
[How to revert if something goes wrong]

### 7. Validation Checklist
- [ ] [specific check]
- [ ] [specific check]
- [ ] [specific check]
```

## Before Finalizing

Verify the plan is:
- [ ] **Implementable**: No vague or hand-wavy steps
- [ ] **Specific**: Real files, commands, and values referenced
- [ ] **Complete**: No TODO placeholders or assumptions
- [ ] **Validated**: Project structure actually supports the plan

⚠️ Do NOT output plans with unverified assumptions. Check the codebase first.
