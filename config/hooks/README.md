# Hook Scripts

This directory contains Python hook scripts that extend Claude Code's lifecycle events.

## Active Hooks (Configured in settings.json)

| Script | Event | Purpose |
|--------|-------|---------|
| `session-snapshot.py` | SessionStart | Captures git diff hash at session start for change tracking |
| `read-docs-reminder.py` | SessionStart | Reminds to read project documentation on new sessions |
| `stop-validator.py` | Stop | Validates completion checkpoint before allowing session end |
| `checkpoint-invalidator.py` | PostToolUse (Edit/Write) | Resets stale checkpoint fields when code changes |
| `plan-execution-reminder.py` | PostToolUse (ExitPlanMode) | Injects autonomous execution context after plan approval |
| `plan-mode-tracker.py` | PostToolUse (ExitPlanMode) | Marks plan_mode_completed=true in state file |
| `plan-mode-enforcer.py` | PreToolUse (Edit/Write) | Blocks Edit/Write on first godo/appfix iteration until plan mode completed |
| `appfix-auto-approve.py` | PermissionRequest | Auto-approves ALL tools during godo/appfix mode |
| `read-docs-trigger.py` | UserPromptSubmit | Suggests reading docs when "read the docs" appears in prompt |

## Utility Scripts (Not Lifecycle Hooks)

| Script | Purpose |
|--------|---------|
| `_common.py` | Shared utility functions used by other hooks |
| `surf-verify.py` | Runs Surf CLI for browser verification, generates web-smoke artifacts |

### _common.py Functions

```python
# State detection
is_godo_active(cwd)             # Check if .claude/godo-state.json exists
is_appfix_active(cwd)           # Check if .claude/appfix-state.json exists
is_autonomous_mode_active(cwd)  # Check if either godo or appfix is active

# Version tracking (excludes infrastructure paths from dirty check)
get_code_version(cwd)           # Returns "abc1234" or "abc1234-dirty" (stable during edits)
get_diff_hash(cwd)              # Returns 12-char hash of current diff

# Debugging
log_debug(message, cwd)         # Write debug logs to temp dir

# Shared constants
VERSION_TRACKING_EXCLUSIONS     # Git pathspecs excluding .claude/, locks, etc.
```

### Infrastructure Path Exclusions

The `stop-validator.py` and related hooks exclude these paths from deployment/linting requirements:

```python
infrastructure_patterns = [
    'config/hooks/',      # Hook scripts
    'config/skills/',     # Skill definitions
    'config/commands/',   # Command definitions
    '.claude/',           # State and checkpoint files
    'prompts/config/',    # Toolkit configuration
    'prompts/scripts/',   # Documentation utilities
    'scripts/',           # Project scripts
]
```

Changes to these paths are treated as "infrastructure changes" and don't require deployment, linting, or browser testing.

## Unused Hooks (Not in settings.json)

| Script | Status | Notes |
|--------|--------|-------|
| `appfix-bash-auto-approve.py` | Deprecated | Superseded by unified `appfix-auto-approve.py` |
| `appfix-exitplan-auto-approve.py` | Deprecated | Superseded by unified `appfix-auto-approve.py` |
| `skill-reminder.py` | Optional | Disabled by design; noisy for users who don't use skills frequently |

### Enabling skill-reminder.py

To enable skill suggestions, add to `settings.json` under `UserPromptSubmit`:

```json
{
  "type": "command",
  "command": "python3 ~/.claude/config/hooks/skill-reminder.py",
  "timeout": 5
}
```

## Security Model

Auto-approval hooks only activate when a state file exists:
- `.claude/godo-state.json` - Created by `/godo` skill
- `.claude/appfix-state.json` - Created by `/appfix` skill

Normal sessions without these files require user approval for all tool operations.

## Hook Execution Flow

```
SessionStart
    └─► session-snapshot.py (captures git hash)
    └─► read-docs-reminder.py (reminds to read docs)

UserPromptSubmit
    └─► read-docs-trigger.py (checks for "read the docs")

PreToolUse (Edit/Write)
    └─► plan-mode-enforcer.py (blocks until plan mode completed, iteration 1 only)

PostToolUse (Edit/Write)
    └─► checkpoint-invalidator.py (resets stale checkpoint)

PostToolUse (ExitPlanMode)
    └─► plan-execution-reminder.py (injects context)
    └─► plan-mode-tracker.py (marks plan_mode_completed=true)

PermissionRequest (any tool)
    └─► appfix-auto-approve.py (auto-approve if godo/appfix active)

Stop
    └─► stop-validator.py (validates checkpoint)
```

## Related Documentation

- [Hook System Deep Dive](../../docs/concepts/hooks.md)
- [Settings Reference](../../docs/reference/settings.md)
- [Appfix Guide](../../docs/skills/appfix-guide.md)
