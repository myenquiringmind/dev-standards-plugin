# Documentation

This directory contains all architectural documentation for `dev-standards-plugin`. The structure follows the Diataxis taxonomy (see [diataxis.fr](https://diataxis.fr)) to separate documentation by user intent.

## Where to look

| You want to... | Start here |
|---|---|
| Understand a core concept | `architecture/principles/` |
| Look up a component | `architecture/components/` (populated as components are built) |
| Understand a lifecycle phase | `architecture/lifecycle/` |
| Follow the implementation roadmap | `phases/` |
| Understand a past decision | `decision-records/` |
| Do a specific task | `guides/` |

## Directory layout

```
docs/
├── README.md                      # this file
├── CLAUDE.md                      # agent guidance for editing docs
│
├── architecture/                  # the framework explained
│   ├── README.md
│   ├── principles/                # explanation — core concepts
│   │   ├── psf.md
│   │   ├── memory-tiers.md
│   │   ├── rrw-tiering.md
│   │   ├── stamps.md
│   │   ├── bootstrap-first.md
│   │   ├── dogfooding.md
│   │   ├── context-awareness.md
│   │   ├── plugin-vs-project.md
│   │   ├── documentation-as-code.md
│   │   └── security.md
│   ├── lifecycle/                 # explanation — how work flows through phases
│   │   └── (phase walkthroughs, filled as phases land)
│   └── components/                # reference — catalog of what exists
│       └── (agent/hook/command/etc. catalogs, filled as components land)
│
├── phases/                        # reference — implementation roadmap
│   ├── README.md
│   ├── phase-0-architecture-lockdown.md
│   └── phase-1-bootstrap.md
│
├── decision-records/              # explanation — why we chose what we chose
│   ├── README.md
│   ├── adr-001-graph-first-architecture.md
│   ├── adr-002-strict-default.md
│   ├── adr-003-bootstrap-first-sequencing.md
│   ├── adr-004-read-reason-write-tiering.md
│   ├── adr-005-documentation-as-code.md
│   ├── adr-006-context-awareness-absolute-budgets.md
│   └── v2-architecture-planning-session.md   (archived canonical plan)
│
└── guides/                        # how-to — task-oriented
    ├── README.md
    └── getting-started.md
```

## Size discipline

Every file in `docs/` is ≤200 lines, enforced by `hooks/post_edit_doc_size.py` from Phase 1 exit. The only exempt file is `decision-records/v2-architecture-planning-session.md` (the archived canonical plan is a historical artifact).

**Why:** agents consuming architectural context load files lazily via `@include` from CLAUDE.md. Small files mean surgical loads. Large files mean bankrupt context budgets and lost-in-the-middle failures.

See `architecture/principles/documentation-as-code.md` for the rationale.

## How files link

Markdown in `docs/` and in CLAUDE.md files throughout the repo uses Claude Code's `@path` syntax to reference other files. When a parent file is loaded, `@path` includes trigger lazy loading of the referenced file. Use `@path` to compose small files into larger intellectual units without duplicating content.
