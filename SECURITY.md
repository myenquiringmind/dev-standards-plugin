# Security Policy

`dev-standards-plugin` is a public, self-hosted Claude Code plugin. This document is the project's security policy.

## Supported versions

The plugin is pre-1.0. Security fixes land on `master` only. There are no supported historical branches.

| Version | Supported |
|---|---|
| `master` (pre-2.0.0) | Yes |
| Any tagged release | Best-effort |
| Any fork | Not supported |

## Reporting a vulnerability

**Do not file a public issue for security vulnerabilities.** Instead:

1. Email the maintainer directly (see `.github/CODEOWNERS` once created, or the repo's public contact).
2. Include: a description of the vulnerability, reproduction steps, affected version, and your disclosure timeline preference.
3. You will receive an acknowledgment within 48 hours.
4. Responsible disclosure is requested: allow at least 14 days for a fix before public disclosure.

Encrypted reports: PGP key (TBD — planned before first public release).

## Scope

The plugin ships:

- **Python hooks** that run in your Claude Code session. Hooks have filesystem and subprocess access. Review them before installing.
- **Agents** that compose subagent calls. Agents can invoke LLM tools within the plugin's declared tool allowlists.
- **Skills** auto-invoked by file path globs. Skill content becomes part of the session context.
- **Schemas** for component frontmatter and validation stamps.
- **Config files** for language profiles and plugin settings.

**Not in scope:** upstream Claude Code vulnerabilities, upstream LLM provider issues, user-installed third-party plugins. Report those to the respective projects.

## What the plugin does not do

- **Does not send data over the network** by default. All hooks are local. All telemetry (if enabled) is local-only by default — see `docs/architecture/principles/security.md`.
- **Does not require secrets** to operate. The plugin has no API keys, credentials, or tokens in its own config.
- **Does not modify files outside the active project** except inside `${CLAUDE_PLUGIN_DATA}` (the framework's own cache and memory directory).

## Known security considerations

- **Hooks run on every tool call.** A malicious or buggy hook can block or corrupt work. All bootstrap hooks are plain Python, auditable at `hooks/*.py`.
- **Agents can execute Bash.** Agents in the `tier: read` and `tier: reason` categories have Bash in a tightly-scoped subset (read-only commands only). Write-tier agents have broader Bash access. Review agent frontmatter before trusting a custom agent.
- **Skills inject context.** When a skill auto-invokes on a path match, its full content enters the session. Review `skills/*/SKILL.md` before relying on a skill.
- **The plugin is dogfooded on itself.** Every commit to this repo passes through the plugin's own gates. This is a strength (proven defence) and a risk (a bad commit can degrade the gates themselves).

## Secure development practices

The plugin's own development follows these practices, enforced by its own hooks:

- `hooks/pre_write_secret_scan.py` — regex-based secret scanner blocks common API key, token, and credential patterns on every file write
- `hooks/session_start_gitignore_audit.py` — validates `.gitignore` covers secret-bearing filenames (`.env`, `*.key`, `*.pem`, etc.)
- `hooks/pre_commit_cli_gate.py` — runs a final secret scan on staged diffs before allowing `git commit`
- `hooks/dangerous_command_block.py` — blocks destructive Bash commands
- Dependencies are pinned via `uv.lock` (Python) and `package-lock.json` (Node)
- License compliance: MIT-compatible dependencies only (enforced by `security-license-compliance` in Phase 3)

## Acknowledgments

Vulnerability reporters will be acknowledged in release notes with their permission.
