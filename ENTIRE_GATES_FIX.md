# Fix for Entire Gates 'Checks' Sub-gate Configuration

**Issue**: [#92 - Entire Gates 'Checks' sub-gate counts every check run on a head — including the merge queue's own check — deadlocking PRs out of the queue](https://github.com/elviskahoro/native/issues/92)

## Problem Summary

The Entire Gates `Checks` sub-gate is configured with `required_checks: []` (require all checks) and `require_all_success: true`. This includes non-CI bookkeeping checks like the Trunk Merge Queue's own status check. When a queue submission is cancelled or fails, it posts a terminal `cancelled`/`failure` conclusion on the PR head, permanently poisoning the Entire Gates status. This prevents the PR from re-entering the queue without pushing a new "retrigger" commit.

### Impact
- PRs get locked out of the merge queue after any queue setback
- Recovery requires pushing a new commit (wasting 3 CI runs, Pullfrog re-review, 6 trail-runner assessments)
- Affected PRs: #28, #31, #35, #38 (cancelled), #2, #23, #36 (failed)

## Solution

Scope the Entire Gates `Checks` sub-gate to **only the three actual CI workflow checks**:

1. `"Trunk Check"` (from `.github/workflows/trunk-check.yml`)
2. `"Unit tests"` (from `.github/workflows/tests.yml`)
3. `"Generate & Verify Docs and Social Cards"` (from `.github/workflows/validate-assets.yml`)

These are the same checks enforced by `.trunk/trunk.yaml` → `merge.required_statuses`.

## How to Apply the Fix

### Option 1: Via Entire Console (Recommended)

1. Go to the Entire console for this repo: https://app.entire.dev/repo/elviskahoro/native
2. Navigate to **Gates** → **Checks** (the "Checks" sub-gate)
3. In the configuration, find the `required_checks` field
4. Change from: `[]` (empty array — require all checks)
5. Change to: 
   ```json
   [
     "Trunk Check",
     "Unit tests",
     "Generate & Verify Docs and Social Cards"
   ]
   ```
6. Click **Save**

### Option 2: Via Entire API (Automated)

#### Prerequisites
- Access to the Entire API with authentication token
- `jq` and `curl` installed (for the shell script)

#### Using the Provided Script

```bash
# Set the TRUNK_API_TOKEN environment variable (if not already set)
export TRUNK_API_TOKEN="your-trunk-api-token"

# Run the script
bash scripts/update-entire-gates.sh
```

#### Manual API Call

```bash
# Get current configuration
curl -s -H "Authorization: Bearer ${TRUNK_API_TOKEN}" \
  "https://api.trails.app/api/v1/trails/gh/elviskahoro/native/gates"

# Update configuration (PATCH request)
curl -X PATCH \
  -H "Authorization: Bearer ${TRUNK_API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "gates": [{
      "gateKey": "checks",
      "gateType": "checks",
      "blocking": true,
      "enabled": true,
      "config": {
        "version": 1,
        "required_checks": [
          "Trunk Check",
          "Unit tests",
          "Generate & Verify Docs and Social Cards"
        ],
        "require_all_success": true
      }
    }]
  }' \
  "https://api.trails.app/api/v1/trails/gh/elviskahoro/native/gates"
```

## Verification

After applying the fix, verify it works:

### 1. Verify Configuration
```bash
curl -s -H "Authorization: Bearer ${TRUNK_API_TOKEN}" \
  "https://api.trails.app/api/v1/trails/gh/elviskahoro/native/gates" | \
  jq '.gates[] | select(.gateKey == "checks") | .config.required_checks'
```

Should output:
```json
[
  "Trunk Check",
  "Unit tests",
  "Generate & Verify Docs and Social Cards"
]
```

### 2. Test on a PR
1. Create and push a test PR
2. Submit it to the merge queue: `trunk merge <pr-number>`
3. Cause a queue setback (e.g., close and reopen the PR)
4. Verify that Entire Gates reports `Checks: passed` (not `failed`)
5. Verify the PR can re-enter the queue without a new commit

### 3. Regression Test
- Run the full gate cascade on a clean PR
- Verify all three CI checks are still required
- Verify Entire Gates passes when all three checks pass

## What's NOT Changing

✅ **No code changes** — this is configuration only  
✅ `.trunk/trunk.yaml` — merge.required_statuses already correct  
✅ GitHub workflows — job names unchanged  
✅ GitHub branch protection ruleset — no changes needed  
✅ Other sub-gates (Findings, Up to date) — unaffected  
✅ Merge queue behavior — unchanged  

## Implementation Notes

### Critical: Check Names Must Match Exactly
The three check names must exactly match the GitHub workflow job names:
- **NOT** `"trunk-check"` (must be `"Trunk Check"`)
- **NOT** `"unit-tests"` (must be `"Unit tests"`)
- **NOT** `"docs"` (must be `"Generate & Verify Docs and Social Cards"`)

Verify by running:
```bash
gh pr checks <any-open-pr> --json name --jq '.[].name'
```

### Optional: Include pullfrog-approval?
The issue mentions `"pullfrog-approval"` is optional. It's already enforced by the GitHub ruleset, so including it would be redundant but harmless. The fix as proposed does NOT include it.

### What This Prevents
- ❌ `"Trunk Merge Queue (main)"` — app bookkeeping check
- ❌ Any other app-generated status checks
- ❌ Non-CI checks that post `cancelled`/`failure` conclusions

## Root Cause

The merge queue posts its own status check (`Trunk Merge Queue (main)`) with terminal conclusions when:
- A submission is cancelled by the user
- The queue test suite fails
- GitHub rejects the merge

Because the gate was configured with `required_checks: []` (requiring ALL checks), these queue-internal state changes permanently poison the Entire Gates status. The gate doesn't distinguish between CI health signals and queue bookkeeping signals.

## Questions?

- **Issue**: https://github.com/elviskahoro/native/issues/92
- **Related issue** (workaround history): https://github.com/elviskahoro/native/issues/90
- **Repository docs**: See AGENTS.md → "Entire Gates" section
