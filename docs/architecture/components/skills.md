# Skill Catalog

26 skills shipped by the plugin to users. Skills are the primary mechanism by which the plugin delivers knowledge to user projects. They auto-invoke on file-path matches and inject conventions, standards, and workflows into the session. See PSF at `@principles/psf.md` (skills are the fourth rung).

## Critical fact

**Plugins ship skills, not rules.** The Claude Code plugin system does not allow plugins to ship `.claude/rules/*.md` to user projects. Skills are the only context-injection primitive available to plugins. See `@principles/plugin-vs-project.md`.

## User-facing standards skills (14)

Auto-invoke when users edit matching files. Encode best-practice conventions per domain.

| Skill | `paths:` glob | Purpose |
|---|---|---|
| `python-standards` | `**/*.py` | Python conventions: ruff, mypy strict, structlog, Pydantic, Google docstrings, snake_case, `from __future__ import annotations` |
| `javascript-standards` | `**/*.{js,jsx,ts,tsx}` | JS/TS conventions: ESLint/Biome, strict TypeScript, Vitest, Zod, camelCase |
| `api-contracts` | `**/routes/**`, `**/api/**`, `**/*.openapi.*` | API conventions: OpenAPI, versioning, breaking-change awareness, contract-first |
| `database` | `**/migrations/**`, `**/models/**`, `**/*.sql` | Database conventions: normalization, indexing, migration safety, reversibility |
| `security` | `**/*` | Security conventions: OWASP top 10, secrets, injection, XSS, dependency hygiene |
| `design-patterns` | `**/*.{py,ts,js,rs,go}` | When to apply / not apply GoF + architectural patterns; language idiom tables |
| `testing` | `**/test_*`, `**/*.test.*`, `**/*.spec.*` | Test conventions: pyramid, fixtures, property tests, determinism, naming |
| `naming-database` | `**/migrations/**`, `**/*.sql` | Database naming: tables, columns, indexes, constraints, foreign keys |
| `naming-api` | `**/routes/**`, `**/api/**` | API endpoint naming: REST nouns, RPC verbs, pluralization, casing |
| `naming-env-vars` | `**/.env*`, `**/config.*` | Environment variable naming: SCREAMING_SNAKE, namespacing, documentation |
| `naming-git` | (manual invocation) | Branch naming, commit message format (conventional commits), PR titles |
| `naming-observability` | `**/logging/**`, `**/telemetry/**` | Log field naming, metric naming (Prometheus), trace/span naming (OpenTelemetry) |
| `naming-cicd` | `**/.github/**`, `**/Dockerfile*`, `**/*.yml` | CI job naming, Docker image tagging, workflow naming |
| `naming-containers` | `**/Dockerfile*`, `**/docker-compose*`, `**/k8s/**` | Container naming, service naming, volume naming |

## Framework workflow skills (12)

Encode multi-step workflows the framework uses internally and exposes to users.

| Skill | Trigger | Purpose |
|---|---|---|
| `dev-workflow` | Any code task | Core development workflow (existing v1.4) |
| `orchestrate` | `/orchestrate` | Standards enforcement dispatcher (existing v1.4) |
| `design-first` | Design-phase work | Design-before-code workflow |
| `debug-systematic` | Debugging work | 4-phase debugging (Observe, Hypothesise, Test, Fix) |
| `tdd-workflow` | TDD work | RED → GREEN → REFACTOR → VALIDATE → COMMIT |
| `pattern-apply` | Pattern work | Pattern identification + scaffold + review |
| `discover-process` | Discover-phase | Requirements elicitation + scanner pipeline |
| `research-process` | Research-phase | Prior-art scan + spike planning |
| `document-process` | Documentation work | ADR / runbook / sequence / onboarding workflow |
| `operate-process` | Incident work | Incident triage + response + postmortem |
| `maintain-process` | Maintenance work | Dep update + deprecation scan + flake detection |
| `refactor-pipeline` | Refactoring work | Detect → plan → apply (worktree) → validate |

## Size discipline

- SKILL.md ≤500 lines (reference material goes in supporting files)
- Description ≤250 characters (CC truncates beyond)
- Post-compaction: shared 25K token budget across all invoked skills (5K per skill)

## How skills interact with other components

```
User edits *.py
      ↓
CC detects python-standards skill matches paths: **/*.py
      ↓
Skill content loads into session context
      ↓
Claude follows the conventions while working
      ↓
Hooks (post_edit_lint, post_auto_format) mechanically enforce what the skill advises
```

Skills advise; hooks enforce. Skills are soft context; hooks are hard gates. Both are needed — a skill without a hook is a polite suggestion; a hook without a skill is a mysterious rejection.
