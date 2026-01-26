# Claude Code Custom Commands

Reference documentation for creating and using custom slash commands in Claude Code.

## Overview

Custom slash commands are markdown files that define frequently used prompts. They're stored in special directories and invoked using the `/` prefix.

```
┌─────────────────────────────────────────────────────────────────┐
│                     Command Invocation Flow                      │
├─────────────────────────────────────────────────────────────────┤
│  User types /command → Claude loads command.md → Executes prompt │
└─────────────────────────────────────────────────────────────────┘
```

## Command Locations

### Global Commands (All Projects)

```
~/.claude/commands/
├── webtest.md        → /webtest
├── review.md         → /review
└── deploy.md         → /deploy
```

### Project Commands (Team Shared)

```
<project-root>/.claude/commands/
├── fix-issue.md      → /fix-issue
└── frontend/
    └── test.md       → /test (project:frontend)
```

**Priority**: Project commands override global commands with the same name.

## Basic Syntax

The filename (without `.md`) becomes the command name:

```bash
# Create a simple command
mkdir -p ~/.claude/commands
echo "Review this code for security vulnerabilities:" > ~/.claude/commands/security-review.md
```

Usage: `/security-review`

## Frontmatter Configuration

Add metadata using YAML frontmatter:

```markdown
---
description: Test new features using browser automation
allowed-tools: Bash(npm run:*), Bash(playwright:*)
argument-hint: [feature-name]
model: claude-3-5-haiku-20241022
---

Your prompt here with $ARGUMENTS placeholder.
```

### Available Frontmatter Fields

| Field | Purpose | Default |
|-------|---------|---------|
| `description` | Brief description (shown in `/help`) | First line of file |
| `allowed-tools` | Tools the command can use | Inherits from conversation |
| `argument-hint` | Expected arguments for auto-complete | None |
| `model` | Specific Claude model to use | Inherits from conversation |
| `disable-model-invocation` | Prevent SlashCommand tool from calling this | false |

## Arguments

### All Arguments: `$ARGUMENTS`

```markdown
Fix issue #$ARGUMENTS following our coding standards.
```

Usage: `/fix-issue 123` → `$ARGUMENTS` becomes `"123"`

### Positional Arguments: `$1`, `$2`, etc.

```markdown
Review PR #$1 with priority $2 and assign to $3.
```

Usage: `/review-pr 456 high alice` → `$1="456"`, `$2="high"`, `$3="alice"`

## Advanced Features

### Bash Command Execution

Include bash output using the `!` prefix:

```markdown
Current branch: !`git branch --show-current`
Current diff: !`git diff HEAD`

Create a commit based on the above changes.
```

### File References

Include file contents using the `@` prefix:

```markdown
Review the implementation in @src/utils/helpers.js
Compare @src/old-version.js with @src/new-version.js
```

### Extended Thinking

Enable thinking mode by including the keyword:

```markdown
Use extended thinking to thoroughly analyze this architecture.
```

## Current Global Commands

| Command | Description |
|---------|-------------|
| `/QA` | Exhaustive architecture, scalability, and maintainability audit |
| `/deslop` | Detect and remove 25 patterns of AI-generated code slop |
| `/docupdate` | Documentation gap analysis and staleness detection |
| `/webtest` | Test features via Surf CLI (autonomous) or Chrome MCP (interactive) |
| `/interview` | Clarify plan details via AskUserQuestion before implementation |
| `/weboptimizer` | Performance benchmarks and optimization for Next.js + FastAPI |
| `/config-audit` | Environment variable analysis and fallback pattern detection |
| `/mobiletest` | Run Maestro E2E tests with failure diagnosis and fix suggestions |
| `/mobileaudit` | Vision-based UI/design audit via Maestro screenshots |
| `/designimprove` | Recursively improve web UI via screenshot grading and targeted fixes |
| `/uximprove` | Recursively improve UX via usability analysis and targeted fixes |

## Commands vs Skills vs Hooks

| Aspect | Commands | Skills | Hooks |
|--------|----------|--------|-------|
| **Trigger** | Manual (`/command`) | Automatic (context-based) | Lifecycle events |
| **Structure** | Single `.md` file | Directory with multiple files | Shell command or script |
| **Scope** | Quick prompts | Domain expertise | Session enforcement |
| **Use Case** | Frequent actions | Complex workflows | Compliance checks |

**Use commands for:**
- Frequently used prompts
- Quick shortcuts for common tasks
- Simple parameterized actions

**Use skills for:**
- Complex domain knowledge
- Multi-file reference documentation
- Patterns requiring examples and context

**Use hooks for:**
- Session startup/stop enforcement
- Automatic compliance checks
- Context injection

## Creating Custom Commands

### Step 1: Create the File

```bash
mkdir -p ~/.claude/commands
cat > ~/.claude/commands/my-command.md << 'EOF'
---
description: Brief description for /help
argument-hint: [arg1] [arg2]
---

Your prompt here. Use $ARGUMENTS or $1, $2 for parameters.
EOF
```

### Step 2: Test

```
> /my-command arg1 arg2
```

### Step 3: Verify in Help

```
> /help
```

Your command should appear with "(user)" suffix.

## Namespacing with Subdirectories

Organize related commands in subdirectories:

```
.claude/commands/
├── review.md                → /review
├── frontend/
│   ├── component.md        → /component (project:frontend)
│   └── test.md             → /test (project:frontend)
└── backend/
    └── test.md             → /test (project:backend)
```

## Best Practices

1. **Use descriptive filenames** for clarity
2. **Add frontmatter descriptions** so commands appear helpful in `/help`
3. **Commit project commands to git** to share with team
4. **Keep commands focused** - one task per command
5. **Test with arguments** to ensure placeholders work correctly
6. **Use subdirectories** to organize related commands

## Related Documentation

- [Hooks Reference](./hooks.md) - Lifecycle event handlers
- [Skills Reference](./skills.md) - Domain-specific knowledge injection
- [Config Files](../../config/) - Actual command/hook/skill files for installation
- [Official Commands Documentation](https://code.claude.com/docs/en/slash-commands) - Anthropic reference
