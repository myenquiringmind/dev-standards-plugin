# Wiring up the statusline

`hooks/statusline.py` writes the framework's context-percentage cache to `.claude/.context_pct` and prints a one-line status string to your terminal. Both outputs are Phase 1 infrastructure — `context_budget.py` reads the cache; the terminal line makes your current context usage visible without waiting for CC's own banner.

Plugins cannot ship a top-level `statusLine` configuration (only `agent` and `subagentStatusLine` are plugin-shippable per the CC docs). So the wiring is a user-side step. This guide walks through it.

## Before you begin, you need

- The plugin installed and enabled (you already have this if your `git commit` fires `pre_commit_cli_gate.py`).
- `uv` on your PATH (the invocation uses `uv run`).
- Write access to `~/.claude/settings.json` (your **user-level** CC settings, not the plugin's).

## Steps

1. **Locate your user settings file.** On Windows, this is typically `%USERPROFILE%\.claude\settings.json`. On macOS/Linux, `~/.claude/settings.json`. Open it in your editor — or create it with `{}` if it does not yet exist.

2. **Add the `statusLine` entry.** Merge the following key into the top-level object:

   ```json
   {
     "statusLine": {
       "type": "command",
       "command": "uv run python -m hooks.statusline"
     }
   }
   ```

   If the file already has other keys (permissions, env, etc.), preserve them. `statusLine` sits at the same level as `permissions`.

3. **Restart Claude Code.** The statusline is wired at session start; a running session will not pick up the new setting until it reloads.

4. **Verify it worked.** Start a new CC session in any project where this plugin is enabled. After your first assistant response, your terminal should display a one-line status in the shape:

   ```
   Opus · ctx 45% (125K/125K) · feat/my-branch
   ```

   The three segments are: model display name, framework-budget percentage (with raw tokens used / hard-cut tokens), current git branch. Any segment is omitted when its data is unavailable.

5. **Verify the cache is populating.** From your project root:

   ```
   cat .claude/.context_pct
   ```

   The file should exist and contain an integer between 0 and 100 (or higher if you are past the hard cut). If the file is missing, the statusline is not running — check your `~/.claude/settings.json` syntax and that `uv run python -m hooks.statusline` resolves from the project root.

## Troubleshooting

- **Status line is blank.** The statusline exits non-zero when the invocation fails (missing `uv`, Python import error). Run `uv run python -m hooks.statusline` from your project root with an empty stdin — the process should exit 0 and print at least the branch segment. If it exits non-zero, the error output tells you what is missing.

- **Status line says `ctx` but never updates.** Check that `hooks/statusline.py` is receiving the CC JSON payload on stdin. CC pipes a JSON object with `model`, `context_window`, `cost`, etc. If you see only the branch segment, CC is not passing the full payload — this usually means the settings.json command format is wrong (missing `"type": "command"`).

- **Framework percentage is always 0 or very low.** CC calculates `used_percentage` against the whole context window (200K for Sonnet/Opus, 1M for Opus 1M). The framework's hard cut is ~62.6% of that window. A reading of 10% raw is ~16% framework. Normal early-session state.

- **Framework percentage is > 100.** You are past the hard cut and `context_budget.py` will exit 2 on your next prompt, forcing `/handoff`. Not a statusline bug — do the handoff.

## Why the plugin doesn't ship the statusline automatically

CC's plugin manifest schema only allows `agent` and `subagentStatusLine` at the plugin-`settings.json` level. Top-level `statusLine` is explicitly user-side. This is a CC design choice — plugins don't override the user's chosen statusline without opt-in. The hook is still bundled; the user chooses whether to wire it.

If this changes in a future CC release, the plugin will update to ship the wiring. Until then, this guide is the wiring step.

## Related

- `hooks/statusline.py` — the command's implementation
- `hooks/context_budget.py` — the primary reader of `.claude/.context_pct`
- `docs/architecture/principles/context-awareness.md` — why the framework cares about context percentage at all
