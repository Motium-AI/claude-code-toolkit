---
name: toolkit
description: Claude Code Toolkit management and information. Use when asked about "/toolkit", "how does the toolkit work", "update toolkit", "toolkit status", "auto-update", or "how to install".
---

# Claude Code Toolkit

This skill explains how the Claude Code Toolkit works, including installation, auto-update, and manual management.

## Triggers

- `/toolkit`
- "how does the toolkit work"
- "update toolkit"
- "toolkit status"
- "how to install"

## What is the Toolkit?

The Claude Code Toolkit extends Claude Code with:

| Component | Purpose | Location |
|-----------|---------|----------|
| **Commands** | Slash-invoked workflows (`/appfix`, `/godo`, `/qa`) | `~/.claude/commands/` |
| **Skills** | Automatic domain expertise injection | `~/.claude/skills/` |
| **Hooks** | Lifecycle event handlers (auto-approval, stop validation) | `~/.claude/hooks/` |

### Key Capabilities

- **Autonomous execution** (`/godo`, `/appfix`) - Complete tasks without asking for confirmation
- **Completion checkpoint** - Stop hook validates that work is actually done
- **Auto-approval** - Tools auto-approved during autonomous workflows
- **Auto-update** - Toolkit updates itself on session start

## Installation Architecture

The toolkit uses **symlinks** to connect `~/.claude/` to the toolkit repository:

```
~/.claude/
├── settings.json → <repo>/config/settings.json
├── commands/     → <repo>/config/commands/
├── hooks/        → <repo>/config/hooks/
└── skills/       → <repo>/config/skills/
```

**Benefits:**
- `git pull` in the repo updates all components
- No manual copying of files
- Easy rollback via git

### Installation Command

```bash
git clone https://github.com/Motium-AI/claude-code-toolkit.git ~/claude-code-toolkit
cd ~/claude-code-toolkit && ./scripts/install.sh
```

**After installation, restart Claude Code** - hooks are captured at session startup.

## Auto-Update Mechanism

The toolkit automatically updates on session start via `auto-update.py` hook.

### How It Works

```
Session Start
     │
     ├─► Check: Has 5+ minutes passed since last check?
     │       NO → Skip (fast path)
     │       YES ↓
     │
     ├─► Compare: git ls-remote origin main vs local HEAD
     │       SAME → Skip (up to date)
     │       DIFFERENT ↓
     │
     ├─► Execute: git fetch && git pull --ff-only
     │
     └─► Detect: Did settings.json change?
             NO → "Update complete" (no restart needed)
             YES → "RESTART REQUIRED" warning
```

### Check Interval

Updates are checked every **5 minutes** (rate-limited to avoid slowdowns).

### Settings Change Detection

If `settings.json` changes during an update:
- **Hooks are stale** - they were captured at session start
- **Strong warning displayed** - "RESTART REQUIRED"
- **Session continues** but new hook behavior won't work

### Disable Auto-Update

Set environment variable:
```bash
export CLAUDE_TOOLKIT_AUTO_UPDATE=false
```

## Manual Update

### Check for Updates

```bash
cd ~/claude-code-toolkit  # or wherever you cloned it
git fetch origin main
git log HEAD..origin/main --oneline
```

### Apply Updates

```bash
cd ~/claude-code-toolkit
git pull
```

**If settings.json changed, restart Claude Code.**

### Check Current Version

```bash
cd ~/claude-code-toolkit
git log -1 --format="%h %s"
```

## Toolkit Status

### Check Installation

```bash
# Verify symlinks exist
ls -la ~/.claude/settings.json
ls -la ~/.claude/hooks
ls -la ~/.claude/commands
ls -la ~/.claude/skills

# Run verification
~/claude-code-toolkit/scripts/install.sh --verify
```

### Check Update State

```bash
cat ~/.claude/toolkit-update-state.json
```

Fields:
- `last_check_timestamp` - When updates were last checked
- `last_check_result` - "up_to_date", "updated", "check_failed"
- `pending_restart_reason` - Non-null if restart needed
- `update_history` - Last 5 updates

### Diagnose Issues

```bash
~/claude-code-toolkit/scripts/doctor.sh
```

## Uninstall

```bash
~/claude-code-toolkit/scripts/install.sh --uninstall
```

This removes symlinks but preserves `~/.claude/` directory (state files, plans, memories).

## Troubleshooting

### Hooks Not Working

**Cause**: Hooks are captured at Claude Code startup.

**Fix**: Exit and restart Claude Code.

### Auto-Update Fails

**Cause**: Network issues or git conflicts.

**Fix**: Manual update:
```bash
cd ~/claude-code-toolkit
git fetch origin main
git reset --hard origin/main  # Warning: discards local changes
```

### Permission Denied on Hooks

**Cause**: Hook scripts not executable.

**Fix**:
```bash
chmod +x ~/claude-code-toolkit/config/hooks/*.py
```

### Symlinks Broken

**Cause**: Repository moved or deleted.

**Fix**: Re-run installer:
```bash
cd ~/claude-code-toolkit && ./scripts/install.sh --force
```

## Related Commands

| Command | Purpose |
|---------|---------|
| `/godo` | Autonomous task execution |
| `/appfix` | Autonomous debugging |
| `/qa` | Codebase architecture audit |
| `/webtest` | Browser automation testing |

## Related Documentation

- `docs/index.md` - Documentation hub
- `docs/concepts/hooks.md` - Hook system deep dive
- `docs/concepts/skills.md` - Skill system guide
- `README.md` - Quick start and overview
