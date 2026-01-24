# Claude Code Hooks: Global Implementation

Reference documentation for implementing global Claude Code hooks that inject context and enforce behavior.

## Overview

Claude Code supports a hooks system that executes shell commands in response to lifecycle events. This document covers three patterns:

1. **SessionStart (Context Injection)**: Force Claude to read project documentation before beginning work
2. **Stop (Compliance Blocking)**: Block Claude from stopping until compliance checks are addressed
3. **UserPromptSubmit (On-Demand Doc Reading)**: Trigger deep documentation reading when user says "read the docs"

> **Note**: Status file hooks were removed in January 2025. Anthropic's native Tasks feature now provides better session tracking and coordination. See [Tasks Deprecation Note](#tasks-deprecation-note) below.

## Key Concepts

### Two-Phase Stop Flow

The Stop hook implements a two-phase blocking pattern to prevent infinite loops:

```
First stop (stop_hook_active=false):
→ Show FULL compliance checklist
→ Block (exit 2)

Second stop (stop_hook_active=true):
→ Allow stop (exit 0)
```

This ensures Claude sees the full checklist at least once, while preventing infinite loops.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    ~/.claude/settings.json                      │
├─────────────────────────────────────────────────────────────────┤
│  hooks:                                                         │
│    SessionStart → type: "command" → echo (context injection)    │
│    Stop         → type: "command" → script (blocking)          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                 ~/.claude/hooks/stop-validator.py               │
├─────────────────────────────────────────────────────────────────┤
│  Reads stdin JSON → Checks stop_hook_active → Exit code 0 or 2 │
└─────────────────────────────────────────────────────────────────┘
```

### Hook Types and Exit Codes

| Type | Behavior | Use Case |
|------|----------|----------|
| `command` | Executes shell command | All hooks |
| `prompt` | Invokes LLM for JSON response | Avoid (unreliable) |

| Exit Code | Effect |
|-----------|--------|
| 0 | Success, allow action |
| 2 | Block action, stderr shown to Claude |
| Other | Non-blocking error, logged only |

### JSON Input Schema

All hooks receive JSON input via stdin with these fields:

```json
{
  "session_id": "abc123-def456-...",
  "cwd": "/path/to/project",
  "hook_event_name": "Stop",
  "stop_hook_active": false
}
```

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string | Unique session identifier (for session-specific files) |
| `cwd` | string | Current working directory of the Claude session |
| `hook_event_name` | string | The hook event type (SessionStart, Stop, UserPromptSubmit) |
| `stop_hook_active` | boolean | **Stop hook only**: True if Claude is continuing after a previous block |
| `message` | string | **UserPromptSubmit only**: The user's message text |

### SessionStart Matchers

SessionStart hooks accept optional matchers to fire on specific triggers:

| Matcher | Description |
|---------|-------------|
| `startup` | Fresh session start |
| `resume` | Resuming from previous context |
| `clear` | After /clear command |
| `compact` | After context compaction |

If no matcher is specified, the hook fires on all SessionStart events.

## Implementation

### Global Configuration

Location: `~/.claude/settings.json`

```json
{
  "env": {
    "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "64000",
    "MAX_THINKING_TOKENS": "31999"
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

### SessionStart Hook

Forces Claude to read project documentation before executing any user request. Uses echo with exit code 0 (context injection, non-blocking).

**Key language patterns that drive compliance**:
- `MANDATORY` / `MUST` - imperative, not suggestive
- `DO NOT skip` - explicit prohibition
- `Actually READ the files` - prevents "I'll summarize from memory" shortcuts
- `The user expects...` - frames as user requirement, not system preference

### Stop Hook (Blocking)

Uses a Python script that blocks Claude from stopping until it addresses compliance checks.

#### The Loop Problem

Without loop prevention:
```
Claude finishes → Stop blocks → Claude works → Claude finishes → Stop blocks → ∞
```

#### The Solution: `stop_hook_active` Flag

The Stop hook receives `stop_hook_active: true` when Claude is already continuing due to a previous block:

```
First stop:  stop_hook_active=false → Block with instructions
Second stop: stop_hook_active=true  → Allow (loop prevention)
```

#### Stop Validator Script

Location: `~/.claude/hooks/stop-validator.py`

The stop validator implements two-phase blocking with change-type detection:

**Phase 1 (First Stop)**: Shows the full compliance checklist
**Phase 2 (Second Stop)**: Only enforces status file freshness

```python
#!/usr/bin/env python3
"""
Global Stop Hook Validator

Two-phase stop flow:
1. First stop (stop_hook_active=false): Show FULL compliance checklist, block
2. Second stop (stop_hook_active=true): Enforce status file freshness, then allow

Exit codes:
  0 - Allow stop
  2 - Block stop (stderr shown to Claude)
"""
import json
import sys
from datetime import datetime
from pathlib import Path

STATUS_FILE_MAX_AGE_SECONDS = 300  # 5 minutes

def check_status_file(cwd: str, session_id: str = "") -> tuple[bool, str]:
    """Check session-specific or legacy status file."""
    claude_dir = Path(cwd) / ".claude"

    # Try session-specific file first
    if session_id:
        session_path = claude_dir / f"status.{session_id}.md"
        if session_path.exists():
            return check_freshness(session_path)

    # Fall back to legacy
    legacy_path = claude_dir / "status.md"
    if legacy_path.exists():
        return check_freshness(legacy_path)

    return False, "MISSING: status file not found"

def main():
    input_data = json.load(sys.stdin)
    cwd = input_data.get("cwd", "")
    session_id = input_data.get("session_id", "")
    stop_hook_active = input_data.get("stop_hook_active", False)

    # SECOND STOP: Only enforce status, then allow
    if stop_hook_active:
        status_ok, msg = check_status_file(cwd, session_id)
        if not status_ok:
            print(f"🚫 STATUS FILE STILL NOT UPDATED\n{msg}", file=sys.stderr)
            sys.exit(2)
        sys.exit(0)  # Allow stop

    # FIRST STOP: Show FULL checklist
    status_ok, status_msg = check_status_file(cwd, session_id)
    # ... detect change types from git diff ...
    # ... format full checklist with status as item 0 if needed ...
    print(instructions, file=sys.stderr)
    sys.exit(2)
```

#### Change-Type Detection

The stop validator detects change types from `git diff` and shows relevant testing requirements:

| Change Type | Detected Patterns | Example Tests |
|-------------|-------------------|---------------|
| `env_var` | `NEXT_PUBLIC_`, `process.env.`, `os.environ` | Check for localhost fallbacks |
| `auth` | `clearToken`, `logout`, `useAuth` | Test 401 cascade behavior |
| `link` | `<Link`, `router.push`, `href="/"` | Validate route targets exist |
| `api_route` | `@app.get`, `APIRouter`, `FastAPI` | Test through proxy, check 307 redirects |
| `websocket` | `WebSocket`, `wss://`, `socket.on` | Test with production WS URL |
| `database` | `CREATE TABLE`, `migration`, `alembic` | Run migrations, verify rollback |
| `proxy` | `proxy`, `rewrites`, `CORS` | Test full request flow |
| `datetime_boundary` | `datetime`, `timezone`, `openpyxl` | Test with tz-aware datetimes |
| `serialization_boundary` | `.model_dump`, `json.dumps`, `BytesIO` | Test with UUID, Decimal types |
| `orm_boundary` | `.query(`, `.filter(`, `AsyncSession` | Integration test with real DB |
| `file_export` | `to_excel`, `csv.writer`, `Workbook(` | Parse actual output in tests |

When detected, the checklist includes a section like:
```
4. CHANGE-SPECIFIC TESTING REQUIRED:

   ⚠️  AUTH CHANGES DETECTED:
      - Trace all paths to token clearing functions
      - Test auth cascade: what happens on 401 response?
      - Verify network failures don't incorrectly clear auth state
```

**Mnemonic structure** in the instructions:

| Category | Mnemonics | Full Principle |
|----------|-----------|----------------|
| Philosophy | `boring over clever` | Clarity Over Cleverness: Write explicit, obvious code |
| Philosophy | `local over abstract` | Locality Over Abstraction: Prefer self-contained modules |
| Philosophy | `small composable units` | Compose Small Units: Single-purpose, safely rewritable |
| Philosophy | `stateless with side effects at edges` | Stateless by Default: Pure functions, effects at boundaries |
| Philosophy | `fail loud never silent` | Fail Fast & Loud: No silent catches |
| Philosophy | `tests are truth` | Tests as Specification: Tests define correct behavior |
| Style | `type hints everywhere` | Type hints on all functions |
| Style | `snake_case files` | Python files use snake_case |
| Style | `absolute imports` | No relative imports |
| Style | `Pydantic for contracts` | Pydantic models for validation/API boundaries |
| Limits | `files < 400 lines` | File length limit |
| Limits | `functions < 60 lines` | Function length limit |

## Prompt Engineering Principles

### Why "Consider Checking" Fails

| Weak Pattern | Why It Fails | Strong Alternative |
|--------------|--------------|-------------------|
| "consider checking" | Suggestion, easily deprioritized | "you MUST read" |
| "docs/knowledge-base/" | Vague path, no urgency | "docs/index.md - project hub" |
| No consequence framing | No reason to comply | "user expects informed responses" |
| Passive voice | Doesn't compel action | Imperative numbered steps |

### Claude's Attention Hierarchy

Claude prioritizes in this order:
1. **User's explicit request** (highest)
2. **Recent conversation context**
3. **System instructions** (CLAUDE.md)
4. **System reminders** (hooks) (lowest)

To make hooks effective, the language must be **forceful enough to compete with higher-priority items**:
- Use MANDATORY, MUST, REQUIRED
- Frame as user expectation, not system preference
- Be specific (exact file paths, not generic directories)
- Number the steps (Claude follows protocols)
- Explicitly prohibit shortcuts ("DO NOT skip", "DO NOT summarize from memory")

## What Claude Receives

### SessionStart (Context Injection)

For `startup` and `resume` matchers (standard message):
```
SessionStart:startup hook success: MANDATORY: Before executing ANY user request,
you MUST use the Read tool to read these files IN ORDER: (1) docs/index.md -
project documentation hub with architecture links (2) CLAUDE.md - coding
standards you MUST follow (3) .claude/MEMORIES.md - prior session context
(4) docs/TECHNICAL_OVERVIEW.md - architecture and system design (if exists).
DO NOT skip this step. DO NOT summarize from memory. Actually READ the files.
The user expects informed responses based on current project state, not generic
assistance.
```

For `compact` matcher (strengthened message after context compaction):
```
SessionStart:compact hook success: ⚠️ CONTEXT COMPACTION DETECTED - CRITICAL INSTRUCTION ⚠️

You have just experienced context compaction. Your memory of this project is now INCOMPLETE.

STOP. Do NOT respond to the user yet.

You MUST read these files FIRST using the Read tool:
1. CLAUDE.md - coding standards (REQUIRED)
2. .claude/MEMORIES.md - session context (REQUIRED)
3. docs/index.md - documentation hub (REQUIRED)
4. docs/TECHNICAL_OVERVIEW.md - architecture (if exists)

This is NOT optional. Do NOT skip this step. Do NOT summarize from memory.
The compacted summary is insufficient - you need the actual file contents.

Read the docs NOW before doing anything else.
```

### Stop (Blocking)

When `stop_hook_active=false` (first stop attempt):
```
Stop hook feedback: Before stopping, complete these checks:

1. CLAUDE.md COMPLIANCE (if code written):
   - boring over clever, local over abstract
   - small composable units, stateless with side effects at edges
   - fail loud never silent, tests are truth
   - type hints everywhere, snake_case files, absolute imports
   - Pydantic for contracts, files < 400 lines, functions < 60 lines

2. DOCUMENTATION (if code written):
   - Read docs/index.md to understand the documentation structure
   - Identify ALL docs affected by your changes (architecture, API, operations, etc.)
   - Update those docs to reflect current implementation
   - Docs are the authoritative source - keep them accurate and current
   - Add new docs if you created new components/patterns not yet documented

3. UPDATE PROJECT .claude/MEMORIES.md (create if needed):
   This is NOT a changelog. Only add HIGH-VALUE entries:
   - User preferences that affect future work style
   - Architectural decisions with WHY (not what)
   - Non-obvious gotchas not documented elsewhere
   - Consolidate/update existing entries rather than append duplicates
   - If nothing significant learned, skip this step

After completing these checks, you may stop.
```

When `stop_hook_active=true` (second stop attempt): Hook allows stop silently.

### UserPromptSubmit Hook (On-Demand)

Triggers when the user includes "read the docs" in their message. Unlike SessionStart (which fires once), this allows on-demand deep documentation reading mid-session.

#### Read Docs Trigger Script

Location: `~/.claude/hooks/read-docs-trigger.py`

```python
#!/usr/bin/env python3
"""
UserPromptSubmit hook - triggers documentation reading when user says "read the docs".
"""
import json
import sys


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    message = input_data.get("message", "").lower()

    # Only fire when user explicitly requests doc reading
    if "read the docs" not in message:
        sys.exit(0)

    reminder = """Before starting this task, you MUST:

1. Read docs/index.md to understand the documentation structure
2. Follow links to the most relevant docs for this specific request
3. Read as deeply as logical - the documentation is up-to-date and authoritative
4. Apply the patterns and conventions documented there

Do NOT skip this step. Do NOT rely on memory. Actually READ the current docs."""

    print(reminder)
    sys.exit(0)


if __name__ == "__main__":
    main()
```

**Usage**: Include "read the docs" anywhere in your message:
- "read the docs and implement the new API endpoint"
- "I need you to read the docs before refactoring this module"

**When to use**:
- Mid-session when documentation has been updated
- For complex tasks requiring deep pattern knowledge
- When Claude seems to be ignoring documented conventions

## Memory File Convention

The implementation assumes per-project memory files:

```
<project-root>/
└── .claude/
    └── MEMORIES.md    # Curated, high-value context for future sessions
```

**MEMORIES.md is NOT a changelog.** It should be:
- **Curated**: Only high-signal information
- **Consolidated**: Update existing entries rather than appending duplicates
- **Actionable**: Information that affects how work should be done
- **Pruned**: Remove stale or superseded entries

Format recommendation:

```markdown
## User Preferences
- Prefers X approach over Y (context: why this matters)

## Architectural Decisions
- Chose pattern A because B (date: 2025-01-05)

## Gotchas
- Component X has quirk Y - must handle with Z
```

**What NOT to include**:
- What was done (use git history)
- Every file touched
- Trivial decisions
- Information already in docs/CLAUDE.md

## Testing & Verification

### Verify SessionStart Hook

1. Start a new Claude Code session (or resume)
2. Look for system message: `SessionStart:* hook success: MANDATORY...`
3. Verify Claude actually uses Read tool on docs/index.md, CLAUDE.md, .claude/MEMORIES.md, and docs/TECHNICAL_OVERVIEW.md (if exists) before responding

### Verify Stop Hook (Blocking)

1. Complete a task in Claude Code
2. Claude tries to stop → Hook blocks with instructions
3. Claude addresses the instructions (verifies compliance, updates MEMORIES)
4. Claude tries to stop again → Hook allows (stop_hook_active=true)

### Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `SessionStart:* hook error` | Hook command failed | Check command syntax |
| `Stop hook error` | Script failed | Check script path, permissions |
| `Hook timed out` | Command exceeds timeout | Increase timeout value |
| Infinite loop | Not checking stop_hook_active | Ensure script checks flag |

## Common Gotchas

### MCP Configuration and Environment Variables

**Problem**: Claude Code's `.mcp.json` does NOT read from `.env` files.

```json
// BROKEN - ${VAR} syntax fails silently
{
  "mcpServers": {
    "logfire": {
      "env": {
        "LOGFIRE_READ_TOKEN": "${LOGFIRE_READ_TOKEN}"  // ❌ Won't work
      }
    }
  }
}
```

**Solution**: Hardcode tokens directly in `.mcp.json` and add the file to `.gitignore`:

```json
// WORKING - hardcoded token
{
  "mcpServers": {
    "logfire": {
      "env": {
        "LOGFIRE_READ_TOKEN": "pylf_v1_actual_token_here"  // ✅ Works
      }
    }
  }
}
```

```bash
# Protect the file
echo ".mcp.json" >> .gitignore
```

**Why**: MCP servers spawn as subprocesses that don't inherit your shell's environment loading. Variables must either exist in the shell environment OR be hardcoded in the config.

## Historical Note: Prompt-Type Hook Issues

We initially attempted `type: "prompt"` for the Stop hook, but encountered:

### Schema Validation Error

```
Schema validation failed: [
  {
    "code": "invalid_type",
    "expected": "boolean",
    "received": "undefined",
    "path": ["ok"],
    "message": "Required"
  }
]
```

### JSON Validation Error

Even with the correct schema, the model sometimes failed to produce valid JSON, causing:
```
Stop hook error: JSON validation failed
```

**Conclusion**: `type: "prompt"` hooks are unreliable. Use `type: "command"` with exit codes instead.

## Optional Hooks (Disabled by Default)

Two additional hooks exist in `config/hooks/` but are not enabled in `settings.json`:

### skill-reminder.py

Scans user prompts for keywords and suggests relevant skills.

**Purpose**: Automatically remind Claude to use skills like `/nextjs-tanstack-stack` when relevant keywords appear.

**How it works**:
1. Receives user prompt via stdin JSON (`message` field)
2. Matches keywords against skill trigger patterns
3. Outputs suggestion like: `Consider using the Skill tool to invoke /nextjs-tanstack-stack`

**To enable**, add to `settings.json` under `UserPromptSubmit`:

```json
{
  "type": "command",
  "command": "python3 ~/.claude/config/hooks/skill-reminder.py",
  "timeout": 5
}
```

**Why disabled**: Can be noisy if you don't use skills frequently. Enable if you want proactive skill suggestions.

## Tasks Deprecation Note

**Status file hooks were removed in January 2025** because Anthropic implemented native Tasks in Claude Code.

### Why Tasks Replace Status Files

The original status file system (`status-working.py`, `finalize-status-v5.py`, etc.) was a custom solution for:
- Tracking what Claude is working on
- Coordinating across sessions
- Monitoring via external UI (Mimesis)

Anthropic's native **Tasks** feature provides all of this natively with better capabilities:

| Old (Status Files) | New (Tasks) |
|-------------------|-------------|
| Custom markdown files per session | Native `~/.claude/tasks/` storage |
| Manual status updates via hooks | Automatic task tracking |
| Session-specific isolation | Cross-session coordination |
| Required hook enforcement | Built-in to Claude Code |

### Using Native Tasks

Tasks are now built into Claude Code. Key features:

```bash
# Share a task list across sessions
CLAUDE_CODE_TASK_LIST_ID=my-project claude

# Tasks persist in ~/.claude/tasks/
# Multiple sessions can collaborate on same task list
```

**When to use Tasks**:
- Multi-step projects spanning sessions
- Subagent coordination
- Complex tasks with dependencies and blockers

**Task capabilities**:
- Dependencies between tasks
- Blockers that prevent progress
- Broadcasts when tasks are updated
- Works with `claude -p` and Agent SDK

For more details, see the [official Tasks announcement](https://x.com/trq212/status/...).

## Related Documentation

- [Claude Code Hooks Reference](https://code.claude.com/docs/en/hooks.md) - Official documentation
- [Commands Reference](./commands.md) - Custom slash commands
- [Skills Reference](./skills.md) - Domain-specific knowledge injection
- [Config Files](../../config/) - Actual hook/skill/command files for installation
- Project CLAUDE.md - Per-project coding standards
- Project .claude/MEMORIES.md - Per-project session memories
