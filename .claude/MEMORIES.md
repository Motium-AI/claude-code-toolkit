# Session Memories

## Source of Truth

**This repo (`namshub`) is the source of truth for all skills, hooks, and configuration.**

`~/.claude/skills/` and `~/.claude/hooks/` are symlinks to this repo's `config/` directory. When you edit skills or hooks (including via `~/.claude/`), you're editing this repo. **Always commit changes to preserve them.**

---

## Memory System v3 (2026-01-31)

**Cross-session learning** via append-only event store in `~/.claude/memory/{project-hash}/events/`.

- **Auto-capture**: Checkpoint requires `key_insight` (>30 chars), `search_terms` (2-7 concept keywords), `category` enum, and optional `memory_that_helped` (event IDs) — archived on every successful stop
- **Auto-injection**: Top 10 relevant events injected at SessionStart via 4-signal scoring (entity 35%, recency 30%, quality 20%, source 15%)
- **Entity matching**: Concept keywords (tools, errors, techniques, platforms) + file paths (basename, stem, dir)
- **Dedup**: Prefix-hash guard (8-event lookback, 60-min window) prevents duplicates
- **Manual capture**: `/compound` skill for deep LESSON/PROBLEM/CAUSE/FIX documentation
- **Feedback loop**: Injection logging at SessionStart, utility tracking at Stop, per-event demotion (3+ injections with 0 citations), auto-tuned MIN_SCORE via proportional controller (bounded [0.05, 0.25])

See [docs/index.md](../docs/index.md#memory-system-v3) for full details.

---

## Architectural Decisions

### Status File Enforcement (2026-01-09, updated)
**Decision**: Two-phase enforcement - checklist visibility AND status blocking.

**Why**: Need both: (1) Full checklist always shown on first stop, (2) Status file actually enforced before allowing stop.

**Implementation**:
- First stop: Show full checklist with status as item 0 (if failed)
- Second stop: Check status again - block if still stale, allow if fresh
- This ensures checklist is never bypassed AND status is always enforced

### Change-Type Detection Filtering (2026-01-09)
**Decision**: Three-layer filtering to reduce false positives in stop-validator pattern detection.

**Why**: Patterns like `.filter(`, `.all()`, `datetime` are too generic - they match CSS, JS array methods, docs, and even the hook script itself.

**Implementation**:
1. Exclude paths: `hooks/`, `.claude/`, `node_modules/`
2. Only analyze changed lines (`+`/`-`), not diff context
3. File-extension aware: ORM patterns → `.py` only, link/websocket → `.js/.ts/.tsx` only
