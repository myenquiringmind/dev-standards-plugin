# Phase 1 Integration Verification Runbook

Mechanical runbook for the three live-verification gates carried forward from `phase-1-exit-report.md` § "Integration gates — pending live verification". The gates need a Claude Code restart on your machine to take effect — they cannot be run from a standalone Python script (`scripts/bootstrap_smoke.py` covers them structurally; this runbook drives them live).

Run this once when convenient. ~5 minutes total.

## Prerequisites

1. **Sync the marketplace clone** so the local CC plugin matches what's on master:
   ```bash
   git -C "$HOME/.claude/plugins/marketplaces/myenquiringmind" pull origin master
   ```
2. **Restart Claude Code.** The new hooks only take effect on a fresh session.
3. **Open this repo** in the restarted session.
4. **Cut a feature branch** for the verification (gates I2 / I3 attempt commits; you don't want to land them on master):
   ```bash
   git checkout -b chore/phase-1-integration-check
   ```

## Gate I1 — `/validate` produces a stamp end-to-end

**Setup:**
```bash
echo "x = 1" > tmp_phase1_check.py
git add tmp_phase1_check.py
```

**Action:** in CC, run `/validate code`.

**Expected:**
- One of `.validation_stamp` / `.frontend_validation_stamp` / `.agent_validation_stamp` / `.db_validation_stamp` / `.api_validation_stamp` exists at the project root.
- The stamp file's JSON contains a `timestamp` within the last minute and a `steps` list covering `PY_VALIDATION_STEPS` from `hooks/_hook_shared.py`.

**Verify:**
```bash
cat .validation_stamp | python -m json.tool
```

**Pass criteria:** stamp present, fresh, branch-matched, steps list non-empty.

## Gate I2 — First non-`[WIP]` commit through the stamp gate

**Pre-condition:** I1's stamp is <15 minutes old (TTL).

**Action:**
```bash
git commit -m "chore: phase-1 integration check"
```

**Expected:** commit succeeds. No `[pre_commit_cli_gate]` rejection on stderr.

**Pass criteria:** exit 0, new commit on the feature branch.

## Gate I3 — Stamp expiry enforced in the wild

**Action:** wait 16 minutes (`STAMP_TTL = 900s` plus a minute of slack), then attempt another commit:

```bash
echo "y = 2" >> tmp_phase1_check.py
git add tmp_phase1_check.py
git commit -m "chore: phase-1 integration check 2"
```

**Expected:** commit blocked. Stderr contains `[pre_commit_cli_gate]` and a stale-stamp message.

**Pass criteria:** non-zero exit, stale-stamp message visible.

## Cleanup

```bash
git checkout master
git branch -D chore/phase-1-integration-check
rm tmp_phase1_check.py
rm .validation_stamp  # if still present
```

## Recording results

If all three gates pass, leave a comment on `docs/phases/phase-1-exit-report.md`'s "Integration gates" table noting the verification date, or open a small follow-up PR amending the section to reflect the live-pass status.

If any gate fails, the failure is a tier-3 finding: open a TR entry in `docs/todo-registry/` describing what diverged from the expected behavior.
