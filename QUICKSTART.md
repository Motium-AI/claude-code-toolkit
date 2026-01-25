# Quick Start Guide

Get up and running with Claude Code Toolkit in 5 minutes.

## Prerequisites

- [Claude Code CLI](https://claude.ai/code) installed
- Git installed
- macOS or Linux (Windows WSL works too)

## Step 1: Clone the Repository

```bash
git clone https://github.com/Motium-AI/claude-code-toolkit.git
cd claude-code-toolkit
```

## Step 2: Run the Installer

```bash
./scripts/install.sh
```

This will:
1. Back up your existing `~/.claude/` directory (if any) to `~/.claude.backup.TIMESTAMP`
2. Create symlinks from `~/.claude/` to this repository
3. Make hook scripts executable

**Manual Installation** (if you prefer):
```bash
# Back up existing config
[ -d ~/.claude ] && mv ~/.claude ~/.claude.backup.$(date +%s)

# Create symlinks
mkdir -p ~/.claude
ln -s "$(pwd)/config/settings.json" ~/.claude/settings.json
ln -s "$(pwd)/config/commands" ~/.claude/commands
ln -s "$(pwd)/config/hooks" ~/.claude/hooks
ln -s "$(pwd)/config/skills" ~/.claude/skills

# Make hooks executable
chmod +x config/hooks/*.py
```

## Step 3: Verify Installation

Start Claude Code:
```bash
claude
```

You should see a message like:
```
SessionStart:startup hook success: MANDATORY: Before executing ANY user request...
```

This confirms the SessionStart hook is working.

## Step 4: Try Your First Command

In Claude Code, run:
```
/qa
```

This triggers the exhaustive codebase audit. Claude will:
1. Enter plan mode
2. Launch parallel exploration agents
3. Analyze architecture, coupling, complexity
4. Generate a detailed report

## Step 5: Explore What's Available

### List All Commands
In Claude Code:
```
/help
```

Or check `config/commands/` for all available commands.

### Trigger a Skill
Skills activate automatically. Try prompts like:
- "Build a data table with sorting and filtering" → triggers `nextjs-tanstack-stack`
- "Write an async web scraper" → triggers `async-python-patterns`
- "Create a login form" → triggers `webapp-testing` for testing

### Test the Stop Hook
Make some code changes, then try to stop Claude. You'll see:
```
Stop hook feedback: Before stopping, complete these checks:

1. CLAUDE.md COMPLIANCE (if code written)...
2. DOCUMENTATION (if code written)...
3. UPDATE PROJECT .claude/MEMORIES.md...
4. CHANGE-SPECIFIC TESTING REQUIRED...
5. COMMIT AND PUSH...
```

The hook detects what types of changes you made (auth, env vars, API routes, etc.) and shows relevant testing requirements.

## What's Next?

- **Deep dive into concepts**: Read [docs/concepts/](docs/concepts/) for how commands, skills, and hooks work
- **Customize**: Create your own commands and skills with [docs/guides/customization.md](docs/guides/customization.md)
- **Understand the architecture**: See [docs/architecture.md](docs/architecture.md) for how everything fits together

## Troubleshooting

### "Hook not found" or "Command not found"
Verify symlinks are correct:
```bash
ls -la ~/.claude/
# Should show symlinks pointing to this repo
```

### "Permission denied" on hooks
Make hooks executable:
```bash
chmod +x ~/.claude/hooks/*.py
```

### Hook errors in Claude output
Check the hook script directly:
```bash
echo '{"stop_hook_active": false}' | python3 ~/.claude/hooks/stop-validator.py
```

### SessionStart hook not firing
Verify `~/.claude/settings.json` exists and contains the `hooks` section:
```bash
cat ~/.claude/settings.json | grep -A5 "SessionStart"
```

## Uninstall

To remove the toolkit:
```bash
rm -rf ~/.claude
# Restore backup if you had one
mv ~/.claude.backup.TIMESTAMP ~/.claude
```

Or to keep Claude Code working without the toolkit:
```bash
rm ~/.claude/settings.json ~/.claude/commands ~/.claude/hooks ~/.claude/skills
```
