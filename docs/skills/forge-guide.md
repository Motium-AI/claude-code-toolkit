# /forge - Task-Agnostic Autonomous Execution

Complete guide to the `/forge` skill for autonomous task execution with Lite Heavy planning and completion validation.

## Table of Contents

1. [Overview](#overview)
2. [When to Use](#when-to-use)
3. [Lite Heavy Planning](#lite-heavy-planning)
4. [Workflow](#workflow)
5. [Completion Checkpoint](#completion-checkpoint)
6. [Comparison with /appfix](#comparison-with-appfix)
7. [Troubleshooting](#troubleshooting)

---

## Overview

`/forge` is the universal autonomous execution skill. It provides:

- **Lite Heavy Planning** - 4 parallel Opus agents (First Principles + AGI-Pilled + 2 dynamic) before execution
- **100% Autonomous Operation** - No permission prompts, no confirmation requests
- **Completion Checkpoint** - Deterministic boolean validation before stopping
- **Browser Verification** - Mandatory testing in real browser
- **Strict Linter Policy** - Fix ALL errors, including pre-existing ones

### Key Features

| Feature | Description |
|---------|-------------|
| Lite Heavy planning | 4-agent planning phase to prevent over/under-engineering |
| Auto-approval hooks | All tool permissions granted automatically |
| Stop hook validation | Cannot stop until checkpoint booleans pass |
| Checkpoint invalidation | Stale fields reset when code changes |
| Version tracking | Detects code drift since checkpoints were set |

---

## When to Use

### Use /forge

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

## Lite Heavy Planning

Lite Heavy is a streamlined version of `/heavy` that uses `/heavy`'s 2 **required** agents to ensure optimal implementation planning.

### The Two Agents (from /heavy)

| Agent | Role | Key Question |
|-------|------|--------------|
| **First Principles** | Simplification | "What can be deleted? What's over-engineered?" |
| **AGI-Pilled** | Capability | "What would god-tier AI implementation look like?" |

**Important**: Forge reads the agent prompts directly from `~/.claude/skills/heavy/SKILL.md` at runtime. This ensures prompts stay in sync - when heavy improves, forge automatically benefits.

### Why These 2 Agents?

| Without Lite Heavy | With Lite Heavy |
|-------------------|-----------------|
| Over-engineering | First Principles asks "delete this?" |
| Under-ambition | AGI-Pilled asks "why constrain the model?" |
| Scope creep | First Principles enforces simplicity |
| Conservative design | AGI-Pilled pushes for intelligence-maximizing |

### Synthesis Output

After both agents return, synthesize their insights:

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
# State file is created AUTOMATICALLY by skill-state-initializer.py hook
# You do NOT need to run this manually
mkdir -p .claude && cat > .claude/forge-state.json << 'EOF'
{"started_at": "2025-01-26T10:00:00Z", "task": "user task"}
EOF

mkdir -p ~/.claude && cat > ~/.claude/forge-state.json << 'EOF'
{"started_at": "2025-01-26T10:00:00Z", "origin_project": "/path/to/project"}
EOF
```

### Phase 0.5: Lite Heavy Planning (MANDATORY)

**This phase is required before making any changes.**

1. `EnterPlanMode` - Switch to planning mode
2. **Explore the codebase**:
   - Project structure and architecture
   - Recent commits: `git log --oneline -15`
   - Environment and deployment configs
   - Relevant code patterns for the task
   - Existing tests and validation
3. **Launch 4 parallel Opus agents in a SINGLE message** (First Principles + AGI-Pilled + 2 dynamic perspectives)
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
    "code_changes_made": true,
    "web_testing_done": true,
    "web_testing_done_at_version": "abc1234",
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
    "what_was_done": "Implemented feature X",
    "what_remains": "none"
  },
  "evidence": {
    "urls_tested": ["https://staging.example.com/feature"],
    "console_clean": true
  }
}
```

### Required Fields

| Field | When Required | Meaning |
|-------|---------------|---------|
| `is_job_complete` | Always | Is the task fully done? |
| `web_testing_done` | Always | Did you verify in browser? |
| `code_changes_made` | Always | Did you modify code? |
| `deployed` | If code changed | Did you deploy? |
| `linters_pass` | If code changed | Do all linters pass? |
| `console_errors_checked` | Always | Did you check console? |
| `what_remains` | Always | Must be "none" or empty |

### Version Tracking

Version-dependent fields include `*_at_version` to detect staleness:

```
deployed: true
deployed_at_version: "abc1234"

# If code changes to "def5678", deployed becomes STALE
# Must re-deploy and update version
```

---

## Comparison with /appfix

| Aspect | /forge | /appfix |
|--------|--------|---------|
| **Purpose** | Any task | Debugging failures |
| **Lite Heavy planning** | Yes (4 agents) | No |
| **docs_read_at_start** | Not required | Required |
| **Health check phase** | No | Yes |
| **Log collection** | No | Yes |
| **Service topology** | Not required | Required |
| **Linter policy** | Strict | Strict |
| **Browser verification** | Required | Required |
| **Checkpoint schema** | Same | Same |

`/forge` is the universal base with Lite Heavy planning. `/appfix` adds debugging-specific phases.

---

## Troubleshooting

### "Checkpoint validation failed"

Your checkpoint has incomplete booleans. Check:
1. `is_job_complete` - Are you honestly done?
2. `web_testing_done` - Did you verify in browser?
3. `linters_pass` - Did all linters pass?
4. `what_remains` - Is it empty?

### "Stop hook blocked me"

This is expected when work is incomplete:
- If `is_job_complete: false` → you're blocked
- Complete the work, update checkpoint, try again

### "Field is STALE"

A checkpoint was set at an older code version:
1. Re-run that step with current code
2. Get current version: `git rev-parse --short HEAD`
3. Update checkpoint with new version

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
| `.claude/forge-state.json` | Enables auto-approval hooks |
| `.claude/completion-checkpoint.json` | Boolean self-report for validation |
| `~/.claude/forge-state.json` | User-level state for cross-repo work |

### Cleanup

Remove state files when done:
```bash
rm -f ~/.claude/forge-state.json .claude/forge-state.json
```
