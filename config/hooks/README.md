# Hook Scripts

This directory contains Python hook scripts that extend Claude Code's lifecycle events.

## Active Hooks (14 registered in settings.json)

| Script | Event | Purpose |
|--------|-------|---------|
| `auto-update.py` | SessionStart | Auto-updates toolkit from GitHub on session start |
| `session-init.py` | SessionStart | Session initialization (cleanup, state management) |
| `compound-context-loader.py` | SessionStart | Injects top-5 relevant memory events at session start |
| `read-docs-reminder.py` | SessionStart | Reminds to read project documentation on new sessions |
| `read-docs-trigger.py` | UserPromptSubmit | Suggests reading docs when "read the docs" appears in prompt |
| `auto-approve.py` | PreToolUse (*) | Auto-approves ALL tools during autonomous mode |
| `deploy-enforcer.py` | PreToolUse (Bash) | Blocks subagent deploys and production deploys |
| `azure-command-guard.sh` | PreToolUse (Bash) | Blocks dangerous Azure CLI commands |
| `exa-search-enforcer.py` | PreToolUse (WebSearch) | Blocks WebSearch, redirects to Exa MCP |
| `tool-usage-logger.py` | PostToolUse (*) | Logs tool usage for post-session behavioral analysis |
| `memory-recall.py` | PostToolUse (Read/Grep/Glob) | Mid-session memory retrieval (8 recalls/session) |
| `bash-version-tracker.py` | PostToolUse (Bash) | Tracks version after git commits, updates checkpoint |
| `doc-updater-async.py` | PostToolUse (Bash) | Suggests async doc updates after git commits |
| `skill-continuation-reminder.py` | PostToolUse (Skill) | Continues autonomous loop after skill delegation |
| `stop-validator.py` | Stop | Validates completion checkpoint before allowing session end |
| `precompact-capture.py` | PreCompact | Injects session summary before context compaction |
| `auto-approve.py` | PermissionRequest (*) | Fallback auto-approve during autonomous mode |

## Internal Modules (Not Lifecycle Hooks)

| Module | Purpose |
|--------|---------|
| `_common.py` | Shared utility functions (TTL checks, version tracking, logging, worktree detection) |
| `_memory.py` | Memory primitives (event store, entity matching, crash-safe writes) |
| `_session.py` | Unified session state management (autonomous-state.json, checkpoint operations) |

## Utility Scripts (Not Lifecycle Hooks)

| Script | Purpose |
|--------|---------|
| `surf-verify.py` | Runs Surf CLI for browser verification, generates web-smoke artifacts |
| `worktree-manager.py` | Creates/manages git worktrees for parallel agent isolation |
| `cleanup.py` | Reclaim disk space from Claude Code session data |

### `_common.py` Key Functions

```python
is_state_expired(state)         # Check if state file exceeded TTL
is_pid_alive(pid)               # Check if process is running
get_code_version(cwd)           # Returns "abc1234" or "abc1234-dirty"
get_diff_hash(cwd)              # Returns 12-char hash of current diff
log_debug(message, hook_name)   # Write debug logs
```

### `_session.py` Key Functions

```python
is_autonomous_mode_active(cwd)  # Check if autonomous-state.json exists and is valid
get_autonomous_state(cwd)       # Get state dict and mode string
get_mode(cwd)                   # Get current mode (melt, repair, burndown, etc.)
write_autonomous_state(cwd, mode)  # Create autonomous-state.json
cleanup_autonomous_state(cwd)   # Remove all state files
load_checkpoint(cwd)            # Load completion-checkpoint.json
save_checkpoint(cwd, data)      # Save checkpoint atomically
```

## Security Model

Auto-approval hooks only activate when `autonomous-state.json` exists with a valid (non-expired) mode. Normal sessions without this file require user approval for all tool operations.

## Hook Execution Flow

```
SessionStart
    └── auto-update.py (updates toolkit from GitHub)
    └── session-init.py (cleanup, state management)
    └── compound-context-loader.py (injects memory events)
    └── read-docs-reminder.py (reminds to read docs)

UserPromptSubmit
    └── read-docs-trigger.py (checks for "read the docs")

PreToolUse (*)
    └── auto-approve.py (auto-approve if autonomous mode active)

PreToolUse (Bash)
    └── deploy-enforcer.py (blocks subagent/production deploys)
    └── azure-command-guard.sh (blocks dangerous az commands)

PreToolUse (WebSearch)
    └── exa-search-enforcer.py (blocks WebSearch, redirects to Exa MCP)

PostToolUse (*)
    └── tool-usage-logger.py (logs tool usage for behavioral analysis)

PostToolUse (Read/Grep/Glob)
    └── memory-recall.py (mid-session memory retrieval)

PostToolUse (Bash)
    └── bash-version-tracker.py (tracks version after git commits)
    └── doc-updater-async.py (suggests doc updates)

PostToolUse (Skill)
    └── skill-continuation-reminder.py (continues autonomous loop)

Stop
    └── stop-validator.py (validates checkpoint + auto-captures memory event)

PreCompact
    └── precompact-capture.py (injects session summary)

PermissionRequest (*)
    └── auto-approve.py (fallback auto-approve if autonomous)
```

## Diagnostic Tools

| Script | Location | Purpose |
|--------|----------|---------|
| `routing-audit.py` | `config/scripts/` | Post-session behavioral pattern detection (edit-test loops, grep storms, file thrash) |

## Testing

Three levels of tests verify hook behavior:

```bash
# Level 1: Pytest subprocess tests (fast, no API cost)
cd prompts && python3 -m pytest config/hooks/tests/ -v

# Level 2: Claude headless E2E (real sessions, ~$0.05-0.15)
cd prompts && bash scripts/test-e2e-headless.sh

# Level 3: tmux interactive E2E (manual observation)
cd prompts && bash scripts/test-e2e-tmux.sh --observe
```

## Related Documentation

- [Hook System Deep Dive](../../docs/concepts/hooks.md)
- [Settings Reference](../../docs/reference/settings.md)
- [Appfix Guide](../../docs/skills/appfix-guide.md)
