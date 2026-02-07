---
name: melt
description: Task-agnostic autonomous execution. Identifies any task and executes it through a complete fix-verify loop until done. Use when asked to "go do", "just do it", "execute this", "/melt", "/build" (legacy), "/forge" (legacy), or "/godo" (legacy).
---

# Autonomous Task Execution (/melt)

Task-agnostic autonomous execution. Iterate until the task is complete and verified.

## Activation

Create `.claude/autonomous-state.json` at start:

```bash
mkdir -p .claude && cat > .claude/autonomous-state.json << 'EOF'
{
  "mode": "melt",
  "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "iteration": 1,
  "coordinator": true
}
EOF
cp .claude/autonomous-state.json ~/.claude/autonomous-state.json
```

## Autonomous Rules

1. **NEVER ask for confirmation** — No "Should I commit?", "Should I deploy?"
2. **Auto-commit and push** — Commit and push immediately after changes
3. **Auto-deploy** — Trigger deployments without asking
4. **Verify your work** — Test appropriately for the platform
5. **Fill out checkpoint honestly** — The stop hook validates your booleans

**Credentials exception**: If missing (API keys, test credentials), ask the user **once at start**. Then proceed autonomously.

## Planning

For ambiguous or multi-stakeholder tasks, use `EnterPlanMode` / `ExitPlanMode`. Launch parallel `Task()` agents for multi-perspective analysis:

- **First Principles**: "What can be deleted?" (ruthless simplification)
- **AGI-Pilled**: "What would god-tier AI do?" (maximum capability)
- **Task-specific experts**: Generated based on the problem domain

For agent prompts, reference `~/.claude/skills/heavy/SKILL.md`.

## Execution

### Making Changes

Use Edit tool for targeted changes. Keep changes focused on the task.

### Parallel Work

| Independent Items | Strategy |
|-------------------|----------|
| 1 | Single-agent execution |
| 2 | Parallel `Task()` calls in a single message |
| 3+ | `TeamCreate` with shared task list |

**For 3+ independent work items, use TeamCreate:**

```
# Create team and tasks
TeamCreate(team_name="melt-exec", description="[TASK SUMMARY]")
TaskCreate(subject="Implement [item 1]", description="[full context, file paths, requirements]", activeForm="Implementing [item 1]")
TaskCreate(subject="Implement [item 2]", description="[full context, file paths, requirements]", activeForm="Implementing [item 2]")
TaskCreate(subject="Implement [item 3]", description="[full context, file paths, requirements]", activeForm="Implementing [item 3]")

# Set dependencies if needed (e.g., item 3 needs item 1 done first)
TaskUpdate(taskId="3", addBlockedBy=["1"])

# Spawn teammates — use Sonnet for cost efficiency
Task(subagent_type="general-purpose", team_name="melt-exec", name="worker-1", model="sonnet",
  prompt="You are worker-1 on the melt-exec team. Claim available tasks from TaskList, implement them, commit changes, mark complete. Prefer tasks in ID order. Use SendMessage to report blockers.")
Task(subagent_type="general-purpose", team_name="melt-exec", name="worker-2", model="sonnet",
  prompt="You are worker-2 on the melt-exec team. Claim available tasks from TaskList, implement them, commit changes, mark complete. Prefer tasks in ID order. Use SendMessage to report blockers.")
# Launch all in a SINGLE message

# IMPORTANT: Partition file ownership — never assign overlapping files to different workers
# Monitor via TaskList, synthesize when done, shutdown teammates, TeamDelete
```

**For 2 items, use parallel `Task()` calls** — simpler and cheaper.

### Linter Verification (MANDATORY)

```bash
# JavaScript/TypeScript
[ -f package.json ] && npm run lint 2>/dev/null || npx eslint . --ext .js,.jsx,.ts,.tsx
[ -f tsconfig.json ] && npx tsc --noEmit

# Python
[ -f pyproject.toml ] && ruff check --fix .
```

Fix ALL linter errors, including pre-existing ones. No exceptions.

### Commit and Deploy

```bash
git add <specific files> && git commit -m "feat: [description]"
git push
gh workflow run deploy.yml -f environment=staging && gh run watch --exit-status
```

## Verification (MANDATORY — Platform-Aware)

| Platform | Detection | Verification Method |
|----------|-----------|---------------------|
| Web | `package.json` with frontend deps | Surf CLI first, Chrome MCP fallback |
| Mobile | `app.json`, `eas.json`, `ios/`, `android/` | Maestro MCP tools |
| Backend only | No frontend files | Linters + API tests |
| Config/docs | No code changes | Re-read changed files |

### Web Projects

```bash
python3 ~/.claude/hooks/surf-verify.py --urls "https://staging.example.com/feature"
cat .claude/web-smoke/summary.json
```

### Mobile Projects

```
ToolSearch(query: "maestro")
# Use Maestro MCP tools (NOT bash maestro commands)
```

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
    "what_was_done": "Implemented feature X, deployed to staging, verified in browser",
    "what_remains": "none",
    "key_insight": "Reusable lesson for future sessions (>50 chars)",
    "search_terms": ["keyword1", "keyword2"],
    "memory_that_helped": []
  }
}
```

| Field | Type | Required | Meaning |
|-------|------|----------|---------|
| `is_job_complete` | bool | yes | Is the job actually done? |
| `code_changes_made` | bool | yes | Were code files modified? |
| `linters_pass` | bool | if code changed | Did all linters pass? |
| `category` | enum | yes | bugfix, gotcha, architecture, pattern, config, refactor |
| `what_was_done` | string | yes | >20 chars describing work |
| `what_remains` | string | yes | Must be "none" to allow stop |
| `key_insight` | string | yes | >50 chars — the reusable LESSON, not a repeat of what_was_done |
| `search_terms` | list | yes | 2-7 concept keywords |
| `memory_that_helped` | list | no | Which memories (m1, m2...) were useful |

Extra informational fields (evidence, metrics) are allowed — the stop-validator ignores unknown keys.

## Exit Conditions

| Condition | Result |
|-----------|--------|
| All required fields valid, `what_remains: "none"` | SUCCESS — stop allowed |
| Any required field invalid | BLOCKED — continue working |
| Missing credentials | ASK USER (once) |

**Cleanup on completion:**

```bash
rm -f ~/.claude/autonomous-state.json .claude/autonomous-state.json
```

## Triggers

- `/melt` (primary), `/build` (legacy)
- "go do", "just do it", "execute this", "make it happen"

## Skill Fluidity

You may use techniques from any skill for sub-problems without switching modes. Discover a bug? Debug it inline. Hit tech debt? Apply /burndown patterns. Need deep analysis? Invoke /heavy. Your autonomous state and checkpoint remain governed by /melt.
