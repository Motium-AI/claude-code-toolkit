---
name: build
description: Task-agnostic autonomous execution. Identifies any task and executes it through a complete fix-verify loop until done. Use when asked to "go do", "just do it", "execute this", "/build", "/forge" (legacy), or "/godo" (legacy).
---

# Autonomous Task Execution (/build)

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
│    - web_testing_done: false (web projects) → BLOCKED            │
│    - maestro_tests_passed: false (mobile projects) → BLOCKED     │
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

## Verification is MANDATORY (Platform-Aware)

**ALL forge sessions require E2E verification. The type depends on your platform:**

### Web Projects → Browser Testing (Surf CLI)

| Task Type | Browser Verification Purpose |
|-----------|------------------------------|
| Feature implementation | Verify feature works in UI |
| Bug fix | Verify bug is fixed |
| Refactoring | Verify app still works |
| Config changes | Verify behavior changed |
| API changes | Verify frontend integration works |

### Mobile Projects → Maestro E2E Testing (MCP)

**If the project contains `app.json`, `eas.json`, or `ios/`/`android/` directories, it's a mobile project and requires Maestro testing.**

| Task Type | Maestro Verification Purpose |
|-----------|------------------------------|
| Feature implementation | Verify feature works on simulator |
| Bug fix | Verify bug is fixed via E2E tests |
| Refactoring | Verify app still works (J2 + J3 journeys) |
| Config changes | Verify behavior changed |
| API changes | Verify mobile app integration works |

**Mobile projects MUST use Maestro MCP tools:**
- `mcp__maestro__run_flow()` - Run test journeys
- `mcp__maestro__hierarchy()` - Inspect element tree
- `mcp__maestro__screenshot()` - Capture screenshots

**The purpose of verification is to confirm the application works after your changes.**

## Triggers

- `/build` (primary)
- `/build` (was /forge, /godo)
- "go do"
- "just do it"
- "execute this"
- "make it happen"

## Completion Checkpoint Schema

Before stopping, you MUST create `.claude/completion-checkpoint.json`:

### Web Projects

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
    "is_job_complete": true
  },
  "reflection": {
    "what_was_done": "Implemented feature X, deployed to staging, verified in browser",
    "what_remains": "none"
  },
  "evidence": {
    "urls_tested": ["https://staging.example.com/feature"],
    "console_clean": true
  }
}
```

### Mobile Projects

```json
{
  "self_report": {
    "code_changes_made": true,
    "maestro_mcp_used": true,
    "full_journeys_validated": true,
    "maestro_tests_passed": true,
    "maestro_tests_passed_at_version": "abc1234",
    "linters_pass": true,
    "linters_pass_at_version": "abc1234",
    "is_job_complete": true
  },
  "reflection": {
    "what_was_done": "Fixed auth guard, verified via Maestro E2E",
    "what_remains": "none"
  },
  "evidence": {
    "mcp_tools_used": ["mcp__maestro__run_flow", "mcp__maestro__hierarchy"],
    "maestro_flows_tested": ["J2-returning-user-login.yaml", "J3-main-app-navigation.yaml"],
    "platform": "ios"
  }
}
```

### Common Fields

| Field | Type | Required | Meaning |
|-------|------|----------|---------|
| `code_changes_made` | bool | yes | Were any code files modified? |
| `linters_pass` | bool | if code changed | Did all linters pass with zero errors? |
| `is_job_complete` | bool | yes | **Critical** - Is the job ACTUALLY done? |
| `what_remains` | string | yes | Must be "none" to allow stop |

### Web-Specific Fields

| Field | Type | Required | Meaning |
|-------|------|----------|---------|
| `web_testing_done` | bool | yes | Did you verify in a real browser? |
| `deployed` | bool | conditional | Did you deploy the changes? |
| `console_errors_checked` | bool | yes | Did you check browser console? |

### Mobile-Specific Fields

| Field | Type | Required | Meaning |
|-------|------|----------|---------|
| `maestro_mcp_used` | bool | yes | Did you use Maestro MCP tools (not bash)? |
| `full_journeys_validated` | bool | yes | Did you run complete user journeys (J2+J3)? |
| `maestro_tests_passed` | bool | yes | Did all Maestro E2E tests pass? |

## Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 0: ACTIVATION                                            │
│     └─► Create .claude/build-state.json (enables auto-approval) │
│     └─► Identify task from user prompt                          │
├─────────────────────────────────────────────────────────────────┤
│  ╔═══════════════════════════════════════════════════════════╗  │
│  ║  PHASE 0.5: LITE HEAVY PLANNING (MANDATORY)               ║  │
│  ║     └─► EnterPlanMode                                     ║  │
│  ║     └─► Launch 4 parallel Opus agents:                    ║  │
│  ║         ├─► First Principles: "What can be deleted?"      ║  │
│  ║         ├─► AGI-Pilled: "What would god-tier AI do?"      ║  │
│  ║         └─► 2 Dynamic: Generated based on the task        ║  │
│  ║     └─► Synthesize tradeoffs + write plan                 ║  │
│  ║     └─► ExitPlanMode                                      ║  │
│  ╚═══════════════════════════════════════════════════════════╝  │
├─────────────────────────────────────────────────────────────────┤
│  PHASE 1: EXECUTE                                               │
│     └─► Make code changes                                       │
│     └─► Run linters, fix ALL errors                             │
├─────────────────────────────────────────────────────────────────┤
│  ╔═══════════════════════════════════════════════════════════╗  │
│  ║  PHASE 1.75: HARNESS TEST (if in toolkit project)         ║  │
│  ║     └─► Detect if cwd is namshub              ║  │
│  ║     └─► Check for modified hooks/skills/settings          ║  │
│  ║     └─► Create sandbox, propagate changes                 ║  │
│  ║     └─► Run test cases in isolated Claude session         ║  │
│  ║     └─► BLOCK if tests fail, continue if pass             ║  │
│  ║     └─► See: /harness-test skill                          ║  │
│  ╚═══════════════════════════════════════════════════════════╝  │
├─────────────────────────────────────────────────────────────────┤
│  PHASE 1.9: COMMIT & DEPLOY                                     │
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

**The state file is created automatically by the `skill-state-initializer.py` hook when you invoke `/build` or `/godo`.**

When you type `/build`, `/godo`, "go do", "just do it", or similar triggers, the UserPromptSubmit hook immediately creates:
- `.claude/build-state.json` - Project-level state for iteration tracking
- `~/.claude/build-state.json` - User-level state for cross-repo detection

This happens BEFORE Claude starts processing, ensuring auto-approval hooks are active from the first tool call.

**You do NOT need to manually create these files.** The hook handles it automatically.

<details>
<summary>Manual fallback (only if hook fails)</summary>

```bash
# Only use this if the automatic hook didn't create the files
mkdir -p .claude && cat > .claude/build-state.json << 'EOF'
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

mkdir -p ~/.claude && cat > ~/.claude/build-state.json << 'EOF'
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
| `started_at` | string | ISO timestamp when forge started |
| `task` | string | Description of the user's task |
| `iteration` | int | Current fix-verify iteration (starts at 1) |
| `plan_mode_completed` | bool | True after ExitPlanMode called (Edit/Write blocked if false on iteration 1) |
| `parallel_mode` | bool | True if running as parallel agent |
| `agent_id` | string | Unique ID if running in worktree |
| `worktree_path` | string | Path to worktree if isolated |
| `coordinator` | bool | True if this is the coordinator (not a subagent) |

**Hook enforcement**: The `plan-mode-enforcer.py` hook blocks Edit/Write tools until `plan_mode_completed: true` on the first iteration. This ensures you explore the codebase before making changes.

## Phase 0.5: Lite Heavy Planning (MANDATORY)

**This phase is REQUIRED before making any changes. It combines codebase exploration with 4-agent analysis for optimal planning.**

### Overview

Lite Heavy is a streamlined version of `/heavy` that provides multi-perspective analysis in a single round. It uses **4 agents** (all hook-enforced): `/heavy`'s **First Principles** and **AGI-Pilled** plus **2 dynamic agents** generated based on the specific task. This ensures you don't over-engineer, under-simplify, AND catches task-specific blind spots.

### Workflow

1. **Call `EnterPlanMode`**

2. **Explore the codebase first**:
   - Project structure and architecture
   - Recent commits: `git log --oneline -15`
   - Environment and deployment configs
   - Relevant code patterns for the task
   - Existing tests and validation

3. **Read `/heavy` agent prompts and generate dynamic perspectives**:

   **CRITICAL**: Read `~/.claude/skills/heavy/SKILL.md` to get the exact prompts for:
   - **REQUIRED AGENT 1: First Principles** (Elon Musk approach)
   - **REQUIRED AGENT 2: AGI-Pilled** (maximally capable AI assumption)
   - **DYNAMIC AGENT TEMPLATE** (lines 346-391 in heavy/SKILL.md)

   **Generate 2 dynamic perspectives** by asking:
   > "For THIS task, who would argue about it at a company meeting? Pick 2 perspectives that catch what First Principles and AGI-Pilled might miss."

   | Task Type | Example Dynamic Agent 1 | Example Dynamic Agent 2 |
   |-----------|------------------------|------------------------|
   | Auth feature | Security Engineer | API Consumer |
   | UI component | UX Designer | Accessibility Expert |
   | DB migration | DBA | Application Developer |
   | API design | Frontend Consumer | External Partner |

4. **Launch 4 parallel Opus agents in a SINGLE message**:

   Using the prompts read from heavy/SKILL.md:

   ```
   // 4 AGENTS (all hook-enforced — must be in a SINGLE message)
   Task(
     subagent_type="general-purpose",
     description="First Principles Analysis",
     model="opus",
     prompt="[PASTE HEAVY'S FIRST PRINCIPLES PROMPT with TASK and CODEBASE CONTEXT filled in]"
   )

   Task(
     subagent_type="general-purpose",
     description="AGI-Pilled Analysis",
     model="opus",
     prompt="[PASTE HEAVY'S AGI-PILLED PROMPT with TASK and CODEBASE CONTEXT filled in]"
   )

   // 2 DYNAMIC AGENTS (task-specific, also hook-enforced)
   Task(
     subagent_type="general-purpose",
     description="[DYNAMIC PERSPECTIVE 1] perspective",
     model="opus",
     prompt="[PASTE HEAVY'S DYNAMIC AGENT TEMPLATE with ROLE and TASK filled in]"
   )

   Task(
     subagent_type="general-purpose",
     description="[DYNAMIC PERSPECTIVE 2] perspective",
     model="opus",
     prompt="[PASTE HEAVY'S DYNAMIC AGENT TEMPLATE with ROLE and TASK filled in]"
   )
   ```

5. **Synthesize the agents' responses**:

After all 4 agents return, synthesize their insights:

```
TRADEOFF: [topic]
- First Principles: Delete X because [reason]
- AGI-Pilled: Expand Y because [capability argument]
- [Dynamic 1]: Consider Z because [domain expertise]
- [Dynamic 2]: Watch out for W because [specific risk]
- Resolution: [chosen approach with rationale]
```

6. **Write to plan file**:
   - Tradeoffs discovered and resolutions
   - Final simplified scope (what we WON'T do)
   - Implementation approach with specific files
   - Risks and mitigations

7. **Call `ExitPlanMode`**

### Why 4 Agents?

Lite Heavy uses **4 agents** to cover both universal tensions and task-specific blind spots:

| Agent Type | Force | Key Question | Enforcement |
|------------|-------|--------------|-------------|
| **First Principles** | Simplification | "What can be deleted?" | Hook-enforced |
| **AGI-Pilled** | Capability | "What would god-tier AI do?" | Hook-enforced |
| **Dynamic 1** | Domain expertise | "What does [expert] see?" | Hook-enforced |
| **Dynamic 2** | Adversarial review | "What could go wrong?" | Hook-enforced |

| Problem | Which Agent Catches It |
|---------|----------------------|
| Over-engineering | First Principles |
| Under-ambition | AGI-Pilled |
| Domain-specific pitfalls | Dynamic (domain expert) |
| Implementation flaws | Dynamic (adversarial) |

**Why 4 agents instead of 2?**
- 2 agents = 1 pairwise tension (simplify vs expand)
- 4 agents = 6 pairwise tensions (each perspective challenges 3 others)
- Planning tokens << execution tokens — better planning = fewer fix-verify iterations

**Hook enforcement**: All 4 agents are hook-enforced. The `lite-heavy-enforcer` blocks ExitPlanMode until First Principles, AGI-Pilled, AND 2 dynamic agents have been launched. Dynamic agents are detected by "perspective", "analysis", "review", or "expert" keywords in the Task description.

**Why reference heavy instead of duplicating?** Single source of truth. When heavy's prompts improve, forge automatically benefits.

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

## Phase 1.75: Harness Test (Conditional)

**This phase only runs when working on the namshub repository itself.**

When modifying hooks, skills, or settings, changes don't take effect in the current session (hooks are captured at startup). This phase tests those changes in an isolated sandbox with a fresh Claude session.

### Detection

```bash
# Check if we're in the harness project
~/.claude/skills/harness-test/scripts/detect-harness.sh

# Check for modified harness files
~/.claude/skills/harness-test/scripts/detect-harness-changes.sh
```

If both return true, run harness tests before committing.

### Execution

```bash
# Create sandbox with modified hooks/skills
SANDBOX_ID=$(~/.claude/skills/harness-test/scripts/setup-harness-sandbox.sh)

# Run test cases
~/.claude/skills/harness-test/scripts/run-all-tests.sh "$SANDBOX_ID"

# Cleanup
~/.claude/skills/harness-test/scripts/cleanup-sandbox.sh "$SANDBOX_ID"
```

### Blocking Behavior

- **Tests pass**: Continue to Phase 1.9 (commit)
- **Tests fail**: STOP. Fix the issues and re-run. Do NOT commit broken hooks.

See `/harness-test` skill for full documentation.

## Phase 1.9: Commit and Deploy

### 1.9.1 Commit and Push
```bash
git add <specific files> && git commit -m "feat: [description]"
git push
```

### 1.9.2 Deploy
```bash
gh workflow run deploy.yml -f environment=staging
gh run watch --exit-status
```

## Phase 2: Verification (MANDATORY - Platform-Aware)

**The validator auto-detects your platform and enforces appropriate testing.**

### Web Projects: Surf CLI / Chrome MCP

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

**Fallback: Chrome MCP** (only if Surf CLI unavailable):
```
- mcp__claude-in-chrome__navigate to the app URL
- mcp__claude-in-chrome__computer action=screenshot
- mcp__claude-in-chrome__read_console_messages
```

### Mobile Projects: Maestro MCP

**If the project contains `app.json`, `eas.json`, or `ios/`/`android/` directories, you MUST use Maestro MCP.**

```
# Minimum required journeys
mcp__maestro__run_flow(flow: ".maestro/journeys/J2-returning-user-login.yaml")
mcp__maestro__run_flow(flow: ".maestro/journeys/J3-main-app-navigation.yaml")

# Create artifacts
mkdir -p .claude/maestro-smoke
# Maestro MCP auto-saves screenshots and summary
```

**DO NOT use bash `maestro test` commands.** Always use Maestro MCP tools.

### Verification Checklist

**Web Projects:**
- [ ] Surf CLI tried first (or documented why not)
- [ ] Navigate to actual app (not just /health)
- [ ] Screenshot captured showing feature works
- [ ] Console has ZERO errors
- [ ] Data actually displays (not spinner)

**Mobile Projects:**
- [ ] Maestro MCP tools used (not bash commands)
- [ ] Full journeys validated (J2 + J3 minimum)
- [ ] Screenshots captured via MCP
- [ ] All flows passing
- [ ] Artifacts in .claude/maestro-smoke/

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
rm -f ~/.claude/build-state.json .claude/build-state.json
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

| Aspect | /build | /appfix |
|--------|--------|---------|
| Purpose | Any task | Debugging failures |
| Lite Heavy planning | Yes (4 agents) | No |
| docs_read_at_start | Not required | Required |
| Health check phase | No | Yes |
| Log collection phase | No | Yes |
| Service topology | Not required | Required |
| Linter policy | Strict | Strict |
| Platform detection | Auto (web vs mobile) | Auto (web vs mobile) |
| Web verification | Surf CLI + Chrome MCP | Surf CLI + Chrome MCP |
| Mobile verification | Maestro MCP | Maestro MCP |
| Completion checkpoint | Same schema | Same schema |

`/build` is the universal base skill. `/appfix` is a debugging specialization that adds diagnostic phases.

Both skills now auto-detect mobile projects (via `app.json`, `eas.json`, `ios/`, `android/`) and require Maestro testing instead of browser testing.

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
- Subagents can check `.claude/appfix-state.json` or `.claude/build-state.json`

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
