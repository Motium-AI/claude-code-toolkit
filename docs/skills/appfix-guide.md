# /appfix - Autonomous App Debugging System

Complete guide to the `/appfix` skill for autonomous application debugging and recovery.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Prerequisites](#prerequisites)
4. [Usage](#usage)
5. [Workflow Phases](#workflow-phases)
6. [Completion Checkpoint](#completion-checkpoint)
7. [Verification](#verification)
8. [Linter Verification](#linter-verification)
9. [Infrastructure Sync](#infrastructure-sync)
10. [Log Collection](#log-collection)
11. [Fix Execution](#fix-execution)
12. [State Management](#state-management)
13. [Project Setup](#project-setup)
14. [Troubleshooting](#troubleshooting)
15. [Examples](#examples)

---

## Overview

`/appfix` is an autonomous debugging skill that diagnoses and fixes application failures without human intervention. It implements a fix-verify loop that:

1. Checks service health
2. Collects logs when failures are detected
3. Analyzes root causes
4. Creates and executes fix plans
5. Deploys changes
6. Verifies in browser until working

### Key Features

- **Autonomous Operation**: Runs without user confirmation once started
- **Deterministic Checkpoint**: Uses boolean self-report for reliable completion
- **Browser Verification**: Requires real browser testing via Chrome MCP
- **Trust-Based**: Trusts model to be honest, verifies via boolean checks

### When to Use

| Scenario | Use /appfix? |
|----------|--------------|
| Production is down | Yes |
| Staging deploy broke something | Yes |
| User reports a bug | Yes |
| Scheduled health check | Yes |
| Code review | No |
| New feature development | No |

---

## Architecture

### Deterministic Boolean Checkpoints

The `/appfix` skill uses a **completion checkpoint** that the stop hook validates deterministically:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     COMPLETION CHECKPOINT ARCHITECTURE                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  .claude/completion-checkpoint.json                                          │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ {                                                                     │   │
│  │   "self_report": {                                                    │   │
│  │     "is_job_complete": true/false,  ← BLOCKED if false               │   │
│  │     "web_testing_done": true/false, ← BLOCKED if false (frontend)    │   │
│  │     "deployed": true/false,         ← BLOCKED if false (code change) │   │
│  │     ...                                                               │   │
│  │   },                                                                  │   │
│  │   "reflection": {                                                     │   │
│  │     "what_remains": "none"          ← BLOCKED if not empty           │   │
│  │   }                                                                   │   │
│  │ }                                                                     │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  Stop Hook checks booleans deterministically.                                │
│  If any required field is false → BLOCKED with continuation prompt           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Why This Approach?

| Old Approach | Boolean Checkpoints |
|--------------|---------------------|
| Claude can rationalize around warnings | Must choose true/false |
| Complex regex validation | Simple boolean checks |
| Git diff tracking, timestamp validation | Just: is evidence complete? |
| Distrusts model with heuristics | Trusts model honesty |

### Philosophy

**The model must answer honestly:**
- "Did you test in the browser?" → true/false
- "Is the job actually complete?" → true/false
- "What remains?" → must be empty

If you answer `false`, you're blocked. If you answer `true` dishonestly, that's on you - but you can't accidentally stop early.

### Supporting Hooks

Appfix uses a 3-hook system to enforce autonomous operation:

| Hook | Event | Purpose |
|------|-------|---------|
| `plan-execution-reminder.py` | PostToolUse (ExitPlanMode) | Injects autonomous execution context after plan approval |
| `appfix-auto-approve.py` | PermissionRequest (*) | Auto-approves ALL tools when appfix state file exists |
| `stop-validator.py` | Stop | Validates completion checkpoint booleans before allowing stop |

**How they work together:**

```
1. User runs /appfix
   └─→ Skill creates .claude/appfix-state.json (enables auto-approval)

2. Claude enters plan mode, explores, exits
   └─→ plan-execution-reminder.py injects:
       • Fix-verify loop requirements
       • Checkpoint schema
       • "CONTINUE THE FIX-VERIFY LOOP NOW"

3. Claude requests Edit/Write/Bash permissions
   └─→ appfix-auto-approve.py detects state file → auto-approves

4. Claude tries to stop
   └─→ stop-validator.py checks checkpoint booleans
       • If any required boolean is false → BLOCKED with continuation prompt
       • If what_remains is not empty → BLOCKED
       • If all pass → ALLOWED
```

**Why `plan-execution-reminder.py` matters:**

Without this hook, Claude might:
- Ask for permission after exiting plan mode
- Suggest "next steps" instead of continuing
- Stop after making changes without verifying

The hook injects aggressive context that reminds Claude it's in an autonomous loop and must continue working until the checkpoint passes.

---

## Prerequisites

### Required Tools

```bash
# Azure CLI (for container logs)
az login

# GitHub CLI (for deployments)
gh auth login

# Chrome with Claude in Chrome extension (for browser testing)
# Or use /webtest skill
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LOGFIRE_READ_TOKEN` | Optional | Query LogFire for structured logs |
| `TEST_EMAIL` | Optional | Integration test user email |
| `TEST_PASSWORD` | Optional | Integration test user password |

**Note**: If credentials are missing and needed, the skill asks the user **once at start**, then proceeds autonomously.

### Project Files

Each project using `/appfix` needs:

```
project/
├── .claude/
│   └── skills/appfix/
│       └── references/
│           ├── service-topology.md  # REQUIRED - Service URLs
│           └── log-patterns.md      # Optional - Error patterns
```

**CRITICAL**: The `service-topology.md` file is **REQUIRED**. If missing, the skill stops and asks for service URLs.

> ⚠️ **PATH DISAMBIGUATION**
>
> Appfix reads configuration from **PROJECT-LOCAL** paths, not global toolkit paths:
>
> | Path Type | Location | Purpose |
> |-----------|----------|---------|
> | **Project-local** (use this) | `.claude/skills/appfix/references/` | Your project's service URLs, log patterns |
> | Global (toolkit) | `~/.claude/skills/appfix/` | Skill definition (SKILL.md) - not for project config |
>
> If appfix can't find `service-topology.md`, it will STOP and ask for service URLs.
> Always create project-local references, never edit the global toolkit.

---

## Usage

### Standard Usage

Simply invoke the skill:

```
/appfix
```

Or trigger with natural language:
- "fix the app"
- "debug production"
- "check staging"
- "why is it broken"

### The skill runs autonomously

The model:
1. Explores codebase and creates a fix plan
2. Executes fixes, commits, deploys
3. Verifies in browser via Chrome MCP
4. Updates completion checkpoint
5. Tries to stop - blocked if checkpoint fails
6. Continues working until checkpoint passes

---

## Workflow Phases

### Phase 0: Pre-Flight Checks

**CRITICAL: Create state file FIRST to enable auto-approval of plan mode.**

```bash
# Create state file IMMEDIATELY (enables auto-approval hooks)
mkdir -p .claude && echo '{"iteration":1,"started_at":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'","services":{},"fixes_applied":[],"verification_evidence":null}' > .claude/appfix-state.json
```

Then:
1. **Read project documentation** (MANDATORY):
   - Read `docs/index.md` - Project overview and architecture links
   - Read `docs/TECHNICAL_OVERVIEW.md` - System architecture and design
   - Update checkpoint: `docs_read_at_start: true`
2. Check for `.claude/skills/appfix/references/service-topology.md`
3. If missing: **STOP and ask user** for service URLs
4. Check credentials - if missing, ask **once at start**

**Why read docs first?** Understanding the architecture prevents:
- Fixing symptoms instead of root causes
- Breaking other components with your fix
- Missing context about how services interact

### Phase 0.5: Codebase Context (First Iteration Only)

**Mandatory on first iteration. Optional on subsequent iterations.**

1. Call `EnterPlanMode`
2. Explore: architecture, configs, recent commits
3. Write understanding to plan file
4. Call `ExitPlanMode`

On subsequent iterations, only enter plan mode if your hypothesis changes significantly.

### Phase 1: Health Check

Check each service's health endpoint:

```bash
curl -sf https://[service-url]/health || echo "UNHEALTHY"
```

Use Chrome MCP or /webtest for browser testing.

### Phase 2: Log Collection

Gather evidence from:

1. **Browser Console** - JavaScript errors, network failures
2. **Azure Container Logs** - Backend errors, stack traces
3. **LogFire** - Structured analysis

### Phase 3: Execute Fix

1. Apply code changes using Edit tool
2. Commit: `git add <files> && git commit -m "appfix: [description]"`
3. Push: `git push`
4. Deploy: `gh workflow run deploy.yml && gh run watch --exit-status`
5. Poll health endpoints

### Phase 4: Verification (MANDATORY)

**You cannot claim success without browser verification.**

**ALL appfix sessions require browser verification—regardless of change type.**

| Change Type | What to Verify in Browser |
|-------------|---------------------------|
| Code changes | Navigate to affected feature, confirm it works |
| Database changes | Navigate to page showing data, confirm it displays correctly |
| SQL schema changes | Test the feature that uses the new tables |
| Config changes | Verify the behavior changed as expected |
| Infrastructure changes | Confirm app loads and functions after infra fix |

**Example: Database-only session (resetting CV statuses)**
1. Run SQL to reset CV parsing queue
2. Navigate to `https://staging.example.com/candidates` via Chrome MCP
3. Take screenshot showing queue now displays correctly
4. Check console for errors
5. Record URL in `evidence.urls_tested`

**Example: Infrastructure-only session (increasing memory)**
1. Run `az containerapp update` to increase memory
2. Navigate to app's main page via Chrome MCP
3. Confirm app loads without OOM errors
4. Check console for errors
5. Record URL in `evidence.urls_tested`

**Steps:**
1. Use Chrome MCP to navigate to app and take screenshots
2. Check browser console for errors
3. Update both state files with actual URLs tested

---

## Completion Checkpoint

### Schema

Create `.claude/completion-checkpoint.json` before stopping.

#### Example: Code Changes Session

```json
{
  "self_report": {
    "code_changes_made": true,
    "web_testing_done": true,
    "web_testing_done_at_version": "abc1234",
    "api_testing_done": true,
    "api_testing_done_at_version": "abc1234",
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
    "what_was_done": "Fixed CORS config, deployed to staging, verified login works",
    "what_remains": "none",
    "blockers": null
  },
  "evidence": {
    "urls_tested": ["https://staging.example.com/dashboard"],
    "console_clean": true
  }
}
```

#### Example: Database-Only Session (No Code Changes)

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

**CRITICAL**: Even when `code_changes_made: false`, you MUST have `urls_tested` with actual URLs. The stop hook rejects `web_testing_done: true` with empty `urls_tested`.

### Field Requirements

| Field | Type | Required | Stop Hook Behavior |
|-------|------|----------|-------------------|
| `is_job_complete` | bool | yes | BLOCKED if false |
| `docs_read_at_start` | bool | yes (appfix) | BLOCKED if false |
| `web_testing_done` | bool | yes (appfix) | BLOCKED if false |
| `deployed` | bool | if code changed | BLOCKED if false |
| `linters_pass` | bool | if code changed | BLOCKED if false |
| `preexisting_issues_fixed` | bool | if code changed | BLOCKED if false |
| `az_cli_changes_made` | bool | yes | Track if az CLI used |
| `infra_pr_created` | bool | if az CLI used | BLOCKED if false |
| `console_errors_checked` | bool | yes (appfix) | BLOCKED if false |
| `docs_updated` | bool | conditional | Update relevant docs |
| `what_remains` | string | yes | BLOCKED if not empty |
| `evidence.urls_tested` | array | yes (appfix) | BLOCKED if empty when `web_testing_done: true` |

### Documentation Requirements (docs_updated)

Update these when your changes affect them:
- `docs/TECHNICAL_OVERVIEW.md` - Architectural changes, new services
- Module docs in `docs/` directory - Feature changes, API modifications
- `.claude/skills/*/references/` - Service topology, error patterns
- `.claude/MEMORIES.md` - Significant learnings only (not changelog)

### What Triggers Blocking

The stop hook blocks you if:
- Any required boolean is `false`
- `what_remains` has content (not "none" or empty)
- Checkpoint file doesn't exist (for significant changes)
- A version-dependent field is **STALE** (code changed since it was set)

### Version Tracking

Version-dependent checkpoints become stale when code changes after they're set:

| Field | Must Include |
|-------|--------------|
| `deployed` | `deployed_at_version` |
| `linters_pass` | `linters_pass_at_version` |
| `web_testing_done` | `web_testing_done_at_version` |
| `console_errors_checked` | `console_errors_checked_at_version` |
| `api_testing_done` | `api_testing_done_at_version` |

**Example scenario**:
```
1. Deploy code → deployed: true, deployed_at_version: "abc1234"
2. Run test → test fails
3. Fix code → git commit (now at "def5678")
4. Try stop → BLOCKED: deployed is STALE
5. Redeploy → deployed_at_version: "def5678"
6. Try stop → ALLOWED
```

**How to get current version**:
```bash
git rev-parse --short HEAD
```

**Version format**:
- Clean commit: `abc1234`
- With uncommitted changes: `abc1234-dirty-def5678`

---

## Verification

### Surf CLI Web Verification (PREFERRED)

AppFix uses a **hybrid verification approach**:

| Method | Purpose | When to Use |
|--------|---------|-------------|
| **Surf CLI** | Deterministic "web smoke" verification | Primary method - produces artifacts |
| **Chrome MCP** | Interactive debugging/exploration | Fallback when Surf isn't enough |

#### Install Surf CLI

```bash
npm install -g @nicobailon/surf-cli
```

#### Run Verification

```bash
# Using explicit URLs
python3 ~/.claude/hooks/surf-verify.py --urls "https://staging.example.com/dashboard"

# Or using URLs from service-topology.md
python3 ~/.claude/hooks/surf-verify.py --from-topology
```

#### Check Artifacts

Artifacts are produced in `.claude/web-smoke/`:

```
.claude/web-smoke/
├── summary.json          # Pass/fail + metadata
├── screenshots/          # Visual proof pages loaded
│   └── page_0.png
├── console.txt           # Browser console output
└── failing-requests.sh   # Curl repros for failed requests
```

The stop hook validates these artifacts automatically. If `summary.json` shows `passed: false`, you'll be blocked until you fix the issues.

#### Handling Expected Errors

For third-party errors (analytics blocked, etc.), create `.claude/web-smoke/waivers.json`:

```json
{
  "console_patterns": ["analytics\\.js.*blocked"],
  "network_patterns": ["GET.*googletagmanager\\.com.*4\\d\\d"],
  "reason": "Third-party analytics blocked by privacy settings"
}
```

#### Artifact Version Tracking

Artifacts become stale when code changes:

```
tested_at_version: abc1234
current git version: def5678  ← Different!
→ STALE: Must re-verify
```

See [Web Smoke Contract](../../config/skills/appfix/references/web-smoke-contract.md) for full artifact schema.

### Fallback: Chrome MCP

When Surf CLI is not available or for interactive debugging:

```
1. mcp__claude-in-chrome__navigate - Go to app URL
2. mcp__claude-in-chrome__computer action=screenshot - Capture state
3. mcp__claude-in-chrome__read_console_messages - Check for errors
```

When using Chrome MCP, you must manually set `web_testing_done: true` in the checkpoint.

### Verification Checklist

- [ ] Navigate to actual app (not just /health)
- [ ] Take screenshot showing data loaded
- [ ] Check console has ZERO errors
- [ ] Data actually displays (not spinner)

### Update Both Files After Verification

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
    "web_testing_done": true,
    "console_errors_checked": true,
    "is_job_complete": true
  },
  "reflection": {
    "what_remains": "none"
  }
}
```

---

## Linter Verification

**Phase 3.5: Run after code changes, before verification.**

### Auto-Detect Linters

The skill auto-detects which linters are available:

```bash
# JavaScript/TypeScript projects
[ -f package.json ] && npm run lint 2>/dev/null || npx eslint . --ext .js,.jsx,.ts,.tsx
[ -f tsconfig.json ] && npx tsc --noEmit

# Python projects
[ -f pyproject.toml ] && ruff check --fix .
[ -f pyrightconfig.json ] && pyright
```

### Strict Policy: No Pre-Existing Exceptions

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
- Create technical debt that compounds
- "Not my problem" culture leads to code rot

### Troubleshooting Linter Failures

| Issue | Solution |
|-------|----------|
| "Cannot find module" errors | Run `npm install` first |
| Type errors in third-party code | Add to `exclude` in tsconfig.json |
| Linter config missing | Create `.eslintrc.js` or `ruff.toml` |
| Too many errors to fix | Prioritize errors in files YOU changed |

---

## Infrastructure Sync

**Phase 3.6: Required when `az CLI` commands modify infrastructure.**

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
   git add .
   git commit -m "appfix: Sync infrastructure state"
   gh pr create --title "Sync infra changes from appfix" --body "..."
   ```

5. **Update checkpoint**: `az_cli_changes_made: true`, `infra_pr_created: true`

### Why This Matters

Infrastructure drift causes:
- Next deploy overwrites your fix
- IaC state doesn't match reality
- Team confusion about actual configuration
- Compliance and audit issues

### Troubleshooting Infra Sync

| Issue | Solution |
|-------|----------|
| Infra repo not specified | Add to `service-topology.md` |
| No write access to infra repo | Fork and create PR from fork |
| Unsure which IaC files to update | Search for resource name in repo |

---

## Log Collection

### Priority Order

1. **Browser Console** - JavaScript errors, network failures
2. **Azure Container Logs** - Backend errors, stack traces
3. **LogFire** - Structured analysis
4. **GitHub Actions** - Deploy failures

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

---

## Fix Execution

### Code Change Best Practices

1. **Minimal changes** - Fix only what's broken
2. **No side effects** - Don't refactor while fixing
3. **Add logging** - Help future debugging

### Deployment Flow

```bash
# 1. Commit changes
git add <specific files> && git commit -m "appfix: [description]"
git push

# 2. Trigger deployment
gh workflow run deploy.yml -f environment=staging

# 3. Watch progress - CRITICAL: exits non-zero on failure
gh run watch --exit-status || { echo "Deploy failed!"; exit 1; }

# 4. Poll health (adaptive)
for i in {1..12}; do curl -sf "$HEALTH_URL" && break || sleep 5; done
```

---

## State Management

### State File Location

```
.claude/appfix-state.json
```

### State Schema

```json
{
  "iteration": 2,
  "started_at": "2025-01-24T10:00:00Z",
  "services": {
    "frontend": {
      "healthy": true,
      "last_error": null
    },
    "backend": {
      "healthy": false,
      "last_error": "500 on /health"
    }
  },
  "fixes_applied": [
    {
      "iteration": 1,
      "description": "Added null check to auth middleware",
      "files": ["app/middleware/auth.py"],
      "deployed": true
    }
  ],
  "verification_evidence": {
    "url_verified": "https://staging.example.com/dashboard",
    "console_clean": true,
    "verified_at": "2025-01-24T10:30:00Z",
    "method": "chrome_mcp"
  }
}
```

---

## Project Setup

### Step 1: Create Directory Structure

```bash
mkdir -p .claude/skills/appfix/references
```

### Step 2: Create Service Topology

Create `.claude/skills/appfix/references/service-topology.md`:

```markdown
# Service Topology

| Service | Staging URL | Health Endpoint |
|---------|-------------|-----------------|
| Frontend | https://staging.example.com | /api/health |
| Backend | https://api-staging.example.com | /health |

## Deployment Commands

### Frontend
gh workflow run frontend-ci.yml -f environment=staging

### Backend
gh workflow run backend-ci.yml -f environment=staging

## Infrastructure Repository (for infra sync)
https://github.com/org/infra-repo
```

### Step 3: Create Log Patterns (Optional)

Create `.claude/skills/appfix/references/log-patterns.md` to help Claude recognize common errors:

```markdown
# Log Patterns

## Backend (Python/uvicorn)

| Pattern | Meaning | Common Fix |
|---------|---------|------------|
| `ERROR: Connection refused` | Database/Redis unreachable | Check connection string, verify service is running |
| `422 Unprocessable Entity` | Request validation failed | Check request body against schema |
| `401 Unauthorized` | Auth token invalid/expired | Check Clerk/auth config, refresh tokens |
| `CORS error` | Cross-origin blocked | Update CORS allowed origins |
| `OOMKilled` | Container ran out of memory | Increase memory limits in container config |

## Frontend (Next.js)

| Pattern | Meaning | Common Fix |
|---------|---------|------------|
| `Hydration mismatch` | Server/client HTML differs | Check for browser-only code in SSR |
| `Failed to fetch` | API call failed | Check API URL, CORS, network |
| `Module not found` | Missing dependency | Run `npm install`, check import paths |
| `NEXT_PUBLIC_*` undefined | Env var not exposed | Prefix with NEXT_PUBLIC_ and rebuild |

## Docker/Container

| Pattern | Meaning | Common Fix |
|---------|---------|------------|
| `exec format error` | Wrong architecture | Rebuild for correct platform (amd64/arm64) |
| `no space left on device` | Disk full | Clean unused images, increase volume |
| `port already in use` | Port conflict | Change port or stop conflicting container |

## Azure Container Apps

| Pattern | Meaning | Common Fix |
|---------|---------|------------|
| `Revision failed to provision` | Container startup failed | Check container logs, verify image exists |
| `Ingress timeout` | Health check failing | Increase timeout, check health endpoint |
| `Scale to zero` | No traffic, app sleeping | Configure min replicas if needed |
```

---

## Troubleshooting

### Common Issues

#### "Checkpoint validation failed"

Your checkpoint has incomplete booleans. Check:
1. `is_job_complete` - Are you honestly done?
2. `docs_read_at_start` - Did you read project docs first?
3. `web_testing_done` - Did you verify in browser?
4. `linters_pass` - Did all linters pass with zero errors?
5. `what_remains` - Is it empty or "none"?

#### "Stop hook blocked me"

This is expected when work is incomplete. The hook checks your honest self-report:
- If you said `is_job_complete: false`, you're blocked
- If you said `docs_read_at_start: false` in appfix mode, you're blocked
- If you said `web_testing_done: false` and there are frontend changes, you're blocked
- If you said `linters_pass: false` and there are code changes, you're blocked
- If you said `az_cli_changes_made: true` but `infra_pr_created: false`, you're blocked
- Complete the work, update checkpoint, try again

#### "linters_pass is false"

The stop hook requires all linters to pass when code changes are made:
1. Run `npm run lint` or `ruff check .` to see errors
2. Fix ALL errors, including pre-existing ones
3. "These errors aren't related to our code" is NOT an acceptable excuse
4. Update checkpoint: `linters_pass: true`, `preexisting_issues_fixed: true`

#### "docs_read_at_start is false"

In appfix mode, you must read project documentation before starting:
1. Read `docs/index.md` - Project overview
2. Read `docs/TECHNICAL_OVERVIEW.md` - System architecture
3. Update checkpoint: `docs_read_at_start: true`

#### "infra_pr_created is false"

If you made infrastructure changes with az CLI:
1. Document changes in `.claude/infra-changes.md`
2. Clone infra repo (see `service-topology.md`)
3. Update IaC files to match your az CLI changes
4. Create PR: `gh pr create --title "Sync infra changes from appfix"`
5. Update checkpoint: `infra_pr_created: true`

#### "deployed is STALE" or other version-dependent field

A checkpoint was set at an older code version:
1. The code changed AFTER you deployed/tested/linted
2. Re-run that step with the current code:
   - STALE deployed → redeploy
   - STALE linters_pass → rerun linters
   - STALE web_testing_done → retest in browser
3. Get current version: `git rev-parse --short HEAD`
4. Update checkpoint with new version:
   ```json
   "deployed": true,
   "deployed_at_version": "<current-version>"
   ```

#### "web_smoke: No summary.json found"

Surf CLI verification hasn't been run yet:
1. Install Surf: `npm install -g @nicobailon/surf-cli`
2. Run verification: `python3 ~/.claude/hooks/surf-verify.py --urls "https://..."`
3. Or use Chrome MCP as fallback and manually set `web_testing_done: true`

#### "web_smoke: Artifacts are STALE"

Code changed after verification was run:
1. Get current version: `git rev-parse --short HEAD`
2. Re-run Surf verification with current code
3. New artifacts will include the current version hash

#### "web_smoke: Verification FAILED"

The Surf CLI found errors:
1. Check `.claude/web-smoke/console.txt` for console errors
2. Check `.claude/web-smoke/failing-requests.sh` for network errors
3. Fix the errors in your code
4. Re-run verification

If errors are expected (third-party), create waivers:
```json
// .claude/web-smoke/waivers.json
{
  "console_patterns": ["analytics\\.js.*blocked"],
  "reason": "Third-party analytics blocked"
}
```

#### "surf: command not found"

Surf CLI is not installed:
```bash
npm install -g @nicobailon/surf-cli
```

#### "Chrome MCP not responding"

Check:
1. Chrome is running with Claude in Chrome extension
2. Tab context is available: `mcp__claude-in-chrome__tabs_context_mcp`
3. Create a new tab if needed

#### "Verification evidence incomplete"

Check that your appfix-state.json has all 4 required fields:
- `url_verified` - Must NOT be localhost
- `console_clean` - Must be `true`
- `verified_at` - Must be an ISO timestamp
- `method` - Must specify how verified

---

## Examples

### Example 1: Login Page Broken

```
[PHASE 1] Health Check
  ✓ Frontend: 200 on /
  ✓ Backend: 200 on /health
  ✗ Chrome MCP: login form submission fails

[PHASE 2] Log Collection
  Azure: ERROR auth.py:45 - Clerk key invalid

[PHASE 3] Execute Fix
  - Edit: Update Clerk config
  - Commit: "appfix: Fix Clerk configuration"
  - Deploy: gh workflow run + wait

[PHASE 4] Verification
  - Chrome MCP: login successful
  - Console: clean

[UPDATE CHECKPOINT]
  - is_job_complete: true
  - web_testing_done: true
  - what_remains: "none"

[TRY TO STOP]
  → Stop hook validates checkpoint
  → All booleans pass

[SUCCESS] APPFIX COMPLETE
```

### Example 2: Dashboard Not Loading

```
[PHASE 0.5] Codebase Context
  → Recent commits show API endpoint change

[PHASE 1] Health Check
  ✓ All health endpoints OK
  ✗ Chrome MCP: dashboard shows empty

[PHASE 2] Log Collection
  - Network: GET /api/data returns 404
  - Console: "Failed to fetch"

[PHASE 3] Execute Fix
  - Edit: Fix API route path
  - Deploy

[PHASE 4] Verification
  - Chrome MCP: Dashboard shows 20 items
  - Console: clean

[UPDATE CHECKPOINT]
  - is_job_complete: true
  - web_testing_done: true

[SUCCESS] APPFIX COMPLETE
```

### Example 3: Blocked by Incomplete Checkpoint

```
[PHASE 4] Verification
  - Skipped browser testing (assumed it works)

[UPDATE CHECKPOINT]
  - is_job_complete: true
  - web_testing_done: false  ← HONEST
  - what_remains: "none"

[TRY TO STOP]
  → Stop hook checks checkpoint
  ❌ web_testing_done is false - frontend changes require browser testing

[CONTINUE WORKING]
  → Use Chrome MCP to verify
  → Update checkpoint with true values

[TRY TO STOP AGAIN]
  → All checks pass

[SUCCESS]
```

---

## Reference

### Files

| File | Location | Purpose |
|------|----------|---------|
| `SKILL.md` | `prompts/config/skills/appfix/SKILL.md` | Main skill definition |
| Completion checkpoint | `.claude/completion-checkpoint.json` | Boolean self-report |
| State file | `.claude/appfix-state.json` | Runtime state |
| Service topology | `.claude/skills/appfix/references/service-topology.md` | Service URLs |

### Environment Variables

| Variable | Description |
|----------|-------------|
| `LOGFIRE_READ_TOKEN` | LogFire API access |
| `TEST_EMAIL` | Integration test user |
| `TEST_PASSWORD` | Integration test password |

### Exit Conditions

| Condition | Result |
|-----------|--------|
| All checkpoint booleans pass | Success - stop allowed |
| Any required boolean is false | Blocked - continue working |
| what_remains not empty | Blocked - continue working |
| Missing required credentials | Ask user once, then continue |
| Infrastructure completely down | Exit with error |
