# Installation Guide

## Prerequisites

- [Claude Code CLI](https://claude.ai/code) installed and authenticated
- Python 3.8+
- Git
- macOS or Linux (Windows WSL works)

## Install

```bash
git clone https://github.com/Motium-AI/namshub.git
cd namshub
./scripts/install.sh
```

The installer will:
1. Back up existing `~/.claude/` (if any)
2. Create symlinks to this repository
3. Make hooks executable
4. Verify everything works

**Source of Truth**: After installation, `~/.claude/skills/` and `~/.claude/hooks/` are symlinks to this repo. When you edit skills or hooks, you're editing the repo. **Commit your changes** to preserve them.

### Installation Options

```bash
./scripts/install.sh              # Interactive + verification
./scripts/install.sh --force      # Skip confirmations
./scripts/install.sh --verify     # Verify only (no install)
./scripts/install.sh --remote     # Install on remote devbox
```

## Restart Claude Code

**CRITICAL**: Hooks load at session startup. After installation:

```bash
# Exit Claude Code if running, then:
claude
```

You should see:
```
SessionStart:startup hook success: ...
```

## Verify

```bash
./scripts/doctor.sh
```

## Troubleshooting

### Hooks not firing
```bash
./scripts/install.sh --verify
ls -la ~/.claude/  # Check symlinks
# Restart Claude Code
```

### Auto-approval not working
```bash
cat .claude/appfix-state.json  # Should exist during /build or /appfix
```

### Debug log
```bash
tail -100 /tmp/claude-hooks-debug.log
```

## Remote Installation

```bash
./scripts/install.sh --remote cc-devbox
```

## Uninstall

```bash
rm -rf ~/.claude
# Restore backup if needed:
mv ~/.claude.backup.TIMESTAMP ~/.claude
```

---

See [README.md](README.md) for usage.
