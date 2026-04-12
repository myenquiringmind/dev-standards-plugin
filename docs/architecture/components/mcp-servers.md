# MCP Server Catalog

4 bundled MCP servers, all landing in Phase 10. Each exposes framework capabilities via the Model Context Protocol, making them queryable from any MCP client — not just the Claude Code session that runs the plugin.

## Why MCP

MCP servers are the **sixth rung** of the PSF (`@principles/psf.md`). They're used when a capability must:

- **Persist across sessions** — a hook resets on session end; an MCP server runs continuously or restarts with state
- **Be reusable from CI** — `bin/dsp-validate` wraps MCP queries for CI pipelines
- **Handle complex queries** over durable state — graph traversal, memory search, telemetry aggregation

## The four servers

| Server | Transport | Tools exposed | Data source |
|---|---|---|---|
| **`graph-query`** | stdio | `find_validators_for(file_path)`, `impact_analysis(node_id)`, `topological_order()`, `export_mermaid()` | `config/graph-registry.json` |
| **`memory-search`** | stdio | `search_memories(query)`, `find_similar_incidents(description)`, `get_principle(id)` | `${CLAUDE_PLUGIN_DATA}/agent-memory/`, `${CLAUDE_PLUGIN_DATA}/framework-memory/` |
| **`telemetry-export`** | stdio | `get_agent_metrics(agent, period)`, `get_phase_metrics(phase)`, `get_quality_scores()` | `${CLAUDE_PLUGIN_DATA}/framework-memory/telemetry/` |
| **`incident-log`** | stdio | `list_incidents(filter)`, `get_incident(id)`, `find_by_rule(rule)`, `cluster_by_root_cause()` | `${CLAUDE_PLUGIN_DATA}/framework-memory/incidents/` |

## How MCP servers interact with other components

```
External MCP client (CI, dashboard, another Claude session)
      ↓
MCP server (e.g., graph-query)
      ↓
Reads config/graph-registry.json (derived artifact, rebuilt by scripts/build-graph-registry.py)
      ↓
Returns structured query results via MCP protocol
```

MCP servers are **read-only over the framework's state**. They do not write to the graph registry, the memory tiers, or the incident log — those are written by hooks and agents. MCP servers expose queries; hooks and agents produce the data.

The `bin/` tools (`dsp-validate`, `dsp-graph`, `dsp-incident`, `dsp-telemetry`) are CLI wrappers over the same MCP server query functions, for use outside a Claude Code session.

## Configuration

Bundled in `plugin.json` under `mcpServers`:

```json
{
  "mcpServers": {
    "graph-query": {
      "command": "${CLAUDE_PLUGIN_ROOT}/mcp-servers/graph-query/server.py",
      "cwd": "${CLAUDE_PLUGIN_ROOT}"
    }
  }
}
```

All servers are Python, invoked via `stdio` transport. They start when the plugin is enabled and stop when it's disabled.

## Phase 10 deliverable

MCP servers are not in the bootstrap. They land in Phase 10 (Operate + Maintain + Closed Loop + MCP) after the telemetry, incident log, and memory infrastructure are operational (Phase 4). Building MCP servers before their data sources exist would produce empty query results.

## Future expansion

Additional MCP servers may be added for:

- **Documentation search** — full-text search over `docs/architecture/` for agent context retrieval
- **Dependency analysis** — querying the codebase-dependency-grapher's reports for impact analysis
- **Release management** — querying CHANGELOG, version history, migration status

Each new MCP server would be proposed via ADR and built through the dogfooded gate.
