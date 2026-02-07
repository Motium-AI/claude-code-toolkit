# Appfix Troubleshooting

## Hooks Not Working

**Symptom**: Auto-approval doesn't work, plan mode enforcer doesn't block, stop validator doesn't fire.

**Cause**: Hooks are captured at session startup. Changes don't take effect until a new session.

**Fix**: Exit Claude Code completely, start a new session.

## State File Not Detected

**Symptom**: Auto-approval returns silent passthrough instead of allow.

**Cause**: `is_autonomous_mode_active()` walks up directory tree looking for `.claude/autonomous-state.json`. If not found, auto-approval is disabled.

**Fix**: State file is created automatically by the skill activation (e.g., `/appfix` writes `autonomous-state.json` with `"mode": "repair"`). If missing:
1. Re-invoke the skill (e.g., `/appfix`)
2. Or manually create: `echo '{"mode":"repair"}' > .claude/autonomous-state.json`
3. Start a NEW session

## Auto-Approval After Context Compaction

**Symptom**: After plan phase + context compaction, tool calls need manual approval.

**Cause**: `PermissionRequest` hooks only fire on permission dialogs. After `ExitPlanMode` grants `allowedPrompts`, many tools are pre-approved natively. After compaction, `allowedPrompts` are lost.

**Fix**: `auto-approve.py` (PreToolUse:*) fires for EVERY tool call, bypassing this issue entirely.

## Cross-Repo Detection

**Symptom**: Switching to infra repo loses autonomous mode.

**Cause**: State file walk-up doesn't cross repo boundaries.

**Fix**: User-level state file at `~/.claude/autonomous-state.json` persists across repos (created automatically by skill activation).

## Debug Log

All hooks log to `/tmp/claude-hooks-debug.log`:
```bash
tail -f /tmp/claude-hooks-debug.log
```

## Verify Hook Installation

```bash
./scripts/doctor.sh

# Or manually:
python3 -c "
import sys; sys.path.insert(0, '$HOME/.claude/hooks')
from _common import is_autonomous_mode_active, is_appfix_active
print('appfix:', is_appfix_active('$(pwd)'))
print('autonomous:', is_autonomous_mode_active('$(pwd)'))
"
```
