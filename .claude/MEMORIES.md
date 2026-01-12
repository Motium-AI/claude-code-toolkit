# Session Memories

## Architectural Decisions

### Status File Enforcement (2026-01-09, updated)
**Decision**: Two-phase enforcement - checklist visibility AND status blocking.

**Why**: Need both: (1) Full checklist always shown on first stop, (2) Status file actually enforced before allowing stop.

**Implementation**:
- First stop: Show full checklist with status as item 0 (if failed)
- Second stop: Check status again - block if still stale, allow if fresh
- This ensures checklist is never bypassed AND status is always enforced

### Claude Auto-Switch Multi-Account (2026-01-12, updated)
**Decision**: Use `CLAUDE_CONFIG_DIR` env var with PTY wrapper for automatic account switching.

**Why**: No programmatic API exists to detect rate limits - only terminal output patterns. Using PTY preserves interactive features while allowing stdout monitoring.

**Implementation**:
- `~/.claude` = primary account, `~/.claude-max-2` = backup
- Wrapper monitors output for rate limit patterns ("usage limit", "capacity exceeded", etc.)
- On detection: saves last 50 lines as context, switches account, injects context as prompt
- Config in `~/.claude/scripts/claude-auto-switch/config.json`

**PTY Gotcha**: PTY wrappers must handle bidirectional I/O:
- Monitor BOTH `stdin` and PTY fd in `select()` - not just PTY output
- Forward stdin to PTY child with `os.write(fd, data)`
- Set terminal to raw mode with `tty.setraw()` for proper keystroke handling
- ALWAYS restore terminal settings in `finally` block with `termios.tcsetattr()`
- Without this, terminal freezes because child process never receives keystrokes

### Change-Type Detection Filtering (2026-01-09)
**Decision**: Three-layer filtering to reduce false positives in stop-validator pattern detection.

**Why**: Patterns like `.filter(`, `.all()`, `datetime` are too generic - they match CSS, JS array methods, docs, and even the hook script itself.

**Implementation**:
1. Exclude paths: `hooks/`, `.claude/`, `node_modules/`
2. Only analyze changed lines (`+`/`-`), not diff context
3. File-extension aware: ORM patterns → `.py` only, link/websocket → `.js/.ts/.tsx` only
