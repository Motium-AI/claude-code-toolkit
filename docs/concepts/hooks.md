# Claude Code Hooks: Global Implementation

Reference documentation for implementing global Claude Code hooks that inject context and enforce behavior.

## Overview

Claude Code supports a hooks system that executes shell commands in response to lifecycle events. This document covers eight event types:

1. **SessionStart (Context Injection)**: Force Claude to read project documentation before beginning work
2. **Stop (Compliance Blocking)**: Block Claude from stopping until compliance checks are addressed
3. **UserPromptSubmit (On-Demand Doc Reading)**: Trigger deep documentation reading when user says "read the docs"
4. **PreToolUse (Tool Interception)**: Auto-answer questions during autonomous execution
5. **PermissionRequest (Permission Handling)**: Auto-approve tool permissions during appfix
6. **PostToolUse (Post-Action Context)**: Inject execution context after plan approval or skill completion
7. **SubagentStop (Agent Validation)**: Validate subagent output quality before accepting
8. **PostToolUse (Skill Continuation)**: Continue autonomous loop after skill delegation

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
| `tool_name` | string | **PreToolUse/PostToolUse only**: The tool being called (e.g., "Edit", "ExitPlanMode") |
| `tool_input` | object | **PreToolUse/PostToolUse only**: The tool's input parameters |

**Important**: All field names use `snake_case` (e.g., `tool_name`, not `toolName`). This applies to all hook events including PreToolUse and PostToolUse.

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
            "command": "python3 ~/.claude/hooks/session-snapshot.py",
            "timeout": 5
          },
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

### SessionStart Hook: Auto-Update

**File**: `~/.claude/hooks/auto-update.py`

**Purpose**: Automatically checks for and downloads toolkit updates from GitHub on session start.

**Key features**:
- Rate-limited to once per 24 hours (configurable via `CHECK_INTERVAL_HOURS`)
- Uses `git ls-remote` for fast version check without full fetch
- Uses `git pull --ff-only` to avoid merge conflicts
- Non-blocking on errors (network failures don't break sessions)
- Detects settings.json changes and warns user to restart

**State file**: `~/.claude/toolkit-update-state.json`
```json
{
  "last_check_timestamp": "2026-01-27T10:30:00Z",
  "last_check_result": "up_to_date",
  "local_commit_at_check": "abc1234",
  "remote_commit_at_check": "abc1234",
  "settings_hash_at_session_start": "sha256:abc123...",
  "pending_restart_reason": null,
  "update_history": [...]
}
```

**Disable auto-update**: Set environment variable `CLAUDE_TOOLKIT_AUTO_UPDATE=false`

**Restart requirement**: When settings.json changes in an update, the hook outputs a warning:
```
⚠️ TOOLKIT UPDATED - RESTART REQUIRED ⚠️
...
CRITICAL: settings.json changed in this update.
Hooks are captured at session startup and require restart to reload.
ACTION REQUIRED: Exit this session and start a new one.
```

The hook tracks pending restarts and re-displays the warning on subsequent sessions until the user actually restarts.

### SessionStart Hook: Session Snapshot

**File**: `~/.claude/hooks/session-snapshot.py`

**Purpose**: Captures a snapshot of the git diff state at session start to enable session-specific change detection.

**Why this exists**: Without this, the stop hook would require checkpoints for ANY uncommitted changes, even pre-existing ones from previous sessions. This caused a loop where research-only sessions were blocked because they inherited uncommitted changes.

**How it works**:
1. At session start, computes SHA1 hash of `git diff HEAD -- ":(exclude).claude/"`
2. Saves hash to `.claude/session-snapshot.json`
3. Stop hook compares current hash against saved hash
4. If hashes match → session made no code changes → no checkpoint required
5. If hashes differ → session modified code → checkpoint required

**State file**: `.claude/session-snapshot.json`
```json
{
  "diff_hash_at_start": "a1b2c3d4e5f6",
  "session_started_at": "2026-01-25T10:30:00",
  "session_id": "abc123-def456"
}
```

**Additional behaviors**:
1. **Session guard**: Claims session ownership via `.claude/session-owner.json`, warns if concurrent sessions detected
2. **Expired state cleanup**: Cleans up expired autonomous state files from previous sessions
3. **Worktree garbage collection**: Calls `gc_worktrees(ttl_hours=8)` to clean up stale worktrees from crashed coordinators

### Utility Script: Worktree Manager

**File**: `~/.claude/hooks/worktree-manager.py`

**Purpose**: Provides git worktree isolation for parallel agent operations. Each agent gets its own worktree with a dedicated branch, preventing git operation conflicts during concurrent execution.

**CLI Commands**:
```bash
# Create worktree for an agent
python3 ~/.claude/hooks/worktree-manager.py create <agent-id>

# Cleanup worktree after agent completes
python3 ~/.claude/hooks/worktree-manager.py cleanup <agent-id>

# Merge agent's work back to main branch
python3 ~/.claude/hooks/worktree-manager.py merge <agent-id>

# List all active agent worktrees
python3 ~/.claude/hooks/worktree-manager.py list

# Get worktree path for an agent
python3 ~/.claude/hooks/worktree-manager.py path <agent-id>

# Check if current directory is a worktree
python3 ~/.claude/hooks/worktree-manager.py is-worktree

# Garbage collect stale worktrees (TTL-based)
python3 ~/.claude/hooks/worktree-manager.py gc [ttl_hours] [--dry-run]
```

**Garbage Collection** (`gc_worktrees()`):

Cleans up orphaned worktrees from crashed coordinators:
1. State file entries older than TTL (default: 8 hours)
2. Orphaned directories in `/tmp/claude-worktrees/` not tracked in state
3. Git worktree metadata (via `git worktree prune`)

Called automatically at session start by `session-snapshot.py`.

**State file**: `~/.claude/worktree-state.json`
```json
{
  "worktrees": {
    "agent-123": {
      "path": "/tmp/claude-worktrees/agent-123",
      "branch": "claude-agent/agent-123",
      "main_repo": "/path/to/main/repo",
      "base_commit": "abc1234",
      "created_at": "2026-01-25T10:30:00Z"
    }
  }
}
```

### UserPromptSubmit Hook: Skill State Initializer

**File**: `~/.claude/hooks/skill-state-initializer.py`

**Purpose**: Creates state files for autonomous execution skills (`/appfix`, `/godo`) immediately when the user's prompt matches trigger patterns. This ensures auto-approval hooks activate from the first tool call.

**Coordinator Detection**:

The hook detects whether the session is running in a git worktree (subagent) or main repo (coordinator):

```python
def _detect_worktree_context(cwd: str) -> tuple[bool, str | None, str | None]:
    """Returns: (is_coordinator, agent_id, worktree_path)"""
```

**Production Deployment Permission Detection**:

The hook also scans the user's prompt for production deployment intent. If detected, it pre-populates `allowed_prompts` in the state file, which the `deploy-enforcer.py` hook checks before blocking.

Recognized patterns:
- `deploy to prod/production`
- `push to prod`
- `release to production`
- `/deploy-pipeline ... prod`

Example: `/godo deploy to prod` creates state with:
```json
{
  "allowed_prompts": [{"tool": "Bash", "prompt": "deploy to production"}]
}
```

**State file fields** (`.claude/appfix-state.json` or `.claude/godo-state.json`):
```json
{
  "iteration": 1,
  "started_at": "2026-01-25T10:00:00Z",
  "session_id": "abc123",
  "plan_mode_completed": false,
  "parallel_mode": false,
  "agent_id": null,
  "worktree_path": null,
  "coordinator": true,
  "allowed_prompts": [{"tool": "Bash", "prompt": "deploy to production"}]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `coordinator` | boolean | True if main repo (can deploy), false if worktree |
| `parallel_mode` | boolean | True if running in a worktree |
| `agent_id` | string\|null | Agent ID if in worktree |
| `worktree_path` | string\|null | Worktree path if in worktree |
| `allowed_prompts` | array\|null | Pre-populated permissions from prompt (for deploy-enforcer) |

**Deploy restrictions**: Subagents (`coordinator: false`) should never deploy directly. Only the coordinator agent (in main repo) handles deployments after merging subagent work.

### SessionStart Hook: Read Docs Reminder

Forces Claude to read project documentation before executing any user request. Uses echo with exit code 0 (context injection, non-blocking).

**Key language patterns that drive compliance**:
- `MANDATORY` / `MUST` - imperative, not suggestive
- `DO NOT skip` - explicit prohibition
- `Actually READ the files` - prevents "I'll summarize from memory" shortcuts
- `The user expects...` - frames as user requirement, not system preference

### PostToolUse Hook: Checkpoint Invalidator

**File**: `~/.claude/hooks/checkpoint-invalidator.py`

**Purpose**: Proactively resets stale checkpoint flags immediately after code edits, preventing Claude from working with outdated state.

**Problem this solves**:
1. Deploy at version A → checkpoint: `deployed=true`
2. Test finds error → Claude writes fix → version becomes B
3. WITHOUT this hook: Claude sees `deployed=true`, skips re-deploy
4. WITH this hook: `deployed` is reset to `false` immediately after edit

**Dependency Graph**:
```
linters_pass
     ↓
  deployed
     ↓
┌────┴────┐
↓         ↓
web_testing_done
console_errors_checked
api_testing_done
```

When a field becomes stale, all dependent fields are also invalidated:
- If `linters_pass` is stale → `deployed` is also stale
- If `deployed` is stale → `web_testing_done`, `console_errors_checked`, `api_testing_done` are also stale

**Trigger**: Fires after every `Edit` or `Write` tool use on code files (`.py`, `.ts`, `.tsx`, `.js`, `.jsx`, etc.)

#### Version Format

The `get_code_version()` function returns:

| State | Format | Example |
|-------|--------|---------|
| Clean commit | `{short_hash}` | `abc1234` |
| Uncommitted changes | `{short_hash}-dirty` | `abc1234-dirty` |
| Not a git repo | `unknown` | `unknown` |

**Important**: The dirty indicator is a boolean flag, NOT a content hash. This ensures version stability during development—the version only changes at commit boundaries, not on every file edit. This prevents checkpoint invalidation loops where every edit would change the version and trigger re-verification.

**Output**: Injects a warning message listing invalidated fields:
```
⚠️ CODE CHANGE DETECTED - Checkpoint fields invalidated: deployed, web_testing_done

You edited: src/auth.py
Current version: abc1234-dirty

These fields were reset to false because the code changed since they were set:
  • deployed: now requires re-verification
  • web_testing_done: now requires re-verification

Before stopping, you must:
1. Re-run linters (if linters_pass was reset)
2. Re-deploy (if deployed was reset)
3. Re-test in browser (if web_testing_done was reset)
4. Update checkpoint with new version
```

### PreToolUse Hook: Plan Mode Enforcer

**File**: `~/.claude/hooks/plan-mode-enforcer.py`

**Purpose**: Blocks Edit/Write tools on the first iteration of godo/appfix until plan mode is completed. Ensures Claude explores the codebase before making changes.

**Trigger**: Fires before `Edit` or `Write` tool use during godo/appfix workflows.

**How it works**:
1. Receives PreToolUse event with `tool_name: "Edit"` or `"Write"`
2. Checks if godo or appfix state file exists
3. If first iteration and `plan_mode_completed: false` → blocks the tool
4. If plan files (paths containing `/plans/`) → always allows (for writing implementation plans)
5. If subsequent iteration or plan mode completed → allows the tool

**Configuration**:
```json
"PreToolUse": [
  {
    "matcher": "Edit",
    "hooks": [{"type": "command", "command": "python3 ~/.claude/hooks/plan-mode-enforcer.py", "timeout": 5}]
  },
  {
    "matcher": "Write",
    "hooks": [{"type": "command", "command": "python3 ~/.claude/hooks/plan-mode-enforcer.py", "timeout": 5}]
  }
]
```

**Note**: Matchers must be separate entries (one for "Edit", one for "Write"). The `"Edit|Write"` regex-style syntax does NOT work—matchers use exact string matching, not regex patterns.

**Block message** (when enforcing):
```
PLAN MODE REQUIRED - FIRST ITERATION

1. Call EnterPlanMode
2. Explore codebase architecture, recent commits, configs
3. Write implementation plan to the plan file
4. Call ExitPlanMode

THEN your edit will be allowed.
```

### PostToolUse Hook: Plan Mode Tracker

**File**: `~/.claude/hooks/plan-mode-tracker.py`

**Purpose**: Marks plan mode as completed in godo/appfix state files after ExitPlanMode is called, enabling Edit/Write tools to proceed. Also stores `allowedPrompts` from the plan for permission-based bypasses in other hooks.

**Trigger**: Fires after `ExitPlanMode` tool use during godo/appfix workflows.

**How it works**:
1. Receives PostToolUse event with `tool_name: "ExitPlanMode"`
2. Extracts `allowedPrompts` from `tool_input` (if present)
3. Checks if godo or appfix state file exists (`.claude/godo-state.json` or `.claude/appfix-state.json`)
4. Updates the state file with `plan_mode_completed: true` and `allowed_prompts`
5. The plan-mode-enforcer hook (PreToolUse) then allows Edit/Write tools
6. Other hooks (e.g., deploy-enforcer) can check `allowed_prompts` for permission bypasses

**State file update**:
```json
{
  "started_at": "2026-01-25T10:00:00Z",
  "task": "user's task",
  "iteration": 1,
  "plan_mode_completed": true,  // ← Set by this hook
  "allowed_prompts": [          // ← Stored from ExitPlanMode allowedPrompts
    {"tool": "Bash", "prompt": "deploy to production"}
  ]
}
```

**Why this exists**: The plan-mode-enforcer blocks Edit/Write tools on the first iteration of godo/appfix to ensure Claude explores the codebase before making changes. This hook marks when that exploration is complete. The `allowed_prompts` storage enables other hooks (like deploy-enforcer) to respect permissions explicitly granted by the user in the plan.

### PostToolUse Hook: Skill Continuation Reminder

**File**: `~/.claude/hooks/skill-continuation-reminder.py`

**Purpose**: Reminds Claude to continue the autonomous fix-verify loop after delegating to a skill like `/heavy`.

**Problem this solves**: When `/appfix` delegates to `/heavy` via the Skill tool, after `/heavy` completes, Claude loses context that it's still in an appfix loop and should continue. This hook re-injects that context.

**Trigger**: Fires after `Skill` tool use during godo/appfix workflows.

**How it works**:
1. Receives PostToolUse event with `tool_name: "Skill"`
2. Checks if godo or appfix mode is active via `is_autonomous_mode_active(cwd)`
3. If active, outputs JSON with `hookSpecificOutput.additionalContext` containing continuation instructions
4. If not active, exits silently (no output)

**Configuration**:
```json
"PostToolUse": [
  {
    "matcher": "Skill",
    "hooks": [
      {
        "type": "command",
        "command": "python3 ~/.claude/hooks/skill-continuation-reminder.py",
        "timeout": 5
      }
    ]
  }
]
```

**Injected Context** (when active):
```
APPFIX MODE STILL ACTIVE - SKILL COMPLETED

The skill you invoked has completed. You are STILL in APPFIX autonomous mode.

CONTINUE THE FIX-VERIFY LOOP:
1. Apply any insights from the completed skill
2. Execute the planned changes (Edit tool)
3. Commit and push changes
4. Deploy if required
5. Verify in browser
6. Update completion checkpoint

Do NOT stop here. The fix-verify loop continues until verification is complete.
```

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

The stop validator implements two-phase blocking with execution validation:

**Phase 1 (First Stop)**: Shows full compliance checklist with plan verification and change-specific testing
**Phase 2 (Second Stop)**: Validates execution requirements before allowing stop

```python
#!/usr/bin/env python3
"""
Global Stop Hook Validator

Two-phase stop flow:
1. First stop (stop_hook_active=false): Show FULL compliance checklist, block
2. Second stop (stop_hook_active=true): Validate execution, then allow

Exit codes:
  0 - Allow stop
  2 - Block stop (stderr shown to Claude)
"""
import json
import sys
from pathlib import Path

def check_plan_execution(cwd: str, session_id: str, file_diffs: dict) -> tuple[bool, str]:
    """Validate that plan requirements were actually executed."""
    requirements = parse_plan_requirements(cwd, session_id)
    testing_state = read_testing_state(cwd, session_id)

    # Auto-detect testing requirement from frontend changes
    frontend_testing_required = requires_browser_testing(file_diffs)
    test_required = requirements["test_required"] or frontend_testing_required
    webtest_executed = testing_state.get("webtest_invoked", False)

    if test_required and not webtest_executed:
        return False, "BROWSER TESTING NOT EXECUTED - run /webtest"
    return True, ""

def main():
    input_data = json.load(sys.stdin)
    cwd = input_data.get("cwd", "")
    session_id = input_data.get("session_id", "")
    stop_hook_active = input_data.get("stop_hook_active", False)

    file_diffs = get_git_diff()  # Analyze changed files

    # SECOND STOP: Validate execution before allowing
    if stop_hook_active:
        execution_ok, msg = check_plan_execution(cwd, session_id, file_diffs)
        if not execution_ok:
            print(f"❌ BLOCKED: {msg}", file=sys.stderr)
            sys.exit(2)
        sys.exit(0)  # All requirements met

    # FIRST STOP: Show FULL checklist with plan and change detection
    change_types = detect_change_types(file_diffs)
    plan = get_active_plan(cwd, session_id)
    # ... format checklist with plan verification, testing requirements ...
    print(instructions, file=sys.stderr)
    sys.exit(2)
```

Key features:
- **Plan execution validation**: Checks if deployment/testing from plan was actually done
- **Frontend change detection**: Auto-requires browser testing for .tsx/.jsx changes
- **Testing state tracking**: Reads `.claude/testing-state.json` to verify /webtest ran
- **Second stop enforcement**: Blocks if requirements not met (prevents bypass)
- **Infrastructure bypass**: Skips web testing for infrastructure-only changes

#### Infrastructure Bypass

The stop-validator skips web testing requirements when only infrastructure/toolkit files were changed. This prevents requiring Surf CLI artifacts for changes that have no web UI to test.

**Infrastructure paths excluded from web testing**:
- `config/hooks/` - Hook scripts
- `config/skills/` - Skill definitions
- `config/commands/` - Command definitions
- `.claude/` - Claude configuration
- `prompts/config/` - Toolkit configuration
- `prompts/scripts/` - Toolkit scripts
- `scripts/` - Project scripts

**Logic**:
```python
# has_code_changes() returns False for infrastructure-only changes
if is_autonomous_mode(cwd) and has_app_code:
    # Require Surf CLI artifacts for application changes
    artifact_valid, artifact_errors = validate_web_smoke_artifacts(cwd)
# Infrastructure-only changes: skip web testing requirements
```

This allows hook/skill/script changes to be committed and pushed without requiring browser verification artifacts.

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

### Automated Test Suite

Three levels of automated tests verify hook behavior:

```bash
# Level 1: Pytest subprocess tests (fast, deterministic, no API cost)
cd prompts && python3 -m pytest config/hooks/tests/test_plan_mode_hooks.py -v

# Level 2: Claude headless E2E (real sessions via claude -p, ~$0.05-0.15)
cd prompts && bash scripts/test-e2e-headless.sh

# Level 3: tmux interactive E2E (manual observation with --observe)
cd prompts && bash scripts/test-e2e-tmux.sh --observe
```

**Pytest tests** (`config/hooks/tests/test_plan_mode_hooks.py`) — 24 tests covering:
- `TestPlanModeEnforcer`: `.claude/` artifact exemption, code blocking, plan completion, iteration skip, godo state
- `TestPlanModeTracker`: State updates on ExitPlanMode, field preservation, no-stdout behavior
- `TestSkillStateInitializer`: `/appfix` and `/godo` state creation, natural language triggers
- `TestHookChain`: Full appfix lifecycle (init → enforce → track → allow), auto-approval

**Headless E2E** (`scripts/test-e2e-headless.sh`) — 5 tests using `claude -p --dangerously-skip-permissions`:
- `.claude/` writes allowed during plan enforcement
- Code files blocked before plan mode
- Code files allowed after plan mode
- Iteration > 1 skips enforcement
- No state file = normal passthrough

**tmux E2E** (`scripts/test-e2e-tmux.sh`) — 3 interactive tests:
- `.claude/` artifact write in interactive session
- Code file blocking in interactive session
- Full lifecycle: enforce → plan → allow

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

## Autonomous Execution Hook System

The `/godo` and `/appfix` skills use a coordinated set of hooks to enforce fully autonomous execution. These hooks activate when autonomous mode is detected via:

1. **State file existence** (primary): `.claude/godo-state.json` or `.claude/appfix-state.json` exists in the project
2. **Environment variable** (legacy): `GODO_ACTIVE=true` or `APPFIX_ACTIVE=true`

The `skill-state-initializer.py` hook (UserPromptSubmit) creates these state files automatically when `/godo` or `/appfix` is invoked. State files include a `started_at` timestamp and expire after a configurable TTL (checked by `is_state_expired()` in `_common.py`).

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   AUTONOMOUS EXECUTION HOOK SYSTEM                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  UserPromptSubmit                                                           │
│  └─→ skill-state-initializer.py                                             │
│      └─→ Creates .claude/godo-state.json or .claude/appfix-state.json      │
│      └─→ Sets started_at timestamp for TTL expiry                          │
│                                                                             │
│  PreToolUse(Edit/Write)                                                     │
│  └─→ plan-mode-enforcer.py                                                  │
│      └─→ If autonomous + first iteration: DENY until plan mode completed   │
│      └─→ If not active or plan done: Pass through                          │
│                                                                             │
│  PreToolUse(Bash)                                                           │
│  └─→ deploy-enforcer.py                                                     │
│      └─→ If autonomous + coordinator=false: DENY gh workflow run           │
│      └─→ If production deploy detected: DENY with safety gate              │
│                                                                             │
│  PostToolUse(ExitPlanMode)                                                  │
│  └─→ plan-mode-tracker.py → marks plan mode completed in state file        │
│  └─→ plan-execution-reminder.py → injects fix-verify loop instructions     │
│                                                                             │
│  PostToolUse(Edit/Write)                                                    │
│  └─→ checkpoint-invalidator.py → resets stale checkpoint flags             │
│  └─→ checkpoint-write-validator.py → warns on claims without evidence      │
│                                                                             │
│  PostToolUse(Bash)                                                          │
│  └─→ bash-version-tracker.py → invalidates fields on version change        │
│                                                                             │
│  PostToolUse(Skill)                                                         │
│  └─→ skill-continuation-reminder.py → continues loop after skill           │
│                                                                             │
│  PermissionRequest(*)                                                       │
│  └─→ appfix-auto-approve.py                                                │
│      └─→ If autonomous mode active: Auto-approve ALL tools                 │
│      └─→ If not active: Silent pass-through (normal approval)              │
│                                                                             │
│  Stop                                                                       │
│  └─→ stop-validator.py                                                      │
│      └─→ Validates completion checkpoint (boolean self-report)             │
│      └─→ Cross-validates web smoke artifacts and deploy artifacts          │
│      └─→ Cascade invalidation on version mismatch                          │
│      └─→ Blocks if is_job_complete=false or what_remains is non-empty      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### PreToolUse Hook: Auto-Approve All Tools (Primary)

**File**: `~/.claude/hooks/pretooluse-auto-approve.py`

**Purpose**: Auto-approve ALL tools during godo/appfix by intercepting at the PreToolUse stage, BEFORE the permission system decides whether to show a dialog.

**Why PreToolUse instead of PermissionRequest?**

`PermissionRequest` hooks only fire when Claude Code would show a permission dialog. However, after ExitPlanMode grants `allowedPrompts`, many tools are pre-approved and NO dialog is shown - so the PermissionRequest hook never fires. After context compaction, the in-memory `allowedPrompts` are lost, requiring manual approval again.

`PreToolUse` hooks fire for EVERY tool call, allowing us to bypass the permission system entirely by returning `permissionDecision: "allow"`. This ensures auto-approval works both before AND after context compaction.

**Detection**: Uses `is_autonomous_mode_active()` from `_common.py`, which checks for state files with TTL validation.

**Behavior**:
1. Reads stdin JSON for `cwd` and `tool_name`
2. Checks if godo or appfix state file exists and is not expired
3. If active: Returns `permissionDecision: "allow"` to bypass permission system
4. If not active: Silent pass-through (exit 0, no output)

**Hook Output Schema**:
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "permissionDecisionReason": "Auto-approved by appfix mode"
  }
}
```

**Configuration** (wildcard matcher — matches all tools):
```json
"PreToolUse": [
  {
    "matcher": "*",
    "hooks": [
      {
        "type": "command",
        "command": "python3 ~/.claude/hooks/pretooluse-auto-approve.py",
        "timeout": 5
      }
    ]
  }
]
```

### PermissionRequest Hook: Auto-Approve Fallback

**File**: `~/.claude/hooks/appfix-auto-approve.py`

**Purpose**: Fallback auto-approval for any permission dialogs that still appear (defense in depth).

**Note**: This hook is largely superseded by the PreToolUse hook above, but remains as a backup for edge cases where a permission dialog is still shown.

**Configuration** (catch-all matcher — no `matcher` field):
```json
"PermissionRequest": [
  {
    "hooks": [
      {
        "type": "command",
        "command": "python3 ~/.claude/hooks/appfix-auto-approve.py",
        "timeout": 5
      }
    ]
  }
]
```

### PreToolUse Hook: Plan Mode Enforcement

**File**: `~/.claude/hooks/plan-mode-enforcer.py`

**Purpose**: Block Edit/Write tools on the first iteration of godo/appfix until plan mode is completed. This ensures Claude explores the codebase before making changes.

**Behavior**:
1. Checks if autonomous mode is active
2. If plan mode not yet completed (tracked by `plan-mode-tracker.py`): Returns `permissionDecision: "deny"` with message instructing Claude to enter plan mode first
3. After plan mode completed: Silent pass-through

**Configuration**:
```json
"PreToolUse": [
  {
    "matcher": "Edit",
    "hooks": [{ "type": "command", "command": "python3 ~/.claude/hooks/plan-mode-enforcer.py", "timeout": 5 }]
  },
  {
    "matcher": "Write",
    "hooks": [{ "type": "command", "command": "python3 ~/.claude/hooks/plan-mode-enforcer.py", "timeout": 5 }]
  }
]
```

### PreToolUse Hook: Deploy Enforcement

**File**: `~/.claude/hooks/deploy-enforcer.py`

**Purpose**: Prevents subagents from deploying and blocks production deploys in autonomous mode, unless explicitly permitted in the plan.

**Behavior**:
1. Parses Bash command from stdin JSON
2. **Subagent blocking**: If autonomous mode active AND state has `coordinator: false`, blocks `gh workflow run` commands
3. **Production gate**: If command targets `environment=production`:
   - Checks if production deployment was explicitly allowed via `allowedPrompts` in the plan
   - If allowed → permits the command
   - If not allowed → blocks with safety message

**Plan-Based Permission Bypass**:

When ExitPlanMode is called with `allowedPrompts`, the `plan-mode-tracker.py` hook stores these in the state file. The deploy-enforcer then checks for Bash permissions mentioning production:

```json
// In ExitPlanMode call:
{
  "allowedPrompts": [
    {"tool": "Bash", "prompt": "deploy to production"}
  ]
}

// Stored in state file by plan-mode-tracker.py:
{
  "allowed_prompts": [
    {"tool": "Bash", "prompt": "deploy to production"}
  ]
}
```

Permission patterns recognized: `prod`, `production`, `deploy to prod`, `push to prod`.

**Configuration**:
```json
"PreToolUse": [
  {
    "matcher": "Bash",
    "hooks": [{ "type": "command", "command": "python3 ~/.claude/hooks/deploy-enforcer.py", "timeout": 5 }]
  }
]
```

### Stop Hook: Completion Checkpoint Validation

**File**: `~/.claude/hooks/stop-validator.py`

**Purpose**: Prevent Claude from stopping until the job is actually done. Validates a deterministic boolean checkpoint.

**Checkpoint Schema** (`.claude/completion-checkpoint.json`):
```json
{
  "self_report": {
    "is_job_complete": true,
    "code_changes_made": true,
    "linters_pass": true,
    "deployed": true,
    "web_testing_done": true,
    "console_errors_checked": true,
    "api_testing_done": false,
    "docs_updated": true
  },
  "reflection": {
    "what_was_done": "Fixed CORS config, deployed, verified login works",
    "what_remains": "none"
  },
  "evidence": {
    "urls_tested": ["https://app.example.com/dashboard"],
    "console_clean": true
  }
}
```

**Blocking Conditions**:
- `is_job_complete: false` → BLOCKED
- `what_remains` is non-empty → BLOCKED
- Version-dependent fields stale (field version != current git version) → cascade reset + BLOCKED
- Web smoke artifacts missing/failed (cross-validation) → reset `web_testing_done` + BLOCKED
- Deployment artifacts missing/failed (cross-validation) → reset `deployed` + cascade

**Cascade Invalidation**: When a field is reset, all downstream fields are also reset:
- `linters_pass` → resets `deployed` → resets `web_testing_done`, `console_errors_checked`, `api_testing_done`
- `deployed` → resets `web_testing_done`, `console_errors_checked`, `api_testing_done`

### PostToolUse Hooks: Version Tracking and Checkpoint Management

**bash-version-tracker.py** (PostToolUse/Bash): Detects version-changing commands (git commit, az CLI, gh workflow run) and invalidates stale checkpoint fields. Prevents the scenario where code changes go undetected.

**checkpoint-invalidator.py** (PostToolUse/Edit/Write): Proactively resets stale checkpoint flags when code is edited, before the stop hook checks. Prevents false checkpoint claims.

**checkpoint-write-validator.py** (PostToolUse/Write): Warns (does not block) when writing checkpoint claims without evidence. Catches issues early before the stop hook rejects them.

**plan-execution-reminder.py** (PostToolUse/ExitPlanMode): Injects aggressive autonomous execution context after plan mode completes — the fix-verify loop instructions.

**plan-mode-tracker.py** (PostToolUse/ExitPlanMode): Marks plan mode as completed in the state file so `plan-mode-enforcer.py` stops blocking Edit/Write.

**skill-continuation-reminder.py** (PostToolUse/Skill): After a skill (like `/heavy`) completes within a godo/appfix loop, reminds Claude to continue the autonomous loop.

### Testing the Hooks

```bash
# Test auto-approve with state file
mkdir -p /tmp/test-project/.claude
echo '{"iteration": 1, "started_at": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > /tmp/test-project/.claude/appfix-state.json
echo '{"tool_name":"Bash","cwd":"/tmp/test-project"}' | python3 ~/.claude/hooks/appfix-auto-approve.py
# Expected: JSON with decision.behavior: "allow"

# Test auto-approve without state (should pass through)
rm -rf /tmp/test-project/.claude
echo '{"tool_name":"Bash","cwd":"/tmp/test-project"}' | python3 ~/.claude/hooks/appfix-auto-approve.py
# Expected: No output (pass through)

# Test deploy-enforcer blocking subagent deploy
mkdir -p /tmp/test-project/.claude
echo '{"iteration": 1, "started_at": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'", "coordinator": false}' > /tmp/test-project/.claude/godo-state.json
echo '{"tool_name":"Bash","tool_input":{"command":"gh workflow run deploy.yml"},"cwd":"/tmp/test-project"}' | python3 ~/.claude/hooks/deploy-enforcer.py
# Expected: JSON with permissionDecision: "deny"

# Test plan-mode-enforcer blocking Edit before plan mode
mkdir -p /tmp/test-project/.claude
echo '{"iteration": 1, "started_at": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'", "plan_mode_completed": false}' > /tmp/test-project/.claude/godo-state.json
echo '{"tool_name":"Edit","tool_input":{"file_path":"/tmp/test.py"},"cwd":"/tmp/test-project"}' | python3 ~/.claude/hooks/plan-mode-enforcer.py
# Expected: JSON with permissionDecision: "deny"

# Cleanup
rm -rf /tmp/test-project/.claude
```

---

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

For more details, see the official Claude Code documentation on Tasks.

## Related Documentation

- [Claude Code Hooks Reference](https://code.claude.com/docs/en/hooks.md) - Official documentation
- [Commands Reference](./commands.md) - Custom slash commands
- [Skills Reference](./skills.md) - Domain-specific knowledge injection
- [Config Files](../../config/) - Actual hook/skill/command files for installation
- Project CLAUDE.md - Per-project coding standards
- Project .claude/MEMORIES.md - Per-project session memories
