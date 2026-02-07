---
name: appfix
description: Autonomous app debugging system. Checks environment health, diagnoses failures via logs, creates fix plans, auto-executes fixes, and loops until all services are healthy. Use when asked to "fix the app", "debug production", "check staging", or "/appfix".
---

# Autonomous App Debugging (/appfix)

> **Recommended**: Use `/repair` instead - it auto-detects web vs mobile and routes appropriately.
> `/appfix` is the internal web debugging skill. Use it directly only when you specifically want
> web debugging without platform detection.

Autonomous debugging skill that iterates until all services are healthy and verified in browser.

> `/appfix` is a debugging specialization of `/build`. It inherits the completion checkpoint
> architecture and adds debugging-specific phases (health checks, log collection, service topology).

## Triggers

- `/appfix`, "fix the app", "debug production", "check staging", "why is it broken"

## CRITICAL: Autonomous Execution Rules

**THIS WORKFLOW IS 100% AUTONOMOUS. YOU MUST:**

1. **NEVER ask for confirmation** — No "Should I commit?", "Should I deploy?"
2. **Auto-commit and push** — Commit and push immediately after fixes
3. **Auto-deploy** — Trigger deployments without asking
4. **Complete verification** — Test in browser via Surf CLI
5. **Fill out checkpoint honestly** — The stop hook checks your booleans

**Only stop when the checkpoint passes. If booleans say the job isn't done, you'll be blocked.**

**Credentials exception**: If missing (LOGFIRE_READ_TOKEN, TEST_EMAIL, TEST_PASSWORD), ask user **once at start**. Then proceed autonomously.

## Completion Checkpoint

Before stopping, create `.claude/completion-checkpoint.json`:

```json
{
  "self_report": {
    "is_job_complete": true,
    "code_changes_made": true,
    "linters_pass": true,
    "category": "bugfix"
  },
  "reflection": {
    "what_was_done": "Fixed CORS config, deployed, verified login works",
    "what_remains": "none",
    "key_insight": "Reusable lesson for future sessions (>50 chars)",
    "search_terms": ["cors", "deployment", "login"]
  },
  "evidence": {
    "urls_tested": ["https://staging.example.com/dashboard"],
    "console_clean": true
  }
}
```

| Field | Type | Required | Meaning |
|-------|------|----------|---------|
| `is_job_complete` | bool | yes | Is the job actually done? |
| `code_changes_made` | bool | yes | Were code files modified? |
| `linters_pass` | bool | if code changed | Did all linters pass? |
| `category` | string | yes | bugfix, gotcha, architecture, pattern, config, refactor |
| `what_was_done` | string | yes | >20 chars describing work |
| `what_remains` | string | yes | Must be "none" to allow stop |
| `key_insight` | string | yes | >50 chars — the reusable LESSON |
| `search_terms` | list | yes | 2-7 concept keywords |

Extra fields (evidence, urls_tested, etc.) are allowed — the stop-validator ignores unknown keys.

## Workflow

### Phase 0: Pre-Flight Check

Create `.claude/autonomous-state.json` with `"mode": "repair"` at activation.

1. **Read project documentation**:
   - **If QMD available**: `qmd_search "project architecture overview"` — faster, semantic
   - **If no QMD**: Read `docs/index.md` and `docs/TECHNICAL_OVERVIEW.md`
2. Check for `.claude/skills/appfix/references/service-topology.md`
3. If missing: **STOP and ask user** for service URLs
4. Check credentials — ask user **ONCE** if missing

### Phase 0.5: Codebase Context (First Iteration Only)

1. Call `EnterPlanMode`
2. **FIRST: Temporal causality checkpoint**
   - `git log --oneline --since="48 hours ago"` — What changed recently?
   - Does symptom timing correlate with any recent change?
   - If correlation exists → that change is your primary hypothesis
3. Explore: architecture, configs, error patterns
4. Write understanding to plan file
5. Call `ExitPlanMode`

### Phase 0.75: Parallel Task Distribution

After ExitPlanMode, analyze plan for 2+ independent work items. Launch multiple Task tool calls in a **SINGLE message** for parallel execution. Each agent needs full context (file paths, errors, requirements).

| Work Type | Subagent Type |
|-----------|--------------|
| Research/exploration | `Explore` |
| Code changes | `general-purpose` |
| Build/test commands | `Bash` |

### Phase 1: Health Check

Check each service from `service-topology.md`:
```bash
curl -sf https://[service-url]/health || echo "UNHEALTHY"
```

### Phase 2: Log Collection

- **Azure**: `az containerapp logs show --name [app] --resource-group [rg] --type console --tail 100`
- **LogFire**: `curl -H "Authorization: Bearer $LOGFIRE_READ_TOKEN" "https://logfire-api.pydantic.dev/v1/query?level=error&since=1h"`
- **Browser**: Chrome MCP `read_console_messages`

### Phase 3: Execute Fix

1. **Apply** code changes with Edit tool
2. **Commit and push**: `git add <files> && git commit -m "appfix: [description]" && git push`
3. **Deploy**: `gh workflow run deploy.yml -f environment=staging && gh run watch --exit-status`
4. **Health poll**: `for i in {1..12}; do curl -sf "$HEALTH_URL" && break || sleep 5; done`

### Phase 3.5: Linter Verification (MANDATORY)

Auto-detect and run ALL linters:
```bash
[ -f package.json ] && npm run lint
[ -f tsconfig.json ] && npx tsc --noEmit
[ -f pyproject.toml ] && ruff check --fix .
```

**Fix ALL errors including pre-existing ones.** No exceptions: "not my code" is prohibited.

### Phase 3.6: Infrastructure Sync (if az CLI used)

<reference path="references/infrastructure-sync.md" />

### Phase 3.7: Fix Validation Tests (MANDATORY for code changes)

Ask: **"What would PROVE this specific fix worked?"** Web smoke tests prove "the app loads" but NOT "the fix worked."

1. Define tests in checkpoint `validation_tests.tests` array
2. Execute tests, record actual results
3. If tests FAIL → fix root cause → re-run
4. Save artifacts to `.claude/validation-tests/summary.json`

### Phase 4: Browser Verification (MANDATORY)

**Use Surf CLI first, Chrome MCP only as fallback.**

```bash
python3 ~/.claude/hooks/surf-verify.py --urls "https://staging.example.com/dashboard"
cat .claude/web-smoke/summary.json  # Must show passed: true
```

Artifacts in `.claude/web-smoke/` are validated by the stop hook. If `passed: false`, you're blocked until issues are fixed.

<reference path="references/surf-verification.md" />

### Phase 4.2: Console Check

- ZERO uncaught JavaScript errors
- ZERO network requests returning 500
- Data actually displays (not spinner/loading state)

## State File

`.claude/autonomous-state.json` tracks iteration state (created at activation with `"mode": "repair"`):

| Field | Purpose |
|-------|---------|
| `iteration` | Current fix-verify iteration |
| `plan_mode_completed` | True after ExitPlanMode (blocks Edit/Write if false on iteration 1) |
| `coordinator` | True if not a subagent |
| `services` | Service health tracking |
| `fixes_applied` | Log of fixes per iteration |
| `verification_evidence` | Browser verification results |

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `LOGFIRE_READ_TOKEN` | Query LogFire API |
| `TEST_EMAIL` / `TEST_PASSWORD` | Integration test credentials |

## Safety Gate (Production Only)

Pause for human confirmation ONLY for:
- **Production** environment targeting
- **Destructive** operations (delete, drop, truncate)
- **Secrets** exposure

All other actions proceed autonomously.

## Exit Conditions

| Condition | Result |
|-----------|--------|
| All booleans true, `what_remains: "none"` | SUCCESS — stop allowed |
| Any required boolean false | BLOCKED — continue working |
| Missing credentials | ASK USER (once) |

## Skill Fluidity

You may use techniques from any skill for sub-problems without switching modes. Your autonomous state and checkpoint remain governed by /appfix.

## Reference Files

| Reference | Path |
|-----------|------|
| Service topology | `references/service-topology.md` |
| Full checkpoint schema | `references/checkpoint-schema.md` |
| Surf verification guide | `references/surf-verification.md` |
| Infrastructure sync | `references/infrastructure-sync.md` |
| Worktree isolation | `references/worktree-guide.md` |
| Troubleshooting | `references/troubleshooting.md` |
| Validation test contract | `references/validation-tests-contract.md` |
| Web smoke contract | `references/web-smoke-contract.md` |
| Debugging rubric | `references/debugging-rubric.md` |
