# Operate Phase

**"Something's broken. Fix it systematically. Capture lessons."**

The operate phase handles incident response, SLO monitoring, and runbook execution for deployed systems.

## Trigger

`/incident <description>` or SLO alert.

## Flow

### Step 1: Incident triage

`operate-incident-responder` (reason, opus max) runs the 4-phase debug loop:

1. **Observe** — gather symptoms, logs, metrics, traces
2. **Hypothesise** — generate 2-3 candidate root causes
3. **Test** — design and run diagnostic tests for each hypothesis
4. **Fix** — apply the fix for the confirmed root cause

### Step 2: SLO context

`operate-slo-monitor` (reason, sonnet) provides telemetry context:

- Current SLO compliance (error budget remaining)
- Burn rate (how fast we're consuming error budget)
- Impact scope (which users, which endpoints, which regions)

### Step 3: Runbook execution

`operate-runbook-executor` (reason, sonnet) walks through the applicable runbook:

- Finds the matching runbook in `docs/guides/` or project-specific runbooks
- Executes each step with validation at each stage
- Flags deviations from the runbook

### Step 4: Record and learn

- Incident record written to `${CLAUDE_PLUGIN_DATA}/framework-memory/incidents/`
- `doc-runbook-writer` updates the runbook with resolution steps
- Postmortem triggers `closed-loop-incident-retrospective-analyst` in the next weekly run

## Exit

Incident closed, runbook updated, lessons captured in framework memory.

## Interactions

- **Consumes:** deploy phase outputs (what was deployed, what changed)
- **Produces:** incident records → feeds closed-loop improvement
- **Updates:** runbooks in `docs/guides/` based on resolution steps
- **Gated by:** `meta-session-planner` (sizes the incident work — operate gets 80K guideline budget)
