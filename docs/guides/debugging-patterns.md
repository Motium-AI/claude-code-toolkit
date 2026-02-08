# Debugging Patterns Reference

How the toolkit's debugging infrastructure works across skills, hooks, and memory.

## Architecture Overview

Debugging is handled at three layers:

1. **Pre-execution gates** (PreToolUse hooks) — block dangerous commands
2. **Post-execution advisories** (PostToolUse hooks) — surface error context
3. **Session-exit validation** (Stop hooks) — verify work was completed

## Hook Chain for Debugging

```
User prompt → [prompt-entity-recall] → inject debugging memories
                                         ↓
Bash command → [deploy-enforcer] → gate deploys
                                         ↓
Bash output  → [bash-error-advisor] → advisory warnings + rollback suggestions
             → [bash-version-tracker] → invalidate stale checkpoints
             → [autonomous-health-monitor] → session health warnings
                                         ↓
Session stop → [stop-validator] → verify checkpoint + verification artifacts
             → [agent verifier] → transcript-based quality evaluation
```

## Debugging-Aware Memory

When a skill activates repair/appfix/mobileappfix mode, the memory system adjusts scoring:

- **bugfix/config category events** get a +0.10 scoring boost
- **Events with problem_type entity** get a +0.05 boost
- Both `prompt-entity-recall` and `memory-recall` apply these boosts

This means debugging sessions surface past bug fixes and config lessons more aggressively.

## Error Advisory System

`bash-error-advisor.py` (PostToolUse, Bash matcher) provides:

- **Pattern matching**: 15+ error signatures (Python, Node, Git, Docker, DB, network)
- **Escalation**: Same error 3+ times in 5 minutes triggers stronger warning
- **Deploy rollback**: Deploy failures get specific rollback command suggestions
- **Advisory only**: Never blocks — just adds context to help the agent self-correct

## Verification Cross-Check

`stop-validator.py` reads verification artifacts from two sources:

| Source | Path | What it proves |
|--------|------|----------------|
| Web smoke tests | `.claude/web-smoke/summary.json` | "The app loads" |
| Validation tests | `.claude/validation-tests/summary.json` | "The fix worked" |

If either has `passed: false`, the stop hook adds it to the validation failure list.

## Crash Recovery

`precompact-capture.py` handles the gap between normal stop and unexpected session death:

- If PreCompact fires with no checkpoint AND code changes exist → writes emergency memory event
- Event has `source: crash-recovery` for tracking
- Prevents total loss of debugging context when sessions die mid-work

## Cross-Project Memory

When `cross_project_recall: true` is set in MEMORIES.md:

- `compound-context-loader` queries concept entities across all project memory stores
- Only concept entities match (not file paths — those are project-specific)
- High overlap threshold (0.5) prevents noisy cross-pollination
- Fills remaining injection slots after project-specific memories

## Health Monitoring

`autonomous-health-monitor.py` (PostToolUse, * matcher) checks:

1. **State expiry** — autonomous-state.json TTL exceeded
2. **Commit staleness** — no git commit in 30+ minutes during autonomous mode
3. **Checkpoint drift** — checkpoint version doesn't match current code version

Rate-limited to one check every 2 minutes to avoid performance drag.

## Debugging Workflow Patterns

### Data Pipeline Debugging
1. Identify which pipeline stage fails (ingestion → transform → load)
2. Check database state at each stage boundary
3. Write validation tests that prove data flows end-to-end
4. Use `/repair` which auto-detects web vs mobile platform

### Serverless/Cloud Function Debugging
1. Check deployment logs first (`az webapp log tail`, `kubectl logs`)
2. Verify environment variables are set in the target environment
3. Test locally with production-like config before deploying
4. Deploy enforcer gates prevent accidental production pushes

### Mobile App Debugging
1. Use `/mobileappfix` for Maestro-based E2E debugging
2. OAuth-gated apps require verification script before iOS builds
3. EAS build failures get specific rollback suggestions from error advisor

### Relay/Real-time Debugging
1. Check WebSocket connection state and reconnection logic
2. Verify subscription authentication tokens
3. Test with isolated relay instances before production
4. Monitor for connection refused errors (advisor catches these)
