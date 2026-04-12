# Deploy Phase

**"Ship it safely. Prove the rollback works."**

The deploy phase handles release review, migration ordering, canary rollout, and post-deploy smoke testing.

## Trigger

`/release` or CI trigger.

## Flow

### Step 1: Release review

`deploy-release-reviewer` (write/blocking, opus) validates:

- CHANGELOG updated with all changes since last tag
- Version bump is appropriate (major/minor/patch per SemVer)
- Breaking changes documented and flagged
- All stamps are valid for the current branch
- No `[WIP]` commits in the release branch

### Step 2: Migration sequence

`deploy-migration-sequence-reviewer` (write/blocking, opus) validates:

- Migrations are ordered correctly (no out-of-sequence)
- Every migration has a rollback plan
- Data-preserving migrations (no `DROP` without backup step)
- Lock-duration analysis (long-running migrations flagged)

### Step 3: Canary planning

`deploy-canary-advisor` (reason, opus) proposes:

- Canary rollout strategy (percentage-based, region-based, or feature-flag)
- Rollback triggers (error rate, latency, SLO violations)
- Monitoring period before full rollout

### Step 4: Post-deploy smoke

`deploy-smoke-runner` (write/blocking, sonnet) runs smoke tests:

- Health check endpoints respond
- Critical user flows complete
- Database connectivity confirmed
- No regression in key metrics

## Exit

Tagged release, canary healthy, rollback path documented and tested.

## Interactions

- **Consumes:** validate phase stamps (no deploy without valid stamps)
- **Feeds into:** operate phase (deployed service needs monitoring)
- **Records:** release tag + CHANGELOG entry + migration verification report
- **Gated by:** `meta-session-planner` (sizes the release work)
