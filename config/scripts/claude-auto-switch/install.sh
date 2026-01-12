#!/bin/bash
# Install claude-auto-switch
#
# This script:
# 1. Creates the target directory
# 2. Copies switch.py and config.json
# 3. Provides instructions for account setup and shell alias

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="$HOME/.claude/scripts/claude-auto-switch"

echo "📦 Installing claude-auto-switch..."
echo ""

# Create target directory
mkdir -p "$TARGET_DIR"

# Copy files
cp "$SCRIPT_DIR/switch.py" "$TARGET_DIR/"
cp "$SCRIPT_DIR/config.json" "$TARGET_DIR/"
chmod +x "$TARGET_DIR/switch.py"

echo "✅ Installed to: $TARGET_DIR"
echo ""

# Symlink settings.json to share MCP servers, hooks, env vars across accounts
echo "🔗 Setting up settings symlinks for backup accounts..."
for dir in ~/.claude-max-*; do
    if [ -d "$dir" ] && [ ! -L "$dir/settings.json" ]; then
        ln -sf ~/.claude/settings.json "$dir/settings.json"
        echo "   Linked: $dir/settings.json -> ~/.claude/settings.json"
    fi
done
echo ""

# Symlink projects directory to enable session resume across accounts
echo "🔗 Setting up projects symlinks for session sharing..."
for dir in ~/.claude-max-*; do
    if [ -d "$dir" ]; then
        # Remove existing projects dir (if it's a directory, not a symlink)
        if [ -d "$dir/projects" ] && [ ! -L "$dir/projects" ]; then
            rm -rf "$dir/projects"
            echo "   Removed: $dir/projects (was directory)"
        fi
        # Create symlink if not exists
        if [ ! -L "$dir/projects" ]; then
            ln -sf ~/.claude/projects "$dir/projects"
            echo "   Linked: $dir/projects -> ~/.claude/projects"
        fi
    fi
done
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "NEXT STEPS:"
echo ""
echo "1️⃣  Create account directories:"
echo "    mkdir -p ~/.claude-max-1 ~/.claude-max-2"
echo ""
echo "2️⃣  Authenticate each account (requires separate Anthropic accounts):"
echo "    CLAUDE_CONFIG_DIR=~/.claude-max-1 claude"
echo "    # Complete login for account 1, then exit"
echo ""
echo "    CLAUDE_CONFIG_DIR=~/.claude-max-2 claude"
echo "    # Complete login for account 2, then exit"
echo ""
echo "3️⃣  Symlink settings (preserves MCP servers, hooks, env vars):"
echo "    ln -sf ~/.claude/settings.json ~/.claude-max-1/settings.json"
echo "    ln -sf ~/.claude/settings.json ~/.claude-max-2/settings.json"
echo ""
echo "4️⃣  Add alias to your shell config (~/.zshrc or ~/.bashrc):"
echo ""
echo "    # Add this line:"
echo "    alias claude='python3 $TARGET_DIR/switch.py'"
echo ""
echo "5️⃣  Reload your shell:"
echo "    source ~/.zshrc  # or source ~/.bashrc"
echo ""
echo "6️⃣  (Optional) Edit config to customize account names:"
echo "    $EDITOR $TARGET_DIR/config.json"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "USAGE:"
echo "  claude              # Starts with primary account"
echo "                      # Auto-switches on rate limit"
echo ""
echo "  claude -p 'prompt'  # Pass arguments as normal"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "⚠️  IMPORTANT: You need TWO separate Anthropic accounts"
echo "   (different email addresses) for this to work."
echo ""
echo "📖 Documentation: prompts/docs/guides/auto-switch.md"
echo ""
