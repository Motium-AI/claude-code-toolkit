# Customization Guide

Learn how to create your own commands, skills, and hooks.

## Creating Custom Commands

Commands are markdown files with YAML frontmatter that define structured workflows.

### Basic Command

Create a file in `~/.claude/commands/my-command.md`:

```markdown
---
description: Brief description shown in /help
---

Your prompt instructions here. Claude will execute these when the user runs /my-command.

Be specific about:
1. What to analyze
2. How to format output
3. What to include/exclude
```

### With Arguments

Commands can accept arguments via `$ARGUMENTS` or positional `$1`, `$2`:

```markdown
---
description: Analyze a specific file
argument-hint: <file-path>
---

Analyze the file at $ARGUMENTS for:
1. Code quality issues
2. Security concerns
3. Performance problems

Output as a markdown table.
```

Usage: `/my-command src/auth/login.ts`

### Restricting Tools

Limit which tools the command can use:

```markdown
---
description: Read-only analysis
allowed-tools: Read, Grep, Glob
---

Analyze the codebase. Do NOT make any changes.
```

### Forcing a Model

Use a specific model for the command:

```markdown
---
description: Complex analysis requiring Opus
model: opus
---

Perform deep architectural analysis...
```

### Structured Workflow Example

Commands can define complex multi-phase workflows:

```markdown
---
description: Exhaustive code audit
---

## Execution Strategy

**Phase 1: Exploration**
Use plan mode. Launch up to 3 parallel agents:
- Agent 1: Find files > 300 lines
- Agent 2: Map import graph
- Agent 3: Catalog error handling patterns

**Phase 2: Synthesis**
Cross-reference findings. Group related issues.

**Phase 3: Report**
Output format:

### Finding #N
- **File**: path:line
- **Issue**: description
- **Severity**: Critical | High | Medium | Low
- **Fix**: suggested approach
```

## Creating Custom Skills

Skills provide domain expertise that Claude draws on when relevant keywords appear.

### Basic Skill

Create a directory `~/.claude/skills/my-skill/` with a `SKILL.md` file:

```markdown
---
name: my-skill
description: Expertise in [domain]. Use when building [triggers], working with [keywords].
---

## Overview

[Brief introduction to the domain]

## Core Patterns

### Pattern 1: [Name]

[Explanation and example]

```code
// Example implementation
```

### Pattern 2: [Name]

[Explanation and example]

## Best Practices

- [Practice 1]
- [Practice 2]

## Common Pitfalls

- [Pitfall 1]: [How to avoid]
- [Pitfall 2]: [How to avoid]
```

### Skill with References

For complex domains, organize with subdirectories:

```
my-skill/
├── SKILL.md              # Main skill content
├── references/           # Deep-dive documentation
│   ├── pattern-a.md
│   └── pattern-b.md
└── examples/             # Working code examples
    ├── basic.py
    └── advanced.py
```

In SKILL.md, reference these:

```markdown
For advanced patterns, see [references/pattern-a.md](references/pattern-a.md).

Working examples are in the `examples/` directory.
```

### Trigger Description Best Practices

The `description` field in frontmatter is crucial — it determines when Claude activates the skill.

**Good**:
```yaml
description: Master Next.js App Router patterns. Use when building server components, client components, data fetching with TanStack Query, or implementing virtualized tables.
```

**Bad**:
```yaml
description: Frontend development skill.
```

Include:
- Specific technologies (Next.js, TanStack, etc.)
- Use cases ("building server components")
- Keywords users might say ("virtualized tables")

## Creating Custom Hooks

Hooks are scripts that run at lifecycle events and can inject context or block actions.

### Basic Hook Script

Create `~/.claude/hooks/my-hook.py`:

```python
#!/usr/bin/env python3
"""
My custom hook.

Exit codes:
  0 - Allow action / success
  2 - Block action (stderr shown to Claude)
"""
import json
import sys

def main():
    # Read JSON input from stdin
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)  # Allow on parse error

    message = input_data.get("message", "")

    # Your logic here
    if "dangerous" in message.lower():
        print("Warning: Detected dangerous keyword!", file=sys.stderr)
        sys.exit(2)  # Block

    # Allow by default
    sys.exit(0)

if __name__ == "__main__":
    main()
```

Make it executable:
```bash
chmod +x ~/.claude/hooks/my-hook.py
```

### Register Hook in settings.json

> **Important**: Toolkit hooks are registered globally in `~/.claude/settings.json`. Do NOT re-register them in project-level `.claude/settings.json` — Claude Code runs hooks from both files, and path variations defeat dedup, causing double execution. See [Hooks: Global vs Project Settings](../concepts/hooks.md#global-vs-project-settings--the-settings-contract).

Add to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/hooks/my-hook.py",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

### Hook Event Types

| Event | When | Input JSON | Common Uses |
|-------|------|------------|-------------|
| `SessionStart` | Session starts/resumes | `{"prompt": "..."}` | Inject context, force doc reading |
| `Stop` | Claude tries to stop | `{"stop_hook_active": bool}` | Compliance checks, commit reminders |
| `UserPromptSubmit` | Each user message | `{"message": "...", "prompt": "..."}` | Suggest skills, validate input |

### SessionStart Matchers

Target specific session start types:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup",  // Only fresh starts
        "hooks": [...]
      },
      {
        "matcher": "resume",   // Only resumes
        "hooks": [...]
      }
    ]
  }
}
```

Matchers: `startup`, `resume`, `clear`, `compact`

### Stop Hook with Loop Prevention

Critical for Stop hooks — prevent infinite blocking:

```python
def main():
    input_data = json.load(sys.stdin)

    # If we already blocked once, allow stop
    if input_data.get("stop_hook_active", False):
        sys.exit(0)

    # First stop attempt — block with instructions
    print("Complete these checks before stopping:", file=sys.stderr)
    print("1. Run tests", file=sys.stderr)
    print("2. Update docs", file=sys.stderr)
    sys.exit(2)
```

### Context Injection Hook

SessionStart hooks can inject context:

```python
#!/usr/bin/env python3
import sys

# This output goes to Claude as context
print("IMPORTANT: This project uses custom linting rules.")
print("Always run `npm run lint` before committing.")
print("See docs/linting.md for details.")

sys.exit(0)  # exit 0 = success, output shown to Claude
```

## Testing Your Customizations

### Test a Command

```bash
claude
> /my-command
```

### Test a Skill Trigger

```bash
claude
> Build a [keywords from your skill description]
# Claude should apply your skill
```

### Test a Hook

```bash
# Test hook script directly
echo '{"message": "test input"}' | python3 ~/.claude/hooks/my-hook.py
echo "Exit code: $?"
```

## Debugging

### Command Not Found

```bash
# Verify file exists and has correct extension
ls -la ~/.claude/commands/
# Should show your-command.md
```

### Skill Not Triggering

1. Check description has relevant keywords
2. Test with explicit keywords from description
3. Verify SKILL.md exists in skill directory

### Hook Not Running

```bash
# Verify settings.json syntax
python3 -m json.tool ~/.claude/settings.json

# Check hook is executable
ls -la ~/.claude/hooks/my-hook.py

# Test hook directly
echo '{}' | python3 ~/.claude/hooks/my-hook.py
```

### Hook Blocking When It Shouldn't

- Check exit codes (0 = allow, 2 = block)
- Add logging to debug: `print("debug", file=sys.stderr)`
- Verify JSON parsing handles errors gracefully

## Examples

See the `examples/` directory for:
- `minimal-setup/` — Just the essentials (settings + stop hook)
- `standalone-prompts/` — Individual audit prompts you can copy/adapt

## Related

- [docs/architecture.md](../architecture.md) — How it all fits together
- [docs/concepts/commands.md](../concepts/commands.md) — Command reference
- [docs/concepts/skills.md](../concepts/skills.md) — Skill reference
- [docs/concepts/hooks.md](../concepts/hooks.md) — Hook reference
