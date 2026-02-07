# Settings Reference

The `config/settings.json` file defines global settings and hook configurations for Claude Code.

## Environment Variables

These variables control Claude Code's behavior:

| Variable | Default | Purpose |
|----------|---------|---------|
| `CLAUDE_CODE_MAX_OUTPUT_TOKENS` | `128000` | Maximum tokens in Claude's response output |

```json
{
  "env": {
    "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "128000"
  }
}
```

> **Note**: `MAX_THINKING_TOKENS` was removed — it bleeds into Haiku subagents, exceeding their 64k ceiling. Claude Code manages thinking token allocation per-model automatically.

## Boolean Flags

| Flag | Default | Purpose |
|------|---------|---------|
| `alwaysThinkingEnabled` | `true` | Force extended thinking for all responses |

When enabled, Claude uses extended thinking mode to reason through complex problems before responding.

## Hook Definitions

Hooks are defined as arrays under event type keys. Each event can have multiple hook configurations.

### Structure

```json
{
  "hooks": {
    "EventType": [
      {
        "matcher": "optional-filter",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/hooks/script.py",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `type` | Yes | Always `"command"` for shell/Python hooks |
| `command` | Yes | Shell command to execute (receives JSON on stdin) |
| `timeout` | No | Maximum seconds to wait (default: 60) |
| `matcher` | No | Filter when hook runs (see Matchers below) |

### Matchers

Matchers filter when a hook should run:

| Type | Example | Description |
|------|---------|-------------|
| String | `"compact"` | Match SessionStart source field |
| String | `"AskUserQuestion"` | Match tool name for PreToolUse |
| Object | `{"tool_name": "ExitPlanMode"}` | Match specific tool for PostToolUse |

## Event Types

The toolkit defines hooks for these events:

| Event | When Triggered | Common Use |
|-------|----------------|------------|
| `SessionStart` | New conversation starts | Force reading project docs |
| `Stop` | Claude attempts to stop | Compliance validation |
| `UserPromptSubmit` | User sends a message | Suggest relevant docs |
| `PreToolUse` | Before tool execution | Auto-answer questions |
| `PostToolUse` | After tool execution | Inject context |
| `PermissionRequest` | Before permission prompt | Auto-approve actions |
| `SubagentStop` | Subagent finishes | Validate output |

## Complete Example

```json
{
  "env": {
    "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "128000"
  },
  "alwaysThinkingEnabled": true,
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/hooks/read-docs-reminder.py",
            "timeout": 5
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/hooks/stop-validator.py",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

## Environment Variables (Runtime)

These environment variables affect hook behavior at runtime:

| Variable | Effect |
|----------|--------|
| `FLEET_ROLE` | Set to `"knowledge_sync"` or `"scheduled_job"` to skip hooks for automation |

## State Files

Hooks may read/write state files in `.claude/`:

| File | Purpose |
|------|---------|
| `.claude/testing-state.json` | Records /webtest execution evidence |
| `.claude/autonomous-state.json` | Tracks autonomous skill activation (mode: melt/repair/burndown/improve/episode) |
| `.claude/compliance-checklist.md` | Stop hook compliance output |

## Related Documentation

- [Hooks Concept](../concepts/hooks.md) — How hooks work
- [Customization Guide](../guides/customization.md) — Creating custom hooks
