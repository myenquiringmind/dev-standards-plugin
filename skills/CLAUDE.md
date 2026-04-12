# skills/ — Auto-triggering capability bundles

You are working in the skills directory. Skills are the primary mechanism by which this plugin ships knowledge to users. They are auto-invoked by path matching or explicit user invocation.

## Critical fact

**Plugins ship skills, not rules.** The Claude Code plugin system does not let plugins ship `.claude/rules/*.md` files to users. Plugins contribute skills via the plugin manifest, and skills auto-invoke based on `paths:` frontmatter globs.

This repo has both:

- **Skills shipped to users** (this directory) — auto-invoke in user projects when installed
- **Rules in `.claude/rules/`** — for this repo's own dogfooded development, not shipped

See `@docs/architecture/principles/plugin-vs-project.md` for the full duality.

## Directory layout

One directory per skill, with `SKILL.md` as the entry point:

```
skills/
├── <skill-name>/
│   ├── SKILL.md           # the skill itself (≤500 lines)
│   ├── templates/         # supporting files loaded on reference
│   └── examples/          # optional, referenced from SKILL.md
```

## Required frontmatter (SKILL.md)

```yaml
---
name: <kebab-case-name>         # stable identifier
description: <≤250 chars>       # shown in the skill index; truncated beyond 250
paths: [<glob>, <glob>]         # auto-invoke when Claude works with these file types
allowed-tools: <list>           # tools Claude can use while skill is active
context: fork | none            # fork = isolated subagent context
model: opus | sonnet | haiku    # optional override
user-invocable: true | false    # hide from / menu if false
disable-model-invocation: true | false  # prevent auto-invocation
---
```

## Size discipline (hard, not guideline)

- **`SKILL.md` ≤500 lines.** Beyond this, move reference material to supporting files in the skill directory.
- **`description` ≤250 characters.** CC truncates beyond; longer descriptions are silently cut.
- **Supporting files** (templates, examples, long reference docs) are referenced from SKILL.md, loaded on demand — they do not count against the skill size budget.

## Compaction behaviour

Skills survive compaction with a **shared 25,000-token budget** across all invoked skills. Each skill keeps the first 5,000 tokens of its most recent invocation; older skills are dropped entirely if the budget is exceeded. **If a skill must survive compaction, it must be in the first 5,000 tokens.** Put the most important content at the top.

## Naming

- Skills shipped for end-user development: `python-standards`, `javascript-standards`, `api-contracts`, `database`, `design-patterns`, `security`, `naming-database`, etc.
- Skills used internally by the framework development lifecycle: `tdd-workflow`, `pattern-apply`, `debug-systematic`, etc.

## Scaffolding a new skill

Use `meta-skill-scaffolder` (TBD) or follow the template at `templates/skill/`. Do not hand-write skills after the scaffolder lands — it enforces the ≤250 char description, the ≤500 line SKILL.md, and the `paths:` frontmatter.

## Read these first

- `@docs/architecture/principles/psf.md` — skills sit at the fourth rung of the PSF
- `@docs/architecture/principles/plugin-vs-project.md` — why plugins ship skills and not rules
- `@docs/architecture/principles/documentation-as-code.md` — size limits are enforced by `post_edit_doc_size.py`
