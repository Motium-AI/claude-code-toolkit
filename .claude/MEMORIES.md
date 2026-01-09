# Session Memories

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
