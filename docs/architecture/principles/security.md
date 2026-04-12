# Security

`dev-standards-plugin` is a public open-source repository and a Claude Code plugin. Both facts impose security requirements above and beyond normal code hygiene. This document describes the plugin's security posture and the mechanisms that enforce it.

## The public-plugin posture

The plugin repo is publicly visible. Accidentally committing a secret is **public disclosure**, not just an internal team leak. This changes the calculus:

- Secret scanning is not optional; it's a Phase 1 bootstrap requirement
- `.gitignore` must be comprehensive before the first commit; drift is a vulnerability
- Every dependency is a supply-chain attack vector; pinning and audit are required
- `SECURITY.md` at repo root is table stakes — users need to know how to report issues
- Development must be exemplary — users will read the code and copy patterns from it

## Secret scanning — multi-layer defence

Three-layer defence implemented in Phase 1 bootstrap:

### Layer 1: `hooks/pre_write_secret_scan.py`

PreToolUse hook on `Edit|Write`. Regex-based scanner blocks on common secret patterns:

- AWS access keys (`AKIA[0-9A-Z]{16}`)
- AWS secret keys (length + entropy check)
- GitHub tokens (`ghp_`, `gho_`, `ghu_`, `ghs_`, `ghr_` prefixes)
- OpenAI keys (`sk-proj-`, `sk-`)
- Anthropic keys (`sk-ant-`)
- Private keys (`-----BEGIN (RSA|EC|DSA|OPENSSH) PRIVATE KEY-----`)
- Generic patterns: `password\s*=\s*["'][^"']{8,}`, `api[_-]?key\s*=\s*["'][^"']{16,}`, `secret\s*=\s*["'][^"']{16,}`
- `.env` file creation (blocks unless the file is already tracked as a template)
- `*.pem`, `*.key`, `*.p12`, `credentials.json`, `secrets.json` — blocks write if filename matches

Exit 2 with a pointer to this document on match.

### Layer 2: `hooks/pre_commit_cli_gate.py` (extended)

The commit gate runs the same regex scan over the staged diff just before the commit completes. Belt on top of braces. If a secret somehow slipped past the PreToolUse hook, the commit gate catches it.

### Layer 3: Phase 2 `security-secret-scanner` agent

Full agent (replaces the regex hook in Phase 2) with:

- Entropy-based detection of high-randomness strings (catches secrets that don't match known patterns)
- Git history scan (catches secrets committed historically, even if deleted)
- Known false-positive suppression (reduces noise)
- Classification: confirmed secret / probable / possible / noise

## `.gitignore` audit

`hooks/session_start_gitignore_audit.py` (SessionStart) validates that `.gitignore` contains critical patterns:

```
.env, .env.*, *.pem, *.key, *.p12, credentials.json, secrets.json, .secrets/
.venv/, venv/, .uv/
node_modules/, dist/, build/
.claude/settings.local.json, CLAUDE.local.md
__pycache__/, *.pyc, .mypy_cache/, .ruff_cache/, .pytest_cache/
```

Warns (not blocks) on missing patterns. Emits on the first SessionStart of the day. Does not block because users may have intentional exclusions.

## Dependency security

- **Python:** `uv.lock` pins every transitive dependency; `uv sync` reproduces the exact environment
- **JavaScript:** `package-lock.json` pins the Node side of the plugin's existing `lib/`
- **GitHub Actions** (Phase 2): pinned by SHA, not by version tag, per supply-chain-attack mitigation best practice
- **`security-dep-vuln-scanner` agent** (Phase 2): checks `uv.lock` and `package-lock.json` against CVE feeds
- **`security-license-compliance` agent** (Phase 3): ensures every dep is MIT-compatible (since the plugin is MIT-licensed)

## Telemetry privacy — opt-in by default

**`userConfig.telemetryOptIn` defaults to `false`.** Opt-in, not opt-out. Rationale:

- GDPR-friendly out of the box
- Trust-building for the public plugin
- User control is primary; the plugin's internals are transparent

Additional constraints:

- **Local-only by default.** Telemetry writes to `${CLAUDE_PLUGIN_DATA}/framework-memory/telemetry/`. Never leaves the machine unless the user also opts in to export.
- **Minimum data collected:** agent name, invocation timestamp, latency, verdict (pass/fail), token count. Explicitly NOT collected: code content, user prompts, file paths, repo origin URL (without export consent).
- **Documented fields.** Every telemetry field is listed here with its rationale.
- **Disable entirely.** `userConfig.telemetryOptIn: false` (the default) means no hooks emit telemetry at all.

## What the plugin does not do

The plugin operates strictly offline by default:

- **No network calls** unless a user explicitly configures an MCP server that requires network (and MCP servers are in Phase 10)
- **No secrets in its own config.** The plugin has no API keys, credentials, or tokens built in
- **No modification of files outside the active project** except inside `${CLAUDE_PLUGIN_DATA}` (framework state) and the user's Auto Memory (which the plugin only reads from, never writes to)

## Dangerous command blocking

`hooks/dangerous_command_block.py` blocks destructive Bash commands at PreToolUse time:

- `rm -rf /`, `rm -rf $HOME`, `rm -rf ~`
- `dd if=/dev/`, `mkfs.*`, `shred`
- `git reset --hard` + `git push --force` combinations on protected branches
- `chmod -R 777` on repo directories
- Fork bombs, shell code injection patterns

Extend as needed; the list is a starting point, not exhaustive.

## Responsible disclosure

Vulnerability reporting policy lives in `SECURITY.md` at repo root. Reporters are acknowledged in release notes with their consent. Minimum disclosure timeline: 14 days from acknowledgment to public fix.

## What to read next

- `SECURITY.md` at repo root — the public-facing policy (what users see on GitHub)
- `@docs/architecture/principles/dogfooding.md` — why the plugin's own development must be exemplary
- `@docs/architecture/principles/plugin-vs-project.md` — the boundary between what ships and what stays internal
