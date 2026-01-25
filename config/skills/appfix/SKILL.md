---
name: appfix
description: Autonomous app debugging system. Checks environment health, diagnoses failures via logs, creates fix plans, auto-executes fixes, and loops until all services are healthy. Use when asked to "fix the app", "debug production", "check staging", or "/appfix".
---

# Autonomous App Debugging (/appfix)

Autonomous debugging skill that iterates until all services are healthy and verified in browser.

## Architecture: Completion Checkpoint

This workflow uses a **deterministic boolean checkpoint** to enforce completion:

```
┌─────────────────────────────────────────────────────────────────────┐
│  STOP HOOK VALIDATION                                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Load .claude/completion-checkpoint.json                             │
│                                                                      │
│  Check booleans deterministically:                                   │
│    - is_job_complete: false → BLOCKED                                │
│    - web_testing_done: false (if frontend) → BLOCKED                 │
│    - deployed: false (if code changed) → BLOCKED                     │
│    - what_remains not empty → BLOCKED                                │
│                                                                      │
│  If blocked → stderr: continuation instructions                      │
│  All checks pass → exit(0) → Allow stop                              │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

**Why this works**: The model must explicitly state true/false for each checkpoint field. If you say `false`, you're blocked. If you say `true` dishonestly, that's your problem - but you can't accidentally stop early.

## CRITICAL: Autonomous Execution

**THIS WORKFLOW IS 100% AUTONOMOUS. YOU MUST:**

1. **NEVER ask for confirmation** - No "Should I commit?", "Should I deploy?"
2. **Auto-commit and push** - When fixes are applied, commit and push immediately
3. **Auto-deploy** - Trigger deployments without asking
4. **Complete verification** - Test in browser and check console
5. **Fill out checkpoint honestly** - The stop hook checks your booleans

**Only stop when the checkpoint can pass. If your booleans say the job isn't done, you'll be blocked.**

### Credentials Exception

If credentials are missing (LOGFIRE_READ_TOKEN, TEST_EMAIL, TEST_PASSWORD), ask the user **once at start**. After that, proceed autonomously.

## Browser Verification is MANDATORY

**ALL appfix sessions require browser verification. No exceptions.**

| Change Type | Browser Verification Purpose |
|-------------|------------------------------|
| Code changes | Verify fix works in UI |
| Database changes | Verify data displays correctly in app |
| Infrastructure changes | Verify app functions after infra fix |
| Config changes | Verify behavior changed as expected |
| Schema changes | Verify feature using new tables works |

**INVALID REASONS TO SKIP BROWSER TESTING:**
- "No code changes to test"
- "Database-only session"
- "Infrastructure-only changes"
- "The fix was server-side"
- "I only ran SQL queries"

The purpose of browser verification is to confirm **the application works after your fix**, not to test code changes specifically. A database fix (e.g., resetting CV statuses) must be verified by navigating to the affected page and confirming the data displays correctly.

**Required evidence for ALL appfix sessions:**
```json
{
  "evidence": {
    "urls_tested": ["https://staging.example.com/affected-page"],  // REQUIRED - actual URLs
    "console_clean": true
  }
}
```

The stop hook will reject checkpoints where `web_testing_done: true` but `urls_tested` is empty.

## Triggers

- `/appfix`
- "fix the app"
- "debug production"
- "check staging"
- "why is it broken"

## Completion Checkpoint Schema

Before stopping, you MUST create `.claude/completion-checkpoint.json`:

### Example: Code Changes Session (with Surf CLI artifacts)
```json
{
  "self_report": {
    "code_changes_made": true,
    "web_testing_done": true,
    "web_testing_done_at_version": "abc1234",
    "web_smoke_artifacts_exist": true,
    "web_smoke_passed": true,
    "web_smoke_version": "abc1234",
    "api_testing_done": true,
    "deployed": true,
    "deployed_at_version": "abc1234",
    "console_errors_checked": true,
    "console_errors_checked_at_version": "abc1234",
    "docs_updated": true,
    "docs_read_at_start": true,
    "linters_pass": true,
    "linters_pass_at_version": "abc1234",
    "preexisting_issues_fixed": true,
    "az_cli_changes_made": false,
    "infra_pr_created": false,
    "is_job_complete": true
  },
  "reflection": {
    "what_was_done": "Fixed CORS config in next.config.js, deployed to staging, verified login flow works via Surf CLI",
    "what_remains": "none",
    "blockers": null
  },
  "evidence": {
    "urls_tested": ["https://staging.example.com/dashboard"],
    "console_clean": true,
    "web_smoke_summary": ".claude/web-smoke/summary.json"
  }
}
```

### Example: Database-Only Session (No Code Changes)
```json
{
  "self_report": {
    "code_changes_made": false,
    "web_testing_done": true,
    "web_testing_done_at_version": "abc1234",
    "console_errors_checked": true,
    "console_errors_checked_at_version": "abc1234",
    "docs_read_at_start": true,
    "az_cli_changes_made": false,
    "is_job_complete": true
  },
  "reflection": {
    "what_was_done": "Reset 191 CVs in parsing queue to pending status via SQL",
    "what_remains": "none",
    "blockers": null
  },
  "evidence": {
    "urls_tested": ["https://staging.example.com/candidates"],
    "console_clean": true,
    "note": "Verified CV parsing queue shows 191 pending CVs after reset"
  }
}
```

**CRITICAL**: Even when `code_changes_made: false`, you MUST still have `urls_tested` with actual URLs. The stop hook rejects `web_testing_done: true` with empty `urls_tested`.

| Field | Type | Required | Meaning |
|-------|------|----------|---------|
| `code_changes_made` | bool | yes | Were any code files modified? |
| `web_testing_done` | bool | yes | Did you verify in a real browser? |
| `web_smoke_artifacts_exist` | bool | appfix | Do Surf CLI artifacts exist in .claude/web-smoke/? |
| `web_smoke_passed` | bool | appfix | Did Surf verification pass? |
| `web_smoke_version` | string | appfix | Git version when Surf verification ran |
| `api_testing_done` | bool | conditional | Did you test API endpoints? |
| `deployed` | bool | conditional | Did you deploy the changes? |
| `console_errors_checked` | bool | yes | Did you check browser console? |
| `docs_updated` | bool | conditional | Did you update relevant documentation? |
| `docs_read_at_start` | bool | yes (appfix) | Did you read project docs before starting? |
| `linters_pass` | bool | if code changed | Did all linters pass with zero errors? |
| `preexisting_issues_fixed` | bool | if code changed | Did you fix ALL issues (no excuses)? |
| `az_cli_changes_made` | bool | yes | Did you run az CLI infrastructure commands? |
| `infra_pr_created` | bool | if az CLI used | Did you create PR to infra repo? |
| `is_job_complete` | bool | yes | **Critical** - Is the job ACTUALLY done? |
| `what_remains` | string | yes | Must be "none" to allow stop |

### Web Smoke Artifact Fields (NEW)

When using Surf CLI for verification, the stop hook validates artifacts in `.claude/web-smoke/`:

| Field | Source | Validation |
|-------|--------|------------|
| `web_smoke_artifacts_exist` | summary.json exists | Required if appfix mode |
| `web_smoke_passed` | summary.json → passed | Must be true |
| `web_smoke_version` | summary.json → tested_at_version | Must match current git version |

**If artifacts pass validation, `web_testing_done` and `console_errors_checked` are auto-set to true.**

### Documentation Requirements (docs_updated)

Update these when your changes affect them:
- `docs/TECHNICAL_OVERVIEW.md` - Architectural changes, new services
- Module docs in `docs/` - Feature changes, API modifications
- `.claude/skills/*/references/` - Service topology, error patterns
- `.claude/MEMORIES.md` - Significant learnings only (not changelog)

## Workflow Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 0: PRE-FLIGHT CHECK                                          │
│     └─► Read docs/index.md + TECHNICAL_OVERVIEW.md (MANDATORY)      │
│     └─► Verify service-topology.md exists                           │
│     └─► If missing credentials, ask user ONCE                       │
├─────────────────────────────────────────────────────────────────────┤
│  ╔═══════════════════════════════════════════════════════════════╗  │
│  ║  PHASE 0.5: CODEBASE CONTEXT (MANDATORY - FIRST ITERATION)   ║  │
│  ║     └─► EnterPlanMode                                         ║  │
│  ║     └─► Explore: architecture, recent commits, configs        ║  │
│  ║     └─► Write codebase understanding to plan file             ║  │
│  ║     └─► ExitPlanMode                                          ║  │
│  ╚═══════════════════════════════════════════════════════════════╝  │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  FIX-VERIFY LOOP (iterate until checkpoint passes)                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. HEALTH CHECK                                                     │
│     └─► Check all services (frontend, backend, workers)             │
│     └─► Run browser tests                                           │
│                                                                      │
│  2. IF ALL HEALTHY + VERIFIED → UPDATE CHECKPOINT → EXIT            │
│                                                                      │
│  3. IF FAILURES DETECTED:                                           │
│     a. COLLECT LOGS                                                 │
│        └─► Azure Container App logs                                 │
│        └─► LogFire structured logs                                  │
│        └─► Browser console (via Chrome MCP)                         │
│                                                                      │
│     b. PLAN (optional after first iteration)                        │
│        └─► Write root cause analysis if hypothesis changes          │
│                                                                      │
│     c. EXECUTE FIX                                                  │
│        └─► Apply code changes                                       │
│        └─► Commit and push                                          │
│        └─► Deploy: gh workflow run + gh run watch --exit-status     │
│                                                                      │
│     d. LINTER VERIFICATION (Phase 3.5)                              │
│        └─► Auto-detect linters (eslint, ruff, tsc, pyright)         │
│        └─► Fix ALL errors including pre-existing ones               │
│        └─► NO EXCEPTIONS: "not my code" is prohibited               │
│                                                                      │
│     e. INFRASTRUCTURE SYNC (Phase 3.6 - if az CLI used)             │
│        └─► Document az CLI changes in .claude/infra-changes.md      │
│        └─► Update IaC files in infra repo                           │
│        └─► Create PR to infra repo                                  │
│                                                                      │
│     f. VERIFY                                                       │
│        └─► Test in browser via Chrome MCP or /webtest               │
│        └─► Check browser console is clean                           │
│        └─► Update appfix-state.json                                 │
│                                                                      │
│  4. LOOP UNTIL CHECKPOINT CAN PASS                                  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## State File Schema

Also maintain `.claude/appfix-state.json` for iteration tracking:

```json
{
  "iteration": 1,
  "started_at": "2025-01-24T10:00:00Z",
  "services": {
    "frontend": { "healthy": false, "last_error": "500 on /api/health" },
    "backend": { "healthy": true, "last_error": null }
  },
  "fixes_applied": [
    { "iteration": 1, "description": "Fixed CORS config", "files": ["next.config.js"] }
  ],
  "verification_evidence": {
    "url_verified": "https://staging.example.com/dashboard",
    "console_clean": true,
    "verified_at": "2025-01-24T10:30:00Z",
    "method": "chrome_mcp"
  }
}
```

## Phase 0: Pre-Flight Check

**CRITICAL: Create state files FIRST to enable auto-approval and cross-repo validation.**

```bash
# 1. Create BOTH state files IMMEDIATELY
# User-level state: enables cross-repo appfix detection (e.g., working in terraform repo)
# Project-level state: backwards compatibility + iteration tracking

mkdir -p ~/.claude && cat > ~/.claude/appfix-state.json << 'EOF'
{
  "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "origin_project": "$(pwd)"
}
EOF

mkdir -p .claude && cat > .claude/appfix-state.json << 'EOF'
{
  "iteration": 1,
  "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "services": {},
  "fixes_applied": [],
  "verification_evidence": null
}
EOF
```

**Why both files?**
- **User-level (`~/.claude/appfix-state.json`)**: Ensures stop hook validation works even when you switch to another repo (e.g., terraform-infra) to fix the root cause. Without this, the stop hook only checks the current working directory.
- **Project-level (`.claude/appfix-state.json`)**: Tracks iteration state, fixes applied, and verification evidence for the specific project.

**Cleanup on completion**: Remove both files when appfix completes successfully:
```bash
rm -f ~/.claude/appfix-state.json .claude/appfix-state.json
```

Then:
1. **Read project documentation** (MANDATORY):
   - Read `docs/index.md` - Project overview and architecture links
   - Read `docs/TECHNICAL_OVERVIEW.md` - System architecture and design
   - Update checkpoint: `docs_read_at_start: true`
2. Check for `.claude/skills/appfix/references/service-topology.md`
3. If missing: **STOP and ask user** for service URLs
4. Check credentials - if missing, ask user **ONCE at start**

```bash
# Check for service topology
ls .claude/skills/appfix/references/service-topology.md
```

**Why read docs first?** Understanding the architecture prevents:
- Fixing symptoms instead of root causes
- Breaking other components with your fix
- Missing context about how services interact

## Phase 0.5: Codebase Context (First Iteration Only)

**Mandatory on first iteration. Optional on subsequent iterations.**

1. **Call `EnterPlanMode`**
2. **Explore**:
   - Project structure and architecture
   - Recent commits: `git log --oneline -15`
   - Environment configs
   - Error handling patterns
3. **Write understanding** to plan file
4. **Call `ExitPlanMode`**

On subsequent iterations, only enter plan mode if your hypothesis changes significantly.

## Phase 1: Health Check

Check each service's health endpoint from `service-topology.md`:

```bash
curl -sf https://[service-url]/health || echo "UNHEALTHY"
```

Run browser tests via Chrome MCP or /webtest.

## Phase 2: Log Collection

Gather evidence from multiple sources:

### Azure Container Logs
```bash
az containerapp logs show \
  --name [app-name] \
  --resource-group [rg-name] \
  --type console \
  --tail 100
```

### LogFire Structured Logs
```bash
curl -H "Authorization: Bearer $LOGFIRE_READ_TOKEN" \
  "https://logfire-api.pydantic.dev/v1/query?level=error&since=1h"
```

### Browser Console
Use Chrome MCP `read_console_messages` tool to capture console logs.

## Phase 3: Execute Fix

### 3.1 Apply Code Changes
Use Edit tool for targeted changes. Keep fixes minimal.

### 3.2 Commit and Push (MANDATORY)
```bash
git add <specific files> && git commit -m "appfix: [brief description]"
git push
```

### 3.3 Deploy
```bash
# Trigger deployment
gh workflow run deploy.yml -f environment=staging

# CRITICAL: Wait for completion - exits non-zero if deploy fails
gh run watch --exit-status
```

**If deploy fails, DO NOT proceed.** Diagnose the deployment failure first.

### 3.4 Post-Deploy Health Polling
```bash
# Poll health endpoint (max 60s)
HEALTH_URL="https://staging.example.com/health"
for i in {1..12}; do curl -sf "$HEALTH_URL" && break || sleep 5; done
```

## Phase 3.5: Linter Verification (MANDATORY)

**Run after code changes, before verification.**

### Auto-Detect Linters

Check which linters are available and run them ALL:

```bash
# JavaScript/TypeScript projects
[ -f package.json ] && npm run lint 2>/dev/null || npx eslint . --ext .js,.jsx,.ts,.tsx
[ -f tsconfig.json ] && npx tsc --noEmit

# Python projects
[ -f pyproject.toml ] && ruff check --fix .
[ -f pyrightconfig.json ] && pyright
```

### STRICT POLICY: No Pre-Existing Exceptions

**PROHIBITED EXCUSES:**
- "These errors aren't related to our code"
- "This was broken before we started"
- "I'll fix this in a separate PR"

**REQUIRED BEHAVIOR:**
- Fix ALL linter errors, including pre-existing ones
- If you truly cannot fix an error, explain WHY in `what_remains`
- Update checkpoint: `linters_pass: true`, `preexisting_issues_fixed: true`

**Why this policy?** Pre-existing linter errors:
- Often mask real bugs in your changes
- Create technical debt
- Make the codebase harder to maintain
- "Not my problem" culture leads to code rot

## Phase 3.6: Infrastructure Sync (CONDITIONAL)

**Required when `az CLI` commands modify infrastructure.**

### When This Phase Applies

If you ran ANY of these commands:
- `az containerapp *` (create, update, revision, etc.)
- `az webapp *`
- `az functionapp *`
- `az storage *`
- `az keyvault *`
- `az network *`
- `az resource *`

### Required Actions

1. **Document changes** in `.claude/infra-changes.md`:
   ```markdown
   ## Infrastructure Changes - [DATE]

   ### Commands Executed
   - az containerapp update --name myapp --resource-group myrg --cpu 1.0 --memory 2Gi

   ### Changes Made
   - Increased container CPU from 0.5 to 1.0 cores
   - Increased memory from 1Gi to 2Gi

   ### Reason
   - OOM errors in production logs
   ```

2. **Clone infra repo** (location from `service-topology.md`)

3. **Update IaC files** to match the actual state:
   - Terraform: Update `.tf` files
   - Bicep: Update `.bicep` files
   - ARM: Update ARM templates

4. **Create PR to infra repo**:
   ```bash
   cd /path/to/infra-repo
   git checkout -b appfix/sync-$(date +%Y%m%d)
   # Make changes to match az CLI commands
   git add .
   git commit -m "appfix: Sync infrastructure state from $(date +%Y-%m-%d)"
   gh pr create --title "Sync infra changes from appfix" --body "..."
   ```

5. **Update checkpoint**: `az_cli_changes_made: true`, `infra_pr_created: true`

**Why this matters?** Infrastructure drift causes:
- Next deploy overwrites your fix
- IaC state doesn't match reality
- Team confusion about actual configuration
- Compliance and audit issues

## Phase 4: Verification (MANDATORY)

**You cannot claim success without browser verification.**

### Phase 4.5: Deterministic Web Verification (PREFERRED)

Instead of manually testing with Chrome MCP, run the deterministic Surf workflow for artifact-based proof:

**Step 1: Ensure Surf CLI is installed**
```bash
which surf || npm install -g @nicobailon/surf-cli
```

**Step 2: Run verification**
```bash
# Using explicit URLs
python3 ~/.claude/hooks/surf-verify.py --urls "https://staging.example.com/dashboard" "https://staging.example.com/login"

# Or using URLs from service-topology.md
python3 ~/.claude/hooks/surf-verify.py --from-topology
```

**Step 3: Check artifacts exist**
```bash
ls -la .claude/web-smoke/
# Expected: summary.json, screenshots/, console.txt
```

**Step 4: If verification fails**
- Check `.claude/web-smoke/summary.json` for error details
- Check `.claude/web-smoke/console.txt` for console errors
- Check `.claude/web-smoke/failing-requests.sh` for network errors
- Fix issues and re-run verification

**The stop hook validates these artifacts automatically.** If `summary.json` shows `passed: false`, you'll be blocked until you fix the issues.

**Waiver file for expected errors:**
If you have expected third-party errors (analytics blocked, etc.), create `.claude/web-smoke/waivers.json`:
```json
{
  "console_patterns": ["analytics\\.js.*blocked"],
  "network_patterns": ["GET.*googletagmanager\\.com.*4\\d\\d"],
  "reason": "Third-party analytics blocked by privacy settings"
}
```

### 4.1 Fallback: Chrome MCP Verification

If Surf CLI is not available or fails, use Chrome MCP tools:
```
- mcp__claude-in-chrome__navigate to the app URL
- mcp__claude-in-chrome__computer action=screenshot to capture state
- mcp__claude-in-chrome__read_console_messages to check for errors
```

Or use /webtest skill.

When using Chrome MCP, you must manually set `web_testing_done: true` in the checkpoint.

### 4.2 Check Console
- ZERO uncaught JavaScript errors
- ZERO network requests returning 500
- Data actually displays (not spinner/loading state)

### 4.3 Update State and Checkpoint

After verification, update both files:

**`.claude/appfix-state.json`**:
```json
{
  "verification_evidence": {
    "url_verified": "https://staging.example.com/dashboard",
    "console_clean": true,
    "verified_at": "2025-01-24T10:30:00Z",
    "method": "chrome_mcp"
  }
}
```

**`.claude/completion-checkpoint.json`**:
```json
{
  "self_report": {
    "code_changes_made": true,
    "web_testing_done": true,
    "deployed": true,
    "console_errors_checked": true,
    "is_job_complete": true
  },
  "reflection": {
    "what_was_done": "Fixed CORS, deployed, verified login works",
    "what_remains": "none"
  }
}
```

## Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `LOGFIRE_READ_TOKEN` | Optional | Query LogFire API |
| `TEST_EMAIL` | Optional | Integration test user |
| `TEST_PASSWORD` | Optional | Integration test password |

If missing and needed, ask the user **once at start**.

## Reference Files

| File | Path | Required |
|------|------|----------|
| Service topology | `.claude/skills/appfix/references/service-topology.md` | **YES** |
| Log patterns | `.claude/skills/appfix/references/log-patterns.md` | Optional |

**Always read from project-local paths, not `~/.claude/`**

## Safety Gate (Production Only)

Pause for human confirmation ONLY when:
- **Environment**: production, prod, live, main branch
- **Destructive**: delete, drop, truncate, reset, wipe
- **Secrets**: would print/log secret values

All other actions proceed autonomously.

## Exit Conditions

### Success (Checkpoint Passes)
- All self_report booleans are true (where required)
- what_remains is "none" or empty
- is_job_complete is true

### Blocked (Continue Working)
- Any required boolean is false
- what_remains lists incomplete work
- is_job_complete is false

### Blocked (Ask User)
- Missing credentials (once at start)
- Infrastructure completely down
- Ambiguous destructive action

## Example Session

```
User: /appfix

[PHASE 0] Pre-Flight Check
  ✓ Reading docs/index.md
  ✓ Reading docs/TECHNICAL_OVERVIEW.md
  ✓ docs_read_at_start: true
  ✓ service-topology.md exists
  ⚠ LOGFIRE_READ_TOKEN missing - will ask user once

[User] Please provide LOGFIRE_READ_TOKEN: [user enters token]

[PHASE 0.5] Codebase Context (mandatory first iteration)
  → EnterPlanMode
  → Explored: Next.js + FastAPI, recent auth changes
  → ExitPlanMode

[PHASE 1] Health Check
  ✗ Frontend: 500 on /api/health
  ✓ Backend: healthy
  ✗ Browser test: login failed

[PHASE 2] Log Collection
  - Azure: TypeError in auth middleware
  - Console: "Cannot read property 'user' of undefined"

[PHASE 3] Execute Fix
  - Edit: auth.py - add null check
  - Commit: "appfix: Add null check in auth middleware"
  - Deploy: gh workflow run + gh run watch

[PHASE 3.5] Linter Verification
  - Detected: ruff (pyproject.toml)
  - Running: ruff check --fix .
  - Found 3 errors (1 pre-existing)
  - Fixed ALL 3 errors
  ✓ linters_pass: true
  ✓ preexisting_issues_fixed: true

[PHASE 3.6] Infrastructure Sync (SKIPPED - no az CLI commands used)

[PHASE 4] Verification
  - Chrome MCP: navigated to /dashboard
  - Screenshot: data displays correctly
  - Console: clean (no errors)
  - Updated verification_evidence
  - Updated completion-checkpoint.json

[TRY TO STOP]
  → Stop hook checks checkpoint
  → is_job_complete: true ✓
  → docs_read_at_start: true ✓
  → web_testing_done: true ✓
  → deployed: true ✓
  → linters_pass: true ✓
  → what_remains: "none" ✓

[SUCCESS] APPFIX COMPLETE - Verified!
```

## Philosophy: Honest Self-Reflection

This system works because:

1. **Booleans force honesty** - You must choose true/false, no middle ground
2. **Self-enforcing** - If you say false, you're blocked
3. **Deterministic** - No regex heuristics, just boolean checks
4. **Trusts the model** - Models don't want to lie when asked directly

The stop hook doesn't try to catch lies. It asks direct questions:
- "Did you test this in the browser?" → Answer honestly
- "Is the job actually complete?" → Answer honestly

If you answer `false`, you're blocked. If you answer `true` honestly, you're done.
