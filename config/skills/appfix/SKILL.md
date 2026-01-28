---
name: appfix
description: Autonomous app debugging system. Checks environment health, diagnoses failures via logs, creates fix plans, auto-executes fixes, and loops until all services are healthy. Use when asked to "fix the app", "debug production", "check staging", or "/appfix".
---

# Autonomous App Debugging (/appfix)

Autonomous debugging skill that iterates until all services are healthy and verified in browser.

> **Note**: `/appfix` is a debugging specialization of the universal `/godo` skill.
> It inherits the completion checkpoint architecture and adds debugging-specific phases
> (health checks, log collection, service topology). For general tasks, use `/godo`.

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

## Automatic Cascade Invalidation

**CRITICAL: Checkpoint fields are automatically reset when code changes.**

When you edit files or run git commits, PostToolUse hooks automatically detect version changes and reset stale checkpoint fields:

```
┌─────────────────────────────────────────────────────────────────────┐
│  DEPENDENCY CHAIN (upstream → downstream)                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  linters_pass ─────► deployed ─────► web_testing_done                │
│                          │                                           │
│                          └────────► console_errors_checked           │
│                          │                                           │
│                          └────────► api_testing_done                 │
│                                                                      │
│  If linters_pass is stale → deployed, web_testing_done, etc. reset  │
│  If deployed is stale → web_testing_done, console_errors reset      │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### How It Works

1. **Edit/Write hook** (`checkpoint-invalidator.py`): After any file edit, checks if `*_at_version` fields are stale
2. **Bash hook** (`bash-version-tracker.py`): After git commits or az CLI commands, rechecks version and invalidates
3. **Stop hook** (`stop-validator.py`): Final validation before allowing stop

### Example: Multi-Iteration Fix

```
ITERATION 1:
  - Deploy at version "abc" → deployed: true, deployed_at_version: "abc"
  - Test in browser → web_testing_done: true, web_testing_done_at_version: "abc"
  - Test reveals error!

ITERATION 2:
  - Edit fix.py → version becomes "abc-dirty-xyz"
  ⚠️ HOOK FIRES: deployed ("abc") != current ("abc-dirty-xyz")
     → deployed: false, web_testing_done: false (cascade)

  - Commit fix → version becomes "def"
  ⚠️ HOOK FIRES: Same check, fields already reset

  - MUST re-deploy (deployed is false!)
  - MUST re-test (web_testing_done is false!)
```

### What Triggers Invalidation

| Trigger | Hook | What's Checked |
|---------|------|----------------|
| Edit/Write any file | checkpoint-invalidator.py | Version mismatch |
| `git commit` | bash-version-tracker.py | Version mismatch |
| `az containerapp *` | bash-version-tracker.py | Testing fields reset |
| `az keyvault *` | bash-version-tracker.py | Testing fields reset |

**You cannot skip re-deployment or re-testing after code changes. The hooks enforce this.**

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

## Credentials and Authentication

When the app requires authentication (login pages, API tokens, log access), Claude will:

1. **Check for local `.env` file** in the project root
2. **Read standard credential variables**:
   - `TEST_EMAIL` - Email/username for login
   - `TEST_PASSWORD` - Password for login
   - `LOGFIRE_READ_TOKEN` - For Logfire log queries
   - `API_TOKEN` or service-specific tokens
3. **Ask user only if missing** - If `.env` doesn't contain needed credentials

### Setting Up Credentials

Create a `.env` file in your project root:

```bash
# .env (add to .gitignore!)
TEST_EMAIL=your-test@example.com
TEST_PASSWORD=your-test-password
LOGFIRE_READ_TOKEN=pylf_v1_xxx  # For Logfire integration
```

**IMPORTANT**:
- Add `.env` to `.gitignore` to prevent committing secrets
- Copy from `.env.example` if available
- Claude will ask once if credentials are missing, then expects them in `.env` for future use

## Browser Verification is MANDATORY (Artifacts Required)

**ALL appfix sessions require browser verification with PROOF. No exceptions.**

### Critical: Artifacts are MANDATORY

Setting `web_testing_done: true` without Surf CLI artifacts will be **BLOCKED** by the stop hook.

**The stop hook now requires:**
1. **Surf CLI artifacts** in `.claude/web-smoke/summary.json` with `passed: true`
2. **Real app URLs** in `urls_tested` (not just health endpoints)
3. **Version match** - artifacts must be for current code version

**Boolean-only claims are NO LONGER accepted.** You cannot set `web_testing_done: true` without running Surf CLI or manually creating valid artifacts.

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

**INVALID WAYS TO CLAIM BROWSER TESTING:**
- Setting `web_testing_done: true` without running Surf CLI
- Using `curl` to hit health endpoints and claiming "web testing done"
- Putting only `/health`, `/ping`, `/api/health` URLs in `urls_tested`

The purpose of browser verification is to confirm **the application works after your fix**, not to test code changes specifically. A database fix (e.g., resetting CV statuses) must be verified by navigating to the affected page and confirming the data displays correctly.

### Health Endpoints Don't Count

The stop hook rejects `urls_tested` that contain **only** health endpoints:
- `/health`, `/healthz`, `/api/health`
- `/ping`, `/ready`, `/live`
- `/readiness`, `/liveness`, `/status`

You **MUST** test real user-facing pages like `/dashboard`, `/login`, `/profile`, etc.

**Required evidence for ALL appfix sessions:**
```json
{
  "evidence": {
    "urls_tested": ["https://staging.example.com/dashboard"],  // REQUIRED - REAL app pages
    "console_clean": true,
    "web_smoke_summary": ".claude/web-smoke/summary.json"      // REQUIRED - proof exists
  }
}
```

The stop hook will **BLOCK** checkpoints where:
- `web_testing_done: true` but no Surf artifacts exist
- `urls_tested` contains only health endpoints
- `urls_tested` is empty

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
| `validation_tests_defined` | bool | if code changed | Did you define fix-specific tests? |
| `validation_tests_passed` | bool | if code changed | Did ALL validation tests pass? |
| `validation_tests_passed_at_version` | string | if tests run | Git version when tests passed |
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
│     f. FIX VALIDATION TESTS (Phase 3.7 - MANDATORY)                 │
│        └─► Define: What would PROVE this fix worked?                │
│        └─► Execute tests, record actual values                      │
│        └─► If ANY test fails → SURFACE ISSUE → FIX → re-test       │
│        └─► Save artifacts to .claude/validation-tests/              │
│                                                                      │
│     g. WEB SMOKE VERIFY (Surf CLI first, Chrome MCP fallback)       │
│        └─► Run: python3 ~/.claude/hooks/surf-verify.py              │
│        └─► Check .claude/web-smoke/summary.json passed              │
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
    "method": "surf_cli",
    "artifacts": ".claude/web-smoke/"
  }
}
```

## Phase 0: Pre-Flight Check

### State File (Automatic)

**The state file is created automatically by the `skill-state-initializer.py` hook when you invoke `/appfix`.**

When you type `/appfix`, "fix the app", or similar triggers, the UserPromptSubmit hook immediately creates:
- `.claude/appfix-state.json` - Project-level state for iteration tracking
- `~/.claude/appfix-state.json` - User-level state for cross-repo detection

This happens BEFORE Claude starts processing, ensuring auto-approval hooks are active from the first tool call.

**You do NOT need to manually create these files.** The hook handles it automatically.

<details>
<summary>Manual fallback (only if hook fails)</summary>

```bash
# Only use this if the automatic hook didn't create the files
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
  "plan_mode_completed": false,
  "parallel_mode": false,
  "agent_id": null,
  "worktree_path": null,
  "coordinator": true,
  "services": {},
  "fixes_applied": [],
  "verification_evidence": null
}
EOF
```
</details>

### State File Schema

| Field | Type | Purpose |
|-------|------|---------|
| `iteration` | int | Current fix-verify iteration (starts at 1) |
| `started_at` | string | ISO timestamp when appfix started |
| `plan_mode_completed` | bool | True after ExitPlanMode called (Edit/Write blocked if false on iteration 1) |
| `parallel_mode` | bool | True if running as parallel agent |
| `agent_id` | string | Unique ID if running in worktree |
| `worktree_path` | string | Path to worktree if isolated |
| `coordinator` | bool | True if this is the coordinator (not a subagent) |
| `services` | object | Service health status tracking |
| `fixes_applied` | array | Log of fixes applied per iteration |
| `verification_evidence` | object | Browser verification results |

**Hook enforcement**: The `plan-mode-enforcer.py` hook blocks Edit/Write tools until `plan_mode_completed: true` on the first iteration. This ensures you explore the codebase and read docs before making changes.

**Why both files?**
- **User-level (`~/.claude/appfix-state.json`)**: Ensures stop hook validation works even when you switch to another repo (e.g., terraform-infra) to fix the root cause. Without this, the stop hook only checks the current working directory.
- **Project-level (`.claude/appfix-state.json`)**: Tracks iteration state, fixes applied, plan mode completion, and verification evidence for the specific project.

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

## Phase 0.75: Parallel Task Distribution (After Plan Approval)

**After ExitPlanMode, BEFORE executing sequentially, analyze your plan for parallelizable work.**

### When to Parallelize

Parallelize when your plan contains 2+ independent work items that:
- Touch different files or directories
- Don't depend on each other's output
- Can be explored, implemented, or tested independently

**Skip parallelization** when:
- The plan has only 1 task
- Tasks have sequential dependencies (B needs A's output)
- All changes are in the same file

### How to Parallelize

**Launch multiple Task tool calls in a SINGLE message** (this is what makes them parallel):

```
// CORRECT — parallel (single message, multiple tool calls):
Task(description="Fix auth middleware", subagent_type="general-purpose", prompt="...")
Task(description="Fix CORS config", subagent_type="general-purpose", prompt="...")
Task(description="Update error handlers", subagent_type="general-purpose", prompt="...")

// WRONG — sequential (separate messages, waits between each):
Task(...) → wait → Task(...) → wait → Task(...)
```

### Subagent Types for Execution

| Work Type | Subagent Type | Use When |
|-----------|--------------|----------|
| Research/exploration | `Explore` | Finding files, understanding patterns, reading code |
| Code changes | `general-purpose` | Editing files, implementing features, fixing bugs |
| Build/test commands | `Bash` | Running linters, tests, builds |

### Task Prompt Requirements

Each Task agent prompt MUST include:
1. **Full context** — The agent has NO memory of your plan or the fix-verify loop. Include ALL relevant file paths, error details, and requirements
2. **Specific scope** — Exactly which files/directories to work on
3. **Expected output** — What the agent should produce or change
4. **Constraints** — Don't modify files outside your scope

### After Parallel Tasks Complete

1. Review all agent results for correctness
2. Resolve any conflicts (if agents touched overlapping files)
3. Continue with sequential phases (health check, log collection, commit, deploy, verify)

## Phase 1: Health Check

Check each service's health endpoint from `service-topology.md`:

```bash
curl -sf https://[service-url]/health || echo "UNHEALTHY"
```

Run initial browser health check (Chrome MCP or /webtest for diagnosis, NOT final verification).

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

## Phase 3.7: Fix Validation Tests (MANDATORY for code changes)

**Before claiming completion, you MUST define and execute tests that PROVE the fix worked.**

### Why This Matters

Web smoke tests prove "the app loads" but NOT "the fix worked."

**Example failure mode:**
- Fix: Notes summarization pipeline
- Web test: Dashboard loads ✓
- Reality: Werner Iwens still has `bullhorn_notes_summary_json = NULL`
- Result: Fix DIDN'T WORK but we claimed success!

### Step 1: Define Validation Tests

Ask yourself: **"What would PROVE this specific fix worked?"**

| Fix Type | Example Test |
|----------|--------------|
| Database field populated | Query returns expected value |
| API endpoint fixed | Endpoint returns 200 with expected body |
| UI element appears | Page contains expected text/element |
| Error resolved | Log no longer contains error pattern |
| Config applied | Config query returns new value |

**Add tests to checkpoint:**

```json
{
  "validation_tests": {
    "fix_description": "Notes summarization should populate bullhorn_notes_summary_json",
    "tests": [
      {
        "id": "notes_summary_populated",
        "description": "Werner Iwens' notes should be summarized",
        "type": "database_query",
        "expected": "NOT NULL"
      }
    ]
  }
}
```

### Step 2: Execute Tests

Run each test and record actual results:

```bash
# Database query example
RESULT=$(psql $DATABASE_URL -t -c "SELECT bullhorn_notes_summary_json FROM persons WHERE person_id = 123")

# API endpoint example
curl -s https://staging.example.com/api/notes/123 | jq '.summary'

# Page content example (via Surf CLI)
surf navigate "https://staging.example.com/persons/123"
surf page.text | grep -i "notes summary"
```

### Step 3: If Tests FAIL - Surface the Issue

**CRITICAL: Failed tests surface issues that must be fixed!**

Do NOT:
- Claim completion with failed tests
- Skip tests because "the app works"
- Weaken expected values to make tests pass
- Remove failing tests

DO:
- Investigate WHY the test failed
- Fix the root cause
- Re-run the test
- Loop until ALL tests pass

### Step 4: Update Checkpoint with Results

After all tests pass:

```json
{
  "validation_tests": {
    "tests": [
      {
        "id": "notes_summary_populated",
        "description": "Werner Iwens' notes should be summarized",
        "type": "database_query",
        "expected": "NOT NULL",
        "actual": "{\"summary\": \"Werner is a senior consultant...\"}",
        "passed": true,
        "tested_at": "2026-01-27T10:30:00Z"
      }
    ],
    "summary": {
      "total": 1,
      "passed": 1,
      "failed": 0,
      "last_run_version": "abc1234"
    }
  },
  "self_report": {
    "validation_tests_defined": true,
    "validation_tests_passed": true,
    "validation_tests_passed_at_version": "abc1234"
  }
}
```

### Step 5: Create Artifacts

Save evidence to `.claude/validation-tests/summary.json`:

```bash
mkdir -p .claude/validation-tests
cat > .claude/validation-tests/summary.json << 'EOF'
{
  "passed": true,
  "tested_at": "2026-01-27T10:30:00Z",
  "tested_at_version": "abc1234",
  "fix_description": "Notes summarization pipeline",
  "total_tests": 1,
  "passed_tests": 1,
  "failed_tests": 0,
  "tests": [{
    "id": "notes_summary_populated",
    "passed": true,
    "actual": "NOT NULL"
  }]
}
EOF
```

See `.claude/skills/appfix/references/validation-tests-contract.md` for full schema.

## Phase 4: Verification (MANDATORY)

**You cannot claim success without browser verification.**

### CRITICAL: Use Surf CLI First, Not Chrome MCP

**DO NOT reach for Chrome MCP tools.** Your first action in Phase 4 MUST be running Surf CLI.

The stop hook validates Surf artifacts in `.claude/web-smoke/`. If you skip Surf and use Chrome MCP, you must manually create artifacts AND set checkpoint fields manually. **This is error-prone and slower.**

```
CORRECT ORDER:
1. Try Surf CLI first (automatic artifact generation)
2. ONLY if Surf CLI fails → Fall back to Chrome MCP

INCORRECT:
- Calling mcp__claude-in-chrome__tabs_context as first verification step
- Using Chrome MCP when Surf CLI is available
- Skipping Surf because "Chrome is easier"
```

### Step 1: Run Surf CLI Verification (REQUIRED FIRST ATTEMPT)

```bash
# Check if Surf CLI is available
which surf && echo "Surf CLI available" || echo "FALLBACK: Surf not installed"

# If available, run verification (creates artifacts automatically)
python3 ~/.claude/hooks/surf-verify.py --urls "https://staging.example.com/dashboard" "https://staging.example.com/login"

# Or using URLs from service-topology.md
python3 ~/.claude/hooks/surf-verify.py --from-topology
```

### Step 2: Check Artifacts Were Created

```bash
ls -la .claude/web-smoke/
# Expected: summary.json, screenshots/, console.txt
cat .claude/web-smoke/summary.json
# Should show: "passed": true
```

### Step 3: If Surf Verification Fails

1. Check `.claude/web-smoke/summary.json` for error details
2. Check `.claude/web-smoke/console.txt` for console errors
3. Check `.claude/web-smoke/failing-requests.sh` for network errors
4. **Fix the actual issues** and re-run Surf verification
5. **DO NOT bypass by using Chrome MCP** - fix the real problems

**The stop hook validates these artifacts automatically.** If `summary.json` shows `passed: false`, you'll be blocked until you fix the issues.

### Step 4: Waiver File (for expected third-party errors only)

If you have expected third-party errors (analytics blocked, etc.), create `.claude/web-smoke/waivers.json`:
```json
{
  "console_patterns": ["analytics\\.js.*blocked"],
  "network_patterns": ["GET.*googletagmanager\\.com.*4\\d\\d"],
  "reason": "Third-party analytics blocked by privacy settings"
}
```

### Fallback: Chrome MCP (ONLY if Surf CLI is unavailable)

**Only use Chrome MCP if:**
- Surf CLI is not installed AND cannot be installed
- surf-verify.py script is missing
- Network/environment prevents Surf from running

If forced to use Chrome MCP:
```
- mcp__claude-in-chrome__navigate to the app URL
- mcp__claude-in-chrome__computer action=screenshot to capture state
- mcp__claude-in-chrome__read_console_messages to check for errors
```

**When using Chrome MCP, you MUST manually:**
1. Create `.claude/web-smoke/summary.json` with test results
2. Set `web_testing_done: true` in the checkpoint
3. Set `web_testing_done_at_version` to current git version

This is MORE work than using Surf CLI, which does all this automatically.

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
    "method": "surf_cli",
    "artifacts": ".claude/web-smoke/"
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

## Parallel Agent Isolation (Git Worktrees)

When running multiple agents in parallel, each agent should use its own **git worktree** to avoid conflicts on git operations, checkpoint files, and version tracking.

### Why Worktrees?

Without isolation, parallel agents cause:
- Race conditions on `git commit`/`git push`
- Checkpoint invalidation chaos (Agent A's version invalidated by Agent B's commit)
- Silent merge conflicts when editing same files

### Worktree Workflow for Appfix

```
COORDINATOR (main repo)
├── Creates worktrees for each agent
├── Each agent diagnoses/fixes independently
├── Sequential merge after completion
└── Single deployment after merge

AGENT WORKTREE
├── Own branch: claude-agent/{agent-id}
├── Own .claude/ directory (checkpoint, state)
├── Independent log collection
└── Independent version tracking
```

### Creating a Worktree for an Agent

```bash
# Coordinator creates worktree before spawning agent
python3 ~/.claude/hooks/worktree-manager.py create <agent-id>
# Returns: /tmp/claude-worktrees/<agent-id>

# Agent runs in worktree directory
cd /tmp/claude-worktrees/<agent-id>
# All git operations are isolated to this branch
```

### Merging Agent Work

```bash
# After agent completes, merge back to main
python3 ~/.claude/hooks/worktree-manager.py merge <agent-id>

# If conflict detected (exit code 2):
# - Coordinator must resolve or fall back to sequential execution

# Cleanup after merge
python3 ~/.claude/hooks/worktree-manager.py cleanup <agent-id>
```

### Conflict Strategy: Fail Fast

When a merge conflict is detected:
1. Abort the parallel approach
2. Fall back to sequential execution
3. Let the second agent rebase on the first agent's changes

This maintains autonomous execution without requiring human intervention for conflict resolution.

### Coordinator Deploy Pattern (CRITICAL for 10+ Parallel Agents)

**ONLY the coordinator deploys. Subagents NEVER deploy.**

This prevents deployment race conditions where Agent A deploys, then Agent B deploys over it, losing Agent A's changes.

```
COORDINATOR WORKFLOW:
1. Create worktrees:
   for agent_id in task_ids:
     path = python3 ~/.claude/hooks/worktree-manager.py create {agent_id}

2. Spawn Tasks (each gets worktree path in prompt):
   Task(prompt="... WORKING_DIRECTORY: /tmp/claude-worktrees/{agent_id} ...")

3. Wait for all Tasks

4. Sequential merge:
   for agent_id in task_ids:
     success, msg = python3 ~/.claude/hooks/worktree-manager.py merge {agent_id}
     if not success: ABORT parallel, fall back to sequential

5. SINGLE deploy (coordinator only):
   git push
   gh workflow run deploy.yml
   gh run watch --exit-status

6. Cleanup:
   for agent_id in task_ids:
     python3 ~/.claude/hooks/worktree-manager.py cleanup {agent_id}
```

**SUBAGENT RULES (enforced by state file):**
- Check state file: if `coordinator: false`, NEVER run `gh workflow run` or `git push`
- Commit locally in worktree only
- Mark `needs_deploy: true` in checkpoint
- Exit after local commit (coordinator handles push/deploy)

**How coordination state is detected:**
- `skill-state-initializer.py` automatically detects worktree context
- Sets `coordinator: false`, `parallel_mode: true` when in worktree
- Subagents can check `.claude/appfix-state.json`

### Garbage Collection for Stale Worktrees

If a coordinator crashes, worktrees become orphaned. The `session-snapshot.py` hook automatically cleans up stale worktrees at session start:

```bash
# Automatic cleanup: worktrees older than 8 hours are removed at session start

# Manual cleanup:
python3 ~/.claude/hooks/worktree-manager.py gc           # Default 8-hour TTL
python3 ~/.claude/hooks/worktree-manager.py gc 4         # Custom 4-hour TTL
python3 ~/.claude/hooks/worktree-manager.py gc --dry-run # Preview what would be cleaned
```

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
  - Surf CLI: python3 ~/.claude/hooks/surf-verify.py --urls "https://staging.example.com/dashboard"
  - Artifacts created: .claude/web-smoke/summary.json
  - Screenshots: 1 captured
  - Console: clean (no errors)
  - Stop hook auto-sets: web_testing_done: true

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

## Troubleshooting

### Hooks Not Working

**Symptom**: Auto-approval doesn't work, plan mode enforcer doesn't block, stop validator doesn't fire.

**Root Cause**: Hooks are captured at Claude Code session startup. Changes to hook files or state files don't take effect until a new session starts.

**Solution**:
1. Exit Claude Code completely
2. Start a new session: `claude`
3. Look for `SessionStart:` message confirming hooks loaded

### State File Not Detected

**Symptom**: Auto-approval hook returns silent passthrough (no output) instead of `{"behavior": "allow"}`.

**Root Cause**: The `is_autonomous_mode_active()` function looks for `.claude/appfix-state.json` (or godo-state.json) by walking up the directory tree. If not found, auto-approval is disabled.

**Solution**: The state file should be created automatically by `skill-state-initializer.py` when you type `/appfix`. If it's not working:

1. Check that the hook is registered in `~/.claude/settings.json` under UserPromptSubmit
2. Verify the hook file exists: `ls ~/.claude/hooks/skill-state-initializer.py`
3. Start a NEW Claude Code session (hooks are captured at startup)

**Manual fallback** (only if hook fails):
```bash
mkdir -p .claude
cat > .claude/appfix-state.json << 'EOF'
{
  "iteration": 1,
  "started_at": "2026-01-26T10:00:00Z",
  "plan_mode_completed": true,
  "parallel_mode": false,
  "agent_id": null,
  "worktree_path": null,
  "coordinator": true,
  "services": {},
  "fixes_applied": [],
  "verification_evidence": null
}
EOF
```

### PermissionRequest Hook Empty Stdin

**Symptom**: Auto-approval hook fails with JSONDecodeError.

**Root Cause**: `PermissionRequest` hooks may NOT receive JSON via stdin (unlike other hook types like PreToolUse, PostToolUse, Stop).

**Solution**: The `appfix-auto-approve.py` hook handles this by falling back to `os.getcwd()` when stdin is empty:
```python
stdin_data = sys.stdin.read()
if stdin_data.strip():
    input_data = json.loads(stdin_data)
    cwd = input_data.get("cwd", os.getcwd())
else:
    cwd = os.getcwd()  # Fallback for PermissionRequest hooks
```

### Verify Hook Installation

Run the doctor script:
```bash
./scripts/doctor.sh
```

Or manually test:
```bash
# Test state detection
python3 -c "
import sys
sys.path.insert(0, '$HOME/.claude/hooks')
from _common import is_autonomous_mode_active, is_appfix_active
print('is_appfix_active:', is_appfix_active('$(pwd)'))
print('is_autonomous_mode_active:', is_autonomous_mode_active('$(pwd)'))
"

# Test auto-approval hook
cd /path/to/project/with/state/file
echo "" | python3 ~/.claude/hooks/appfix-auto-approve.py
# Should output: {"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {"behavior": "allow"}}}
```

### Cross-Repo Detection Not Working

**Symptom**: When switching to terraform/infra repo to fix root cause, appfix mode not detected.

**Root Cause**: State file detection walks UP the directory tree, but if you're in a different repo, it won't find the original project's state file.

**Solution**: Create user-level state file that persists across repos:
```bash
mkdir -p ~/.claude
cat > ~/.claude/appfix-state.json << 'EOF'
{
  "started_at": "2026-01-26T10:00:00Z",
  "origin_project": "/path/to/original/project"
}
EOF
```

### Debug Log

All hooks log diagnostic info to `/tmp/claude-hooks-debug.log`:
```bash
tail -f /tmp/claude-hooks-debug.log
```

Check this log when hooks behave unexpectedly.
