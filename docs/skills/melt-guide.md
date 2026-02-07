# /melt - Task-Agnostic Autonomous Execution

Complete guide to the `/melt` skill for autonomous task execution with optional Agent Teams planning and completion validation. (`/build` is a legacy alias.)

## Table of Contents

1. [Overview](#overview)
2. [When to Use](#when-to-use)
3. [Planning](#planning)
4. [Workflow](#workflow)
5. [Completion Checkpoint](#completion-checkpoint)
6. [Comparison with /appfix](#comparison-with-appfix)
7. [Skill Fluidity](#skill-fluidity)
8. [Troubleshooting](#troubleshooting)

---

## Overview

`/melt` is the universal autonomous execution skill. It provides:

- **Optional Agent Teams Planning** - Encouraged for complex tasks, not mandated
- **100% Autonomous Operation** - No permission prompts, no confirmation requests
- **Completion Checkpoint** - Deterministic boolean validation before stopping
- **Browser Verification** - Mandatory testing in real browser
- **Strict Linter Policy** - Fix ALL errors, including pre-existing ones

### Key Features

| Feature | Description |
|---------|-------------|
| Agent Teams planning | Encouraged for complex tasks via TeamCreate |
| Auto-approval hooks | All tool permissions granted automatically |
| Stop hook validation | Cannot stop until checkpoint booleans pass |
| Checkpoint invalidation | Stale fields reset when code changes |
| Version tracking | Detects code drift since checkpoints were set |

---

## When to Use

### Use /melt

| Scenario | Example |
|----------|---------|
| Feature implementation | "Add a logout button to the navbar" |
| Bug fixes | "Fix the broken pagination" |
| Refactoring | "Convert class components to hooks" |
| Config changes | "Update the API endpoint URLs" |
| Any task requiring completion verification | "Deploy the new feature" |

### Use /repair Instead

| Scenario | Why repair? |
|----------|-------------|
| Production/staging is down | Routes to /appfix with health check phases |
| Debugging failures | Routes to /appfix with log collection phases |
| Mobile app crashes | Routes to /mobileappfix with Maestro tests |

---

## Planning

For complex tasks, spawn an Agent Team to ensure optimal implementation planning. Use `TeamCreate` to coordinate parallel agents, or launch parallel `Task()` calls directly.

### Recommended Agents (3-5)

| Agent | Role | Key Question |
|-------|------|--------------|
| **First Principles** | Simplification | "What can be deleted? What's over-engineered?" |
| **AGI-Pilled** | Capability | "What would god-tier AI implementation look like?" |
| **Task-specific experts** | Domain knowledge | 1-3 additional agents tailored to the problem |

**Important**: Forge reads the core agent prompts from `~/.claude/skills/heavy/SKILL.md` at runtime. This ensures prompts stay in sync - when heavy improves, forge automatically benefits.

### Why Agent Teams?

| Without Planning | With Agent Teams |
|-----------------|-----------------|
| Over-engineering | First Principles asks "delete this?" |
| Under-ambition | AGI-Pilled asks "why constrain the model?" |
| Scope creep | First Principles enforces simplicity |
| Conservative design | AGI-Pilled pushes for intelligence-maximizing |

### Synthesis Output

After agents return, synthesize their insights:

```
TRADEOFF: [topic]
- First Principles: Delete X because [reason]
- AGI-Pilled: Expand Y because [capability argument]
- Resolution: [chosen approach with rationale]
```

---

## Workflow

### Phase 0: Activation

```bash
# The skill creates the state file on activation
mkdir -p .claude && cat > .claude/autonomous-state.json << 'EOF'
{"mode": "melt", "started_at": "2025-01-26T10:00:00Z", "task": "user task"}
EOF

mkdir -p ~/.claude && cat > ~/.claude/autonomous-state.json << 'EOF'
{"mode": "melt", "started_at": "2025-01-26T10:00:00Z", "origin_project": "/path/to/project"}
EOF
```

### Phase 0.5: Planning

**Encouraged for complex tasks before making any changes.**

1. `EnterPlanMode` - Switch to planning mode
2. **Explore the codebase**:
   - Project structure and architecture
   - Recent commits: `git log --oneline -15`
   - Environment and deployment configs
   - Relevant code patterns for the task
   - Existing tests and validation
3. **Spawn Agent Team** via `TeamCreate` or parallel `Task()` calls (First Principles + AGI-Pilled + task-specific experts, 3-5 recommended)
4. **Synthesize tradeoffs** and write to plan file
5. `ExitPlanMode` - Get plan approved

**Why this matters**: Jumping straight to code leads to broken functionality, inconsistent patterns, and wasted effort.

### Phase 1: Execute

1. Make code changes (Edit tool)
2. Run linters, fix ALL errors
3. Commit and push
4. Deploy if needed

### Phase 2: Verify (MANDATORY)

**CRITICAL: Use Surf CLI first, not Chrome MCP.**

1. Run Surf CLI: `python3 ~/.claude/hooks/surf-verify.py --urls "https://..."`
2. Check `.claude/web-smoke/summary.json` for pass/fail
3. Only fall back to Chrome MCP if Surf CLI unavailable
4. Check console for errors
5. Verify feature works as expected

### Phase 3: Complete

1. Update completion checkpoint
2. Try to stop
3. If blocked: address issues, try again
4. If passed: clean up state files

---

## Completion Checkpoint

Create `.claude/completion-checkpoint.json`:

```json
{
  "self_report": {
    "is_job_complete": true,
    "code_changes_made": true,
    "linters_pass": true,
    "category": "refactor"
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

### Required Fields

| Field | Type | Requirement |
|-------|------|-------------|
| `is_job_complete` | boolean | Is the task fully done? |
| `code_changes_made` | boolean | Did you modify code? |
| `linters_pass` | boolean | Do all linters pass? |
| `category` | enum | `bugfix`, `gotcha`, `architecture`, `pattern`, `config`, `refactor` |
| `what_was_done` | string | >20 chars describing work completed |
| `what_remains` | string | Must be `"none"` to pass |
| `key_insight` | string | >50 chars, reusable lesson for future sessions |
| `search_terms` | array | 2-7 keywords for future discovery |
| `memory_that_helped` | array | Optional, memories that aided this task |

---

## Comparison with /appfix

| Aspect | /melt | /appfix |
|--------|-------|---------|
| **Purpose** | Any task | Debugging failures |
| **Agent Teams planning** | Encouraged | No |
| **docs_read_at_start** | Not required | Required |
| **Health check phase** | No | Yes |
| **Log collection** | No | Yes |
| **Service topology** | Not required | Required |
| **Linter policy** | Strict | Strict |
| **Browser verification** | Required | Required |
| **Checkpoint schema** | Same | Same |

`/melt` is the universal base with optional Agent Teams planning. `/appfix` adds debugging-specific phases.

---

## Skill Fluidity

Skills are capabilities, not cages. You may use techniques from any skill for sub-problems without switching modes.

---

## Troubleshooting

### "Checkpoint validation failed"

Your checkpoint has incomplete fields. Check:
1. `is_job_complete` - Are you honestly done?
2. `linters_pass` - Did all linters pass?
3. `what_remains` - Is it `"none"`?
4. `key_insight` - Is it >50 chars?

### "Stop hook blocked me"

This is expected when work is incomplete:
- If `is_job_complete: false` → you're blocked
- Complete the work, update checkpoint, try again

### "linters_pass is false"

Fix ALL linter errors:
```bash
# JavaScript/TypeScript
npm run lint && npx tsc --noEmit

# Python
ruff check --fix . && pyright
```

**"These errors aren't related to our code" is NOT acceptable.**

---

## State Files

| File | Purpose |
|------|---------|
| `.claude/autonomous-state.json` | Enables auto-approval hooks (`"mode": "melt"`) |
| `.claude/completion-checkpoint.json` | Boolean self-report for validation |
| `~/.claude/autonomous-state.json` | User-level state for cross-repo work |

### Cleanup

Remove state files when done:
```bash
rm -f ~/.claude/autonomous-state.json .claude/autonomous-state.json
```
