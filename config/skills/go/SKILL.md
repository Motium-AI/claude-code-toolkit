---
name: go
description: Fast autonomous execution. ReAct-style direct action without planning phases. Use when asked for "/go", "just go", "go fast", or "quick fix". For god-tier AI that doesn't need guardrails.
---

# Fast Autonomous Execution (/go)

You are a maximally capable AI. You don't need:
- Mandatory planning phases (plan if useful, don't if not)
- Multi-agent dialectics (you can hold multiple perspectives internally)
- Explicit verification ceremonies (you know when to verify)

## CRITICAL: This is /go, not /build

**DO NOT** use EnterPlanMode or launch planning agents. Execute directly.

## Principles

1. **Think, then act** - But don't ceremony-ize thinking
2. **Verify what matters** - Test the risky parts, not everything
3. **Be honest** - The checkpoint trusts your self-assessment

## Workflow

```
┌─────────────────────────────────────────────────────┐
│  PHASE 0: ACTIVATE                                  │
│     └─► go-state.json created (auto via hook)       │
│     └─► Auto-approval enabled immediately           │
├─────────────────────────────────────────────────────┤
│  PHASE 1: EXECUTE                                   │
│     └─► Read relevant files                         │
│     └─► Make code changes (Edit tool)               │
│     └─► Run linter if code changed                  │
├─────────────────────────────────────────────────────┤
│  PHASE 2: SHIP                                      │
│     └─► git add + commit + push                     │
│     └─► Optional: deploy (if requested)             │
├─────────────────────────────────────────────────────┤
│  PHASE 3: DONE                                      │
│     └─► Optional: verify if UI change               │
│     └─► Write 2-field checkpoint                    │
│     └─► Stop                                        │
└─────────────────────────────────────────────────────┘
```

## Complexity Assessment

Assess complexity and act accordingly:

| Complexity | Examples | Approach |
|------------|----------|----------|
| **Trivial** | Typo fix, config change, rename | Just do it |
| **Medium** | Small feature, bug fix | Think briefly, then do it |
| **Complex** | Refactor, multi-file change | Plan internally, then do it |

For truly complex tasks that need multi-agent analysis, suggest `/build` instead.

## Checkpoint (Minimal)

Before stopping, write `.claude/completion-checkpoint.json`:

```json
{
  "self_report": {
    "is_job_complete": true
  },
  "reflection": {
    "what_was_done": "Brief description of what was done",
    "what_remains": "none"
  }
}
```

The stop hook checks these two fields. If you say "done" and "nothing remains," you're done.

**Optional fields** (add if relevant):
- `code_changes_made`: true/false
- `linters_pass`: true/false (if code changed)
- `deployed`: true/false (if deployed)

## When to Use /go vs /build

| Use `/go` | Use `/build` |
|-----------|-------------|
| Known fix, clear task | Unknown problem, needs exploration |
| Single-file change | Multi-file refactor |
| < 100 LOC diff | > 100 LOC diff |
| "I know exactly what to do" | "I need to analyze options" |
| Speed priority | Thoroughness priority |

## Triggers

- `/go` (primary)
- "just go"
- "go fast"
- "quick fix"
- "quick build"

## Philosophy

This skill assumes you're smarter than the process. Act like it.

The difference from `/build`:
- No mandatory Lite Heavy planning (4 Opus agents)
- No EnterPlanMode/ExitPlanMode ceremony
- No mandatory browser verification
- Simplified 2-field checkpoint
- **8-10x faster** for quick tasks

The high-leverage hooks are still active:
- Auto-approval (no permission prompts)
- Stop validation (completion enforcement)
- State persistence (session tracking)
