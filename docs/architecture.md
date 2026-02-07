# Architecture Overview

This document explains how Claude Code's extension mechanisms work and how this toolkit leverages them.

## The Three Extension Mechanisms

Claude Code supports three ways to extend its behavior:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Claude Code Extensions                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   COMMANDS                    SKILLS                     HOOKS               │
│   ─────────                   ──────                     ─────               │
│   /slash-invoked              Auto-triggered             Lifecycle events    │
│                                                                              │
│   ┌──────────────┐           ┌──────────────┐           ┌──────────────┐    │
│   │ QA.md        │           │ SKILL.md     │           │ settings.json│    │
│   │ deslop.md    │           │ references/  │           │   → hooks:   │    │
│   │ webtest.md   │           │ examples/    │           │   SessionStart│   │
│   │ ...          │           │              │           │   Stop        │   │
│   └──────────────┘           └──────────────┘           │   UserPrompt │    │
│         │                          │                    └──────────────┘    │
│         │                          │                          │              │
│         ▼                          ▼                          ▼              │
│   User types /cmd            Claude detects            Event fires           │
│   → loads markdown           keyword match             → runs command        │
│   → executes workflow        → loads skill             → exit code decides   │
│                              → applies knowledge                             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## File Locations

Claude Code looks for extensions in `~/.claude/` (global) and `.claude/` (project):

```
~/.claude/                          # Global (all projects)
├── settings.json                   # Global settings + hooks
├── commands/                       # Global commands
│   └── *.md
├── skills/                         # Global skills
│   └── skill-name/
│       └── SKILL.md
└── hooks/                          # Hook scripts (referenced in settings.json)
    └── *.py

<project>/.claude/                  # Project-specific (overrides global)
├── settings.json                   # Project settings
├── commands/                       # Project commands
└── skills/                         # Project skills
```

**Precedence**: Project config overrides global config for the same keys.

## Execution Flows

### Command Execution

```
User types: /QA

    │
    ▼
┌─────────────────────────────────────────┐
│ Claude Code loads ~/.claude/commands/QA.md │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ Parses YAML frontmatter:                │
│   - description                         │
│   - allowed-tools (optional)            │
│   - model (optional)                    │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ Markdown body becomes the prompt        │
│ $ARGUMENTS replaced with user input     │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ Claude executes the structured workflow │
│ (plan mode, agents, output format)      │
└─────────────────────────────────────────┘
```

### Skill Activation

```
User prompt: "Build a virtualized data table with sorting"

    │
    ▼
┌─────────────────────────────────────────┐
│ Claude analyzes prompt keywords         │
│ Matches: "data table", "virtualized"    │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ Scans ~/.claude/skills/*/SKILL.md       │
│ Checks each skill's description field   │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ Match found: nextjs-tanstack-stack      │
│ "...TanStack Table, virtualization..."  │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ Loads SKILL.md content as context       │
│ May also load references/, examples/    │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ Claude applies skill knowledge to task  │
└─────────────────────────────────────────┘
```

### Hook Execution

```
Session starts (or user sends prompt, or Claude tries to stop)

    │
    ▼
┌─────────────────────────────────────────┐
│ Claude Code checks settings.json hooks  │
│ Finds matching hook for event type      │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ Runs hook command with JSON on stdin:   │
│ {                                       │
│   "message": "...",                     │
│   "stop_hook_active": false             │
│ }                                       │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ Hook script processes, returns:         │
│   - exit 0 → allow action               │
│   - exit 2 → block, stderr to Claude    │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ Claude sees hook feedback               │
│ Responds accordingly                    │
└─────────────────────────────────────────┘
```

## Hook Types in Detail

### SessionStart Hook

**Purpose**: Force Claude to read project documentation before starting work.

**Configuration** (settings.json):
```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "echo 'MANDATORY: Read docs/index.md, CLAUDE.md...'",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

**Matchers** (optional):
- `startup` — Fresh session start
- `resume` — Resuming previous context
- `clear` — After /clear command
- `compact` — After context compaction

### Stop Hook

**Purpose**: Ensure compliance checks before Claude stops working.

The stop-validator.py hook:
1. Receives JSON input with `stop_hook_active` flag
2. If `stop_hook_active: false` (first stop attempt):
   - Scans `git diff` for change types (env vars, auth, links, etc.)
   - Outputs checklist to stderr
   - Returns exit code 2 (block)
3. If `stop_hook_active: true` (second stop attempt):
   - Auto-captures checkpoint as memory event to `~/.claude/memory/{project-hash}/events/`
   - Returns exit code 0 (allow)

**Loop Prevention**: The `stop_hook_active` flag prevents infinite loops:
```
Claude stops → Hook blocks → Claude addresses → Claude stops → Hook allows
                  ↑                                              ↑
           stop_hook_active=false                    stop_hook_active=true
```

### UserPromptSubmit Hooks

**Purpose**: React to each user prompt. Multiple hooks can fire on the same event.

This toolkit includes two UserPromptSubmit hooks:

#### Skill State Management

**Purpose**: Skills now create their own state files at activation. The unified state file is `.claude/autonomous-state.json` with a `mode` field (melt, repair, burndown, improve, episode).

**Behavior**:
1. When a skill is activated (e.g., `/melt`, `/build`, `/appfix`, `/repair`), the skill itself creates `.claude/autonomous-state.json`
2. The `mode` field indicates the active skill mode
3. No separate hook is needed — the previous `skill-state-initializer.py` hook has been removed

#### Documentation Trigger Hook (read-docs-trigger.py)

**Purpose**: Triggers deep documentation reading when user says "read the docs".

**Behavior**:
1. Checks if "read the docs" appears in user message
2. If found, outputs reminder to read docs/index.md and follow relevant links
3. Returns exit code 0 (non-blocking)

**Usage**: Include "read the docs" anywhere in your prompt:
- "read the docs and implement the new API endpoint"
- "I need you to read the docs before refactoring this"

> **Note**: Status file hooks were removed in January 2025. Anthropic's native Tasks feature now handles session tracking. See [concepts/hooks.md](concepts/hooks.md#tasks-deprecation-note) for details.

## How Change Detection Works

The stop-validator.py uses pattern matching on `git diff`:

```python
CHANGE_PATTERNS = {
    "env_var": {
        "patterns": [r"NEXT_PUBLIC_", r"process\.env\.", r"\.env"],
        "tests": ["Grep for localhost fallbacks", "Test with production config"]
    },
    "auth": {
        "patterns": [r"clearToken", r"logout", r"useAuth"],
        "tests": ["Trace token clearing paths", "Test 401 cascade"]
    },
    # ... more patterns
}
```

When you modify code containing these patterns, the stop hook shows relevant testing requirements:

```
⚠️  ENV VAR CHANGES DETECTED:
   - Grep for fallback patterns: || 'http://localhost'
   - Test with production config: NEXT_PUBLIC_API_BASE='' npm run dev
```

## Configuration Reference

### settings.json Structure

```json
{
  "env": {
    "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "64000",
    "MAX_THINKING_TOKENS": "31999"
  },
  "alwaysThinkingEnabled": true,
  "hooks": {
    "SessionStart": [...],
    "Stop": [...],
    "UserPromptSubmit": [...]
  }
}
```

### Command Frontmatter

```yaml
---
description: Brief description for /help
allowed-tools: Read, Grep, Glob  # Optional: restrict tools
argument-hint: <file-path>       # Optional: usage hint
model: opus                      # Optional: force specific model
---
```

### Skill SKILL.md

```yaml
---
name: skill-name
description: Triggers when user asks about X, Y, Z
---

## Content

[Knowledge Claude should apply]
```

## Best Practices

### For Commands
- Use structured output formats (tables, code blocks)
- Include completeness checklists
- Leverage plan mode for complex audits
- Keep prompts focused on one task

### For Skills
- Write clear trigger descriptions
- Include practical examples
- Organize with references/ for deep dives
- Test that keywords actually trigger the skill

### For Hooks
- Use exit code 0 for success/allow
- Use exit code 2 for block (stderr shown to Claude)
- Handle JSON parse errors gracefully
- Include loop prevention for Stop hooks

## Related Documentation

- [concepts/commands.md](concepts/commands.md) — Command deep dive
- [concepts/skills.md](concepts/skills.md) — Skill deep dive
- [concepts/hooks.md](concepts/hooks.md) — Hook deep dive
- [guides/customization.md](guides/customization.md) — Create your own
