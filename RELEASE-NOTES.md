# Release Notes

## v2.0 — Opus 4.6 + Agent Swarms + Complementary Memory

**Date**: 2026-02-07

### Why This Release

Claude Code has evolved rapidly. Two major platform changes drove this release:

1. **Opus 4.6** is significantly more capable than earlier models — it follows instructions more naturally, reasons better about multi-step tasks, and doesn't need the rigid guardrails (mandatory agent counts, ASCII checkpoint diagrams, forced verification steps) that earlier models required. We've refactored all 26 skills from prescriptive procedures into natural capability modes.

2. **Agent Teams** (experimental) enables true parallel agent swarms — multiple Claude instances coordinating via shared task lists, direct messaging, and team-scoped context. This replaces the previous pattern of sequential `Task()` calls with genuine concurrent collaboration.

3. **Native MEMORY.md** (Claude Code v2.1.32+) adds built-in project memory that loads unconditionally every session. Our custom compound memory system needed to integrate with it rather than compete for context budget.

### What Changed

#### Agent Swarms (Agent Teams)

Skills now leverage Agent Teams for parallel work:

- **`/melt`** spawns planning swarms (First Principles + AGI-Pilled + domain experts), then implementation agents for independent work items
- **`/heavy`** spawns 3-5 analysis agents for simultaneous multi-perspective debate
- **`/burndown`** spawns detection agents that scan different codebase aspects concurrently

Teams coordinate through shared task lists (`~/.claude/tasks/`) with blocking dependencies, auto-assignment, and structured messaging. When a teammate completes a task, it's automatically communicated to the team lead.

**How to enable**:

Add this env var to your `~/.claude/settings.json` (global) or `config/settings.json` (repo):

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

The install script sets this automatically. Restart Claude Code after changing settings.

> **Note**: Agent Teams is an experimental Claude Code feature. It's enabled via environment variable, not a CLI flag. Requires Claude Code v2.1.32+.

**Without Agent Teams**: All skills still work — they fall back to sequential `Task()` subagent calls. You lose shared task lists and team coordination, but the core fix-verify loop is identical.

#### Complementary Memory (Native + Custom)

The compound-context-loader now auto-detects Claude Code's native MEMORY.md and adjusts its behavior:

| Feature | Before | After |
|---------|--------|-------|
| Compound memory budget | Fixed 8000 chars | Dynamic: 4500 with MEMORY.md, 8000 without |
| Native memory awareness | None | Auto-detected, dedup guard active |
| Content deduplication | None cross-system | Events >60% overlapping MEMORY.md are skipped |
| Memory promotion | Manual only | Utility-based script promotes top events |

**How it works**:

1. At session start, the hook checks for `~/.claude/projects/{encoded-path}/memory/MEMORY.md`
2. If found, it reduces compound memory budget from 8K to 4.5K chars (native memory uses ~4-6K)
3. A dedup guard skips compound events whose LESSON content is already well-documented in MEMORY.md
4. High-utility events (cited/injected ratio >= 30%) can be promoted to MEMORY.md

**Promotion workflow**:

```bash
# See which events qualify
python3 config/scripts/promote-to-memory-md.py --dry-run

# Promote top 3 to MEMORY.md
python3 config/scripts/promote-to-memory-md.py
```

Promoted events are tracked in a sidecar file (`promoted-events.json`) so they aren't re-promoted.

**Zero regression risk**: If MEMORY.md detection fails, the system falls back to the 8000-char standalone budget — identical to previous behavior.

#### Opus 4.6 Skill Optimization

All 26 skills were refactored from prescriptive procedures to natural capability modes:

- Removed mandatory agent counts (Opus 4.6 naturally spawns the right number)
- Removed forced ASCII checkpoint diagrams with incorrect fields
- Removed hook enforcement labels that confused more than helped
- Replaced with natural encouragement that the model follows better
- Single universal checkpoint schema from `stop-validator.py` is the only truth

**Key insight**: Skills are MODES that enable capabilities, not PROCEDURES that prescribe steps. When the model is capable enough, removing guardrails produces cleaner execution.

#### Hook System Consolidation

Unified from 24 hooks to 13, reducing ~4500 lines to ~1500:

- Merged duplicate event handlers
- Removed legacy status-file hooks (replaced by Claude Code's native Tasks)
- Combined overlapping functionality into shared modules (`_memory.py`, `_common.py`, `_session.py`)

### Configuration Changes

#### settings.json

```json
{
  "env": {
    "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "64000",
    "MAX_THINKING_TOKENS": "31999",
    "ENABLE_TOOL_SEARCH": "auto",
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  },
  "permissions": {
    "defaultMode": "dontAsk"
  },
  "alwaysThinkingEnabled": true
}
```

**New env vars**:
- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` — enables Agent Teams (swarm mode)
- `ENABLE_TOOL_SEARCH=auto` — defers MCP tool loading until needed (saves 85-95% context tokens)

### New Files

| File | Purpose |
|------|---------|
| `config/scripts/promote-to-memory-md.py` | Promote high-utility compound memories to native MEMORY.md |
| `~/.claude/projects/.../memory/MEMORY.md` | Native project memory seed (created by toolkit) |

### Migration Guide

**From v1.x (pre-Opus 4.6)**:

1. Re-run the installer: `./scripts/install.sh`
2. Restart Claude Code
3. Agent Teams is auto-enabled. To disable: remove `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` from settings.json
4. MEMORY.md is auto-detected. No action needed — the toolkit seeds it if empty

**Manual Agent Teams setup** (if not using install script):

```bash
# Add to ~/.claude/settings.json
python3 -c "
import json
from pathlib import Path
p = Path.home() / '.claude' / 'settings.json'
s = json.loads(p.read_text()) if p.exists() else {}
s.setdefault('env', {})['CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS'] = '1'
p.write_text(json.dumps(s, indent=2))
print('Agent Teams enabled. Restart Claude Code.')
"
```

### Known Limitations

- Agent Teams is experimental — teammates occasionally go idle between turns (this is normal; they wake on message)
- For single-agent read-only analysis, a direct Explore agent is more efficient than a full team
- MEMORY.md path encoding assumes Claude Code's convention (replace `/` and `_` with `-`); a glob fallback handles edge cases
