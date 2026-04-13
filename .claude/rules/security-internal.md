# Security — Internal Development

Security rules for developing the plugin itself. For the public security policy, see `SECURITY.md` at the repo root.

## No secrets in code

Never commit secrets, credentials, API keys, tokens, or private keys. This applies to:

- Source code (Python, JSON, markdown)
- Test fixtures (use obviously fake values like `AKIAIOSFODNN7EXAMPLE`)
- Configuration files
- Commit messages and comments

`hooks/pre_write_secret_scan.py` catches common patterns (AWS keys, GitHub tokens, OpenAI/Anthropic keys, PEM headers) but is not exhaustive. Think before pasting.

## Secret patterns to avoid

These patterns are blocked by the secret scanner:

| Pattern | Example |
|---|---|
| AWS access key | `AKIA` followed by 16 alphanumeric chars |
| GitHub token | `ghp_`, `gho_`, `ghs_`, `ghr_` prefixes |
| OpenAI key | `sk-` followed by 48+ chars |
| Anthropic key | `sk-ant-` prefix |
| Private keys | `-----BEGIN (RSA\|EC\|OPENSSH) PRIVATE KEY-----` |
| Generic high-entropy | Long base64 strings assigned to variables named `secret`, `password`, `token`, `api_key` |

## Forbidden filenames

Never create or commit: `.env`, `.env.local`, `.env.production`, `credentials.json`, `secrets.json`, `*.pem`, `*.key`. The secret scanner blocks writes to these filenames.

## .gitignore discipline

The `.gitignore` must cover:

- `.env*` (all environment files)
- `*.pem`, `*.key` (private keys)
- `.validation_stamp*` (ephemeral stamp files)
- `.context_pct` (ephemeral context cache)
- `session-state.md.injected` (archived session state)
- `tmp/` (throwaway scratch)
- `.venv/` (virtual environment)
- `node_modules/` (JS dependencies)

`session_start_gitignore_audit.py` (Phase 1) warns on missing critical patterns. Until then, check manually.

## Dependency pinning

All Python dependencies are pinned via `uv.lock`. Do not add unpinned dependencies. Do not run `uv add` without reviewing what you're adding. The `portalocker` and `jsonschema` packages are the only runtime dependencies — everything else is dev-only.

## No network in hooks

Hooks are local. No HTTP requests, no DNS, no socket connections. If you find yourself importing `urllib`, `requests`, or `httpx` in a hook file, stop — that logic belongs in an MCP server, not a hook.

## Path traversal prevention

All path construction in hooks must use `_os_safe.safe_join()`. Never concatenate user-provided strings into file paths. The canonical test case: `write_agent_memory.py --agent ../../etc/passwd` must be rejected.
