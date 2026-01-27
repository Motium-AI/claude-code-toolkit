# Quick Start Guide

Get up and running with Claude Code Toolkit in 5 minutes.

## Prerequisites

- [Claude Code CLI](https://claude.ai/code) installed and authenticated
- Python 3.8+ (required for hooks)
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

The installer will:
1. Back up your existing `~/.claude/` directory (if any)
2. Create symlinks from `~/.claude/` to this repository
3. Make hook scripts executable
4. **Verify** that Python and all hooks work correctly
5. **Test** state file detection and auto-approval

You should see:
```
═══════════════════════════════════════════════════════════════
  ✓ ALL CHECKS PASSED
═══════════════════════════════════════════════════════════════

IMPORTANT: Restart Claude Code for hooks to take effect!
```

### Installation Options

```bash
./scripts/install.sh              # Interactive install with verification
./scripts/install.sh --force      # Skip confirmation prompts
./scripts/install.sh --verify     # Only run verification (no install)
./scripts/install.sh --remote     # Install on remote devbox (syncs toolkit)
./scripts/install.sh --remote myhost  # Install on specific remote host
```

### Manual Installation

If you prefer manual control:

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

# Verify installation
./scripts/install.sh --verify
```

## Step 3: Restart Claude Code

**CRITICAL**: Hooks are captured at session startup. After installation, you must restart Claude Code:

```bash
# If Claude is running, exit it first
# Then start fresh:
claude
```

You should see a SessionStart message confirming hooks loaded:
```
SessionStart:startup hook success: MANDATORY: Before executing ANY user request...
```

## Step 4: Try Your First Autonomous Workflow

### Option A: /appfix (Debug a broken app)

```bash
cd your-project
claude
> /appfix
```

Claude will autonomously:
1. Check service health
2. Collect logs from Azure/browser
3. Diagnose and fix issues
4. Deploy and verify in browser
5. **Not stop until it's actually done**

### Option B: /godo (Execute any task)

```bash
claude
> /godo add a logout button to the navbar
```

Claude will:
1. Explore the codebase first (mandatory plan mode)
2. Implement the feature
3. Run linters and fix all errors
4. Deploy and verify
5. **Not stop until verified**

## Step 5: Configure Your Project (Optional)

For `/appfix` to work optimally, create a service topology file:

```bash
mkdir -p .claude/skills/appfix/references
cat > .claude/skills/appfix/references/service-topology.md << 'EOF'
# Service Topology

| Service | URL | Health Endpoint |
|---------|-----|-----------------|
| Frontend | https://staging.example.com | /api/health |
| Backend | https://api-staging.example.com | /health |

## Deployment Commands

```bash
# Frontend
gh workflow run frontend-ci.yml -f environment=staging

# Backend
gh workflow run backend-ci.yml -f environment=staging
```
EOF
```

## Understanding How It Works

### The State File System

The toolkit uses state files to enable autonomous execution:

| File | Location | Purpose |
|------|----------|---------|
| `appfix-state.json` | `~/.claude/` | Enables cross-repo detection (e.g., fixing in terraform repo) |
| `appfix-state.json` | `.claude/` | Tracks iteration, plan mode, verification evidence |
| `godo-state.json` | Same locations | Same purpose for /godo workflows |

When you run `/appfix` or `/godo`, Claude creates these files automatically. The hooks detect them and enable:
- **Auto-approval**: All tool permissions approved without prompts
- **Plan mode enforcement**: Edit/Write blocked until plan mode completes (first iteration)
- **Stop validation**: Cannot stop until completion checkpoint passes

### The Hook Lifecycle

```
┌─────────────────────────────────────────────────────────────────────┐
│  SessionStart                                                        │
│    └─► session-snapshot.py captures git state                       │
│    └─► read-docs-reminder.py reminds to read project docs           │
├─────────────────────────────────────────────────────────────────────┤
│  PreToolUse (Edit/Write)                                             │
│    └─► plan-mode-enforcer.py blocks until plan mode done            │
├─────────────────────────────────────────────────────────────────────┤
│  PermissionRequest (any tool)                                        │
│    └─► appfix-auto-approve.py auto-allows if state file exists      │
├─────────────────────────────────────────────────────────────────────┤
│  PostToolUse                                                         │
│    └─► checkpoint-invalidator.py resets stale checkpoint flags      │
│    └─► plan-mode-tracker.py marks plan mode complete                │
├─────────────────────────────────────────────────────────────────────┤
│  Stop                                                                │
│    └─► stop-validator.py validates completion checkpoint            │
│    └─► Blocks if is_job_complete: false or what_remains not empty   │
└─────────────────────────────────────────────────────────────────────┘
```

### Session Restart Requirement

**Why you must restart Claude Code after installation:**

Hooks are loaded once at session startup. Changes to:
- `~/.claude/settings.json`
- Hook scripts
- State files

...don't take effect until you start a new session.

**Symptoms of stale session:**
- Hooks don't fire (no SessionStart message)
- Auto-approval doesn't work
- Plan mode enforcer doesn't block

**Solution:** Exit Claude Code and start fresh.

## Troubleshooting

### Run the Doctor

If something isn't working, run diagnostics:

```bash
./scripts/doctor.sh
```

This checks:
- Python and hook script syntax
- Symlink integrity
- Hook configuration in settings.json
- State file detection logic
- Auto-approval hook behavior
- Debug log contents

### Common Issues

#### "Hooks not firing"

```bash
# 1. Verify installation
./scripts/install.sh --verify

# 2. Check symlinks
ls -la ~/.claude/

# 3. Restart Claude Code
# Exit and run: claude
```

#### "Auto-approval not working"

```bash
# Check if state file exists
cat .claude/appfix-state.json
# or
cat ~/.claude/appfix-state.json

# If missing, /appfix or /godo should create it
# Or create manually:
mkdir -p .claude
echo '{"iteration": 1, "plan_mode_completed": true}' > .claude/appfix-state.json
```

#### "Plan mode enforcer blocking edits"

The enforcer blocks Edit/Write on first iteration until plan mode completes. This is intentional - it ensures Claude explores the codebase before making changes.

```bash
# Check state
cat .claude/appfix-state.json | grep plan_mode_completed
# Should be: "plan_mode_completed": true

# If stuck, update the state:
# (Only do this if you've already explored the codebase!)
python3 -c "
import json
with open('.claude/appfix-state.json', 'r+') as f:
    state = json.load(f)
    state['plan_mode_completed'] = True
    f.seek(0)
    json.dump(state, f, indent=2)
    f.truncate()
"
```

#### "Hook errors in output"

Check the debug log:

```bash
tail -100 /tmp/claude-hooks-debug.log
```

#### "Remote devbox hooks not working"

```bash
# Sync and install to remote
./scripts/install.sh --remote cc-devbox

# Or manually:
ssh cc-devbox
cd ~/claude-code-toolkit
./scripts/install.sh --force
./scripts/doctor.sh
```

### Verify Hook Imports Manually

```bash
python3 -c "
import sys
sys.path.insert(0, '$HOME/.claude/hooks')
from _common import is_autonomous_mode_active, is_appfix_active, is_godo_active
print('Imports: OK')
print('is_appfix_active test:', is_appfix_active('/tmp'))
"
```

## Remote Installation (Devbox/EC2)

For running Claude Code on a remote server:

```bash
# From your local machine:
./scripts/install.sh --remote cc-devbox

# This will:
# 1. Sync the toolkit to ~/claude-code-toolkit on remote
# 2. Run the installer
# 3. Run verification
```

### Token Sync for OAuth

If using Claude Code on multiple devices with the same OAuth account:

```bash
# On devbox, use CLAUDE_CODE_OAUTH_TOKEN env var
# to avoid OAuth refresh token conflicts

# Add to ~/.bashrc or ~/.profile:
export CLAUDE_CODE_OAUTH_TOKEN="sk-ant-oat01-..."
unset ANTHROPIC_API_KEY

# Get token from Mac keychain:
security find-generic-password -s "Claude Code-credentials" -w | jq -r '.claudeAiOauth.accessToken'
```

## What's Next?

- **Deep dive into concepts**: Read [docs/concepts/](docs/concepts/) for how commands, skills, and hooks work
- **Customize**: Create your own commands and skills with [docs/guides/customization.md](docs/guides/customization.md)
- **Understand the architecture**: See [docs/architecture.md](docs/architecture.md) for how everything fits together

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
