---
name: godo
description: Task-agnostic autonomous execution. Identifies any task and executes it through a complete fix-verify loop until done. Use when asked to "go do", "just do it", "execute this", or "/godo".
---

# Autonomous Task Execution (/godo)

Task-agnostic autonomous execution skill that iterates until the task is complete and verified.

## Architecture: Completion Checkpoint

This workflow uses a **deterministic boolean checkpoint** to enforce completion:

```
┌─────────────────────────────────────────────────────────────────┐
│  STOP HOOK VALIDATION                                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Load .claude/completion-checkpoint.json                         │
│                                                                  │
│  Check booleans deterministically:                               │
│    - is_job_complete: false → BLOCKED                            │
│    - web_testing_done: false → BLOCKED                           │
│    - deployed: false (if code changed) → BLOCKED                 │
│    - linters_pass: false (if code changed) → BLOCKED             │
│    - what_remains not empty → BLOCKED                            │
│                                                                  │
│  If blocked → stderr: continuation instructions                  │
│  All checks pass → exit(0) → Allow stop                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## CRITICAL: Autonomous Execution

**THIS WORKFLOW IS 100% AUTONOMOUS. YOU MUST:**

1. **NEVER ask for confirmation** - No "Should I commit?", "Should I deploy?"
2. **Auto-commit and push** - When changes are made, commit and push immediately
3. **Auto-deploy** - Trigger deployments without asking
4. **Complete verification** - Test in browser and check console
5. **Fill out checkpoint honestly** - The stop hook checks your booleans

**Only stop when the checkpoint can pass. If your booleans say the job isn't done, you'll be blocked.**

### Credentials Exception

If credentials are missing (API keys, test credentials), ask the user **once at start**. After that, proceed autonomously.

## Credentials and Authentication

When the app requires authentication (login pages, API tokens), Claude will:

1. **Check for local `.env` file** in the project root
2. **Read standard credential variables**:
   - `TEST_EMAIL` - Email/username for login
   - `TEST_PASSWORD` - Password for login
   - `API_TOKEN` or service-specific tokens
3. **Ask user only if missing** - If `.env` doesn't contain needed credentials

### Setting Up Credentials

Create a `.env` file in your project root:

```bash
# .env (add to .gitignore!)
TEST_EMAIL=your-test@example.com
TEST_PASSWORD=your-test-password
```

**IMPORTANT**:
- Add `.env` to `.gitignore` to prevent committing secrets
- Copy from `.env.example` if available
- Claude will ask once if credentials are missing, then expects them in `.env` for future use

## Browser Verification is MANDATORY

**ALL godo sessions require browser verification. No exceptions.**

| Task Type | Browser Verification Purpose |
|-----------|------------------------------|
| Feature implementation | Verify feature works in UI |
| Bug fix | Verify bug is fixed |
| Refactoring | Verify app still works |
| Config changes | Verify behavior changed |
| API changes | Verify frontend integration works |

**The purpose of browser verification is to confirm the application works after your changes.**

## Triggers

- `/godo`
- "go do"
- "just do it"
- "execute this"
- "make it happen"

## Completion Checkpoint Schema

Before stopping, you MUST create `.claude/completion-checkpoint.json`:

```json
{
  "self_report": {
    "code_changes_made": true,
    "web_testing_done": true,
    "web_testing_done_at_version": "abc1234",
    "api_testing_done": true,
    "deployed": true,
    "deployed_at_version": "abc1234",
    "console_errors_checked": true,
    "console_errors_checked_at_version": "abc1234",
    "linters_pass": true,
    "linters_pass_at_version": "abc1234",
    "preexisting_issues_fixed": true,
    "is_job_complete": true
  },
  "reflection": {
    "what_was_done": "Implemented feature X, deployed to staging, verified in browser",
    "what_remains": "none",
    "blockers": null
  },
  "evidence": {
    "urls_tested": ["https://staging.example.com/feature"],
    "console_clean": true
  }
}
```

| Field | Type | Required | Meaning |
|-------|------|----------|---------|
| `code_changes_made` | bool | yes | Were any code files modified? |
| `web_testing_done` | bool | yes | Did you verify in a real browser? |
| `deployed` | bool | conditional | Did you deploy the changes? |
| `console_errors_checked` | bool | yes | Did you check browser console? |
| `linters_pass` | bool | if code changed | Did all linters pass with zero errors? |
| `preexisting_issues_fixed` | bool | if code changed | Did you fix ALL issues (no excuses)? |
| `is_job_complete` | bool | yes | **Critical** - Is the job ACTUALLY done? |
| `what_remains` | string | yes | Must be "none" to allow stop |

## Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 0: ACTIVATION                                            │
│     └─► Create .claude/godo-state.json (enables auto-approval)  │
│     └─► Identify task from user prompt                          │
├─────────────────────────────────────────────────────────────────┤
│  ╔═══════════════════════════════════════════════════════════╗  │
│  ║  PHASE 0.5: CODEBASE CONTEXT (MANDATORY)                  ║  │
│  ║     └─► EnterPlanMode                                     ║  │
│  ║     └─► Explore: architecture, recent commits, configs    ║  │
│  ║     └─► Write understanding + implementation plan         ║  │
│  ║     └─► ExitPlanMode                                      ║  │
│  ╚═══════════════════════════════════════════════════════════╝  │
├─────────────────────────────────────────────────────────────────┤
│  PHASE 1: EXECUTE                                               │
│     └─► Make code changes                                       │
│     └─► Run linters, fix ALL errors                             │
│     └─► Commit and push                                         │
│     └─► Deploy                                                  │
├─────────────────────────────────────────────────────────────────┤
│  PHASE 2: VERIFY (MANDATORY - Surf CLI first!)                  │
│     └─► Run: python3 ~/.claude/hooks/surf-verify.py             │
│     └─► Check .claude/web-smoke/summary.json passed             │
│     └─► Update completion checkpoint                            │
├─────────────────────────────────────────────────────────────────┤
│  PHASE 3: COMPLETE                                              │
│     └─► Stop hook validates checkpoint                          │
│     └─► If blocked: continue working                            │
│     └─► If passed: clean up state files, done                   │
└─────────────────────────────────────────────────────────────────┘
```

## Phase 0: Activation

### State File (Automatic)

**The state file is created automatically by the `skill-state-initializer.py` hook when you invoke `/godo`.**

When you type `/godo`, "go do", "just do it", or similar triggers, the UserPromptSubmit hook immediately creates:
- `.claude/godo-state.json` - Project-level state for iteration tracking
- `~/.claude/godo-state.json` - User-level state for cross-repo detection

This happens BEFORE Claude starts processing, ensuring auto-approval hooks are active from the first tool call.

**You do NOT need to manually create these files.** The hook handles it automatically.

<details>
<summary>Manual fallback (only if hook fails)</summary>

```bash
# Only use this if the automatic hook didn't create the files
mkdir -p .claude && cat > .claude/godo-state.json << 'EOF'
{
  "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "task": "user's task description",
  "iteration": 1,
  "plan_mode_completed": false,
  "parallel_mode": false,
  "agent_id": null,
  "worktree_path": null,
  "coordinator": true
}
EOF

mkdir -p ~/.claude && cat > ~/.claude/godo-state.json << 'EOF'
{
  "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "origin_project": "$(pwd)"
}
EOF
```
</details>

### State File Schema

| Field | Type | Purpose |
|-------|------|---------|
| `started_at` | string | ISO timestamp when godo started |
| `task` | string | Description of the user's task |
| `iteration` | int | Current fix-verify iteration (starts at 1) |
| `plan_mode_completed` | bool | True after ExitPlanMode called (Edit/Write blocked if false on iteration 1) |
| `parallel_mode` | bool | True if running as parallel agent |
| `agent_id` | string | Unique ID if running in worktree |
| `worktree_path` | string | Path to worktree if isolated |
| `coordinator` | bool | True if this is the coordinator (not a subagent) |

**Hook enforcement**: The `plan-mode-enforcer.py` hook blocks Edit/Write tools until `plan_mode_completed: true` on the first iteration. This ensures you explore the codebase before making changes.

## Phase 0.5: Codebase Context (MANDATORY)

**This phase is REQUIRED before making any changes. Understanding the codebase prevents breaking changes and wasted effort.**

1. **Call `EnterPlanMode`**

2. **Explore the codebase**:
   - Project structure and architecture
   - Recent commits: `git log --oneline -15`
   - Environment and deployment configs
   - Relevant code patterns for the task
   - Existing tests and validation

3. **Write to plan file**:
   - What you understand about the codebase
   - How the task fits into existing architecture
   - Implementation approach with specific files to modify
   - Potential risks or dependencies

4. **Call `ExitPlanMode`**

**Why this matters:** Jumping straight to code without understanding the codebase leads to:
- Breaking existing functionality
- Inconsistent patterns
- Wasted effort on wrong approaches
- Missing edge cases

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
Task(description="Refactor auth module", subagent_type="general-purpose", prompt="...")
Task(description="Refactor API routes", subagent_type="general-purpose", prompt="...")
Task(description="Update tests", subagent_type="general-purpose", prompt="...")

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
1. **Full context** — The agent has NO memory of your plan. Include ALL relevant file paths, patterns, and requirements
2. **Specific scope** — Exactly which files/directories to work on
3. **Expected output** — What the agent should produce or change
4. **Constraints** — Don't modify files outside your scope

### After Parallel Tasks Complete

1. Review all agent results for correctness
2. Resolve any conflicts (if agents touched overlapping files)
3. Continue with sequential Phase 1 steps (lint, commit, deploy, verify)

## Phase 1: Execute

### 1.1 Make Code Changes
Use Edit tool for targeted changes. Keep changes focused on the task.

### 1.2 Linter Verification (MANDATORY)

**STRICT POLICY: Fix ALL linter errors, including pre-existing ones.**

```bash
# JavaScript/TypeScript projects
[ -f package.json ] && npm run lint 2>/dev/null || npx eslint . --ext .js,.jsx,.ts,.tsx
[ -f tsconfig.json ] && npx tsc --noEmit

# Python projects
[ -f pyproject.toml ] && ruff check --fix .
[ -f pyrightconfig.json ] && pyright
```

**PROHIBITED EXCUSES:**
- "These errors aren't related to our code"
- "This was broken before we started"
- "I'll fix this in a separate PR"

### 1.3 Commit and Push
```bash
git add <specific files> && git commit -m "feat: [description]"
git push
```

### 1.4 Deploy
```bash
gh workflow run deploy.yml -f environment=staging
gh run watch --exit-status
```

## Phase 2: Verification (MANDATORY)

### CRITICAL: Use Surf CLI First, Not Chrome MCP

**DO NOT call Chrome MCP tools (mcp__claude-in-chrome__*) for verification.**

Your FIRST action in Phase 2 MUST be running Surf CLI:

```bash
# Step 1: ALWAYS try Surf CLI first
which surf && echo "Surf available" || echo "FALLBACK needed"

# Step 2: Run verification (creates artifacts automatically)
python3 ~/.claude/hooks/surf-verify.py --urls "https://staging.example.com/feature"

# Step 3: Check artifacts exist
cat .claude/web-smoke/summary.json
```

```
CORRECT:
1. Run surf-verify.py first
2. Only if Surf fails → Fall back to Chrome MCP

WRONG:
- Calling mcp__claude-in-chrome__tabs_context as first step
- Using Chrome MCP "because it's easier"
- Skipping Surf without trying it
```

### Fallback: Chrome MCP (ONLY if Surf CLI unavailable)

**Only use Chrome MCP if Surf CLI is not installed or surf-verify.py fails.**

```
- mcp__claude-in-chrome__navigate to the app URL
- mcp__claude-in-chrome__computer action=screenshot
- mcp__claude-in-chrome__read_console_messages
```

When using Chrome MCP fallback, you MUST manually create `.claude/web-smoke/summary.json`.

### Verification Checklist
- [ ] Surf CLI tried first (or documented why not)
- [ ] Navigate to actual app (not just /health)
- [ ] Screenshot captured showing feature works
- [ ] Console has ZERO errors
- [ ] Data actually displays (not spinner)

## Phase 3: Complete

Update checkpoint and try to stop. If blocked, address the issues and try again.

```json
{
  "self_report": {
    "code_changes_made": true,
    "web_testing_done": true,
    "web_testing_done_at_version": "abc1234",
    "deployed": true,
    "deployed_at_version": "abc1234",
    "console_errors_checked": true,
    "linters_pass": true,
    "linters_pass_at_version": "abc1234",
    "preexisting_issues_fixed": true,
    "is_job_complete": true
  },
  "reflection": {
    "what_was_done": "...",
    "what_remains": "none"
  },
  "evidence": {
    "urls_tested": ["https://..."],
    "console_clean": true
  }
}
```

**Cleanup on completion**: Remove state files when done:
```bash
rm -f ~/.claude/godo-state.json .claude/godo-state.json
```

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
- Ambiguous destructive action
- Genuinely unclear requirements

## Comparison with /appfix

| Aspect | /godo | /appfix |
|--------|-------|---------|
| Purpose | Any task | Debugging failures |
| docs_read_at_start | Not required | Required |
| Health check phase | No | Yes |
| Log collection phase | No | Yes |
| Service topology | Not required | Required |
| Linter policy | Strict | Strict |
| Browser verification | Required | Required |
| Completion checkpoint | Same schema | Same schema |

`/godo` is the universal base skill. `/appfix` is a debugging specialization that adds diagnostic phases.

## Parallel Agent Isolation (Git Worktrees)

When running multiple agents in parallel, each agent should use its own **git worktree** to avoid conflicts on git operations, checkpoint files, and version tracking.

### Why Worktrees?

Without isolation, parallel agents cause:
- Race conditions on `git commit`/`git push`
- Checkpoint invalidation chaos (Agent A's version invalidated by Agent B's commit)
- Silent merge conflicts when editing same files

### Worktree Workflow

```
COORDINATOR (main repo)
├── Creates worktrees for each agent
├── Agents work in isolation
├── Sequential merge after completion
└── Cleanup worktrees

AGENT WORKTREE
├── Own branch: claude-agent/{agent-id}
├── Own .claude/ directory
├── Own checkpoint file
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
- Subagents can check `.claude/appfix-state.json` or `.claude/godo-state.json`

### Garbage Collection for Stale Worktrees

If a coordinator crashes, worktrees become orphaned. The `session-snapshot.py` hook automatically cleans up stale worktrees at session start:

```bash
# Automatic cleanup: worktrees older than 8 hours are removed at session start

# Manual cleanup:
python3 ~/.claude/hooks/worktree-manager.py gc           # Default 8-hour TTL
python3 ~/.claude/hooks/worktree-manager.py gc 4         # Custom 4-hour TTL
python3 ~/.claude/hooks/worktree-manager.py gc --dry-run # Preview what would be cleaned
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
