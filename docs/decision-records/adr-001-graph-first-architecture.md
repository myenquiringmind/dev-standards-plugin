# ADR-001: Graph-First Architecture

**Status:** Accepted
**Date:** 2026-04-11
**Deciders:** Planning session (v2 architecture)

## Context

The v1.4 plugin has implicit relationships: hooks reference agents by name string, the orchestrator has a hardcoded domain list (`DOMAIN_EXECUTION_ORDER` in `lib/core/config.js:530-538`), commands know which agents to spawn via inline constants. Adding a new agent means updating multiple files. Removing one risks dangling references. There's no way to answer "what validates Python code?" without reading all the code.

## Decision

**Every component in the framework is a node in a directed graph. Every relationship between components is a typed edge.** The graph registry (`config/graph-registry.json`) is the single machine-readable artifact that represents the full topology.

Node types: Agent, Command, Hook, Skill, Rule, Gate, Profile, Template, MCPServer, BinTool, OutputStyle.

Edge types: triggers, validates, depends-on, produces, consumes, gates, composes, scoped-by, escalates-to, observed-by, derives-principle-from, overridden-by.

The graph registry is a **derived artifact** — it is built from per-component frontmatter manifests by `scripts/build-graph-registry.py` on pre-commit. Developers edit their component's frontmatter; the aggregator rebuilds the registry atomically.

## Consequences

- **Adding a new language** = adding a profile node + `scoped-by` edges to relevant agents
- **Adding a new agent** = adding a node + edges to the gates that compose it
- **Removing an agent** = checking no dangling edges remain (the aggregator fails on orphans)
- **Impact analysis** = graph traversal: "if I change this agent, what commands/gates are affected?"
- **Visualisation** = generate Mermaid/DOT from the registry
- **Self-validation** = `meta-graph-registry-validator` checks that the registry matches disk on every commit

## Alternatives considered

- **No registry; implicit relationships.** Status quo. Rejected: unscalable as the framework grows to 156 agents.
- **Hand-edited monolithic registry.** Rejected: drift risk is certain; the aggregator prevents drift mechanically.
- **TypeScript-based registry.** Rejected: adds a build step and non-LLM tooling. JSON + JSON Schema is parseable by every agent.
- **YAML registry.** Rejected: whitespace footguns; no canonical diff format.

## References

- Canonical plan §1 (Graph Architecture)
- `schemas/graph-registry.schema.json` — the schema that validates the registry
- `scripts/build-graph-registry.py` — the aggregator (Phase 1)
- `@docs/architecture/principles/psf.md` — the Primitive Selection Framework uses the graph for impact analysis
