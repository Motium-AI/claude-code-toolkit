#!/bin/bash
#
# Claude Code Toolkit Installer
#
# This script installs the toolkit by:
# 1. Backing up existing ~/.claude config
# 2. Creating symlinks to this repository
# 3. Making hooks executable
# 4. Verifying Python and hook imports work
# 5. Running a complete hook verification test
#
# Usage:
#   ./scripts/install.sh              # Interactive install
#   ./scripts/install.sh --force      # Skip confirmation
#   ./scripts/install.sh --verify     # Only run verification (no install)
#   ./scripts/install.sh --remote     # Install on remote devbox
#   ./scripts/install.sh --uninstall  # Remove toolkit symlinks (preserves ~/.claude)
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the directory where this script lives
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG_DIR="$REPO_DIR/config"

# Parse arguments
FORCE=false
VERIFY_ONLY=false
REMOTE=false
REMOTE_HOST=""
UNINSTALL=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --force)
            FORCE=true
            shift
            ;;
        --verify)
            VERIFY_ONLY=true
            shift
            ;;
        --remote)
            REMOTE=true
            REMOTE_HOST="${2:-ubuntu@cc-devbox}"
            shift 2 2>/dev/null || shift
            ;;
        --uninstall)
            UNINSTALL=true
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# ═══════════════════════════════════════════════════════════════════════════
# VERIFICATION FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

verify_python() {
    echo -e "${BLUE}Checking Python 3...${NC}"
    if ! command -v python3 &> /dev/null; then
        echo -e "  ${RED}✗ Python 3 not found${NC}"
        echo "    Install Python 3: https://www.python.org/downloads/"
        return 1
    fi
    PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
    PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
    PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
    if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]; }; then
        echo -e "  ${RED}✗ Python $PYTHON_VERSION too old (need 3.8+)${NC}"
        echo "    Upgrade Python: https://www.python.org/downloads/"
        return 1
    fi
    echo -e "  ${GREEN}✓ Python $PYTHON_VERSION${NC}"
    return 0
}

verify_hook_imports() {
    echo -e "${BLUE}Testing hook imports...${NC}"

    local HOOKS_DIR="$HOME/.claude/hooks"
    if [ ! -d "$HOOKS_DIR" ]; then
        echo -e "  ${RED}✗ Hooks directory not found: $HOOKS_DIR${NC}"
        return 1
    fi

    # Test _common.py imports
    if python3 -c "import sys; sys.path.insert(0, '$HOOKS_DIR'); from _common import is_autonomous_mode_active, is_appfix_active, is_godo_active" 2>/dev/null; then
        echo -e "  ${GREEN}✓ _common.py imports work${NC}"
    else
        echo -e "  ${RED}✗ _common.py import failed${NC}"
        echo "    Run: python3 -c \"import sys; sys.path.insert(0, '$HOOKS_DIR'); from _common import is_autonomous_mode_active\""
        return 1
    fi

    # Test key hooks can be imported/executed
    local KEY_HOOKS=("appfix-auto-approve.py" "plan-mode-enforcer.py" "stop-validator.py")
    for hook in "${KEY_HOOKS[@]}"; do
        if [ -f "$HOOKS_DIR/$hook" ]; then
            if python3 -c "import ast; ast.parse(open('$HOOKS_DIR/$hook').read())" 2>/dev/null; then
                echo -e "  ${GREEN}✓ $hook syntax OK${NC}"
            else
                echo -e "  ${RED}✗ $hook has syntax errors${NC}"
                return 1
            fi
        else
            echo -e "  ${YELLOW}⚠ $hook not found${NC}"
        fi
    done

    return 0
}

verify_state_detection() {
    echo -e "${BLUE}Testing state file detection...${NC}"

    local HOOKS_DIR="$HOME/.claude/hooks"
    local TEST_DIR=$(mktemp -d)

    # Create a test state file
    mkdir -p "$TEST_DIR/.claude"
    cat > "$TEST_DIR/.claude/appfix-state.json" <<EOF
{
  "iteration": 1,
  "plan_mode_completed": true,
  "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

    # Test detection
    local RESULT=$(python3 -c "
import sys
sys.path.insert(0, '$HOOKS_DIR')
from _common import is_autonomous_mode_active, is_appfix_active
print('appfix:', is_appfix_active('$TEST_DIR'))
print('autonomous:', is_autonomous_mode_active('$TEST_DIR'))
" 2>&1)

    # Cleanup
    rm -rf "$TEST_DIR"

    if echo "$RESULT" | grep -q "appfix: True"; then
        echo -e "  ${GREEN}✓ State file detection works${NC}"
        return 0
    else
        echo -e "  ${RED}✗ State file detection failed${NC}"
        echo "    Result: $RESULT"
        return 1
    fi
}

verify_hooks_config() {
    echo -e "${BLUE}Checking hook configuration...${NC}"

    local SETTINGS="$HOME/.claude/settings.json"
    if [ ! -f "$SETTINGS" ]; then
        echo -e "  ${RED}✗ settings.json not found${NC}"
        return 1
    fi

    # Check for required hooks
    local REQUIRED_HOOKS=("SessionStart" "Stop" "PreToolUse" "PostToolUse" "PermissionRequest")
    for hook_event in "${REQUIRED_HOOKS[@]}"; do
        if grep -q "\"$hook_event\"" "$SETTINGS"; then
            echo -e "  ${GREEN}✓ $hook_event hooks configured${NC}"
        else
            echo -e "  ${YELLOW}⚠ $hook_event hooks not found${NC}"
        fi
    done

    return 0
}

verify_auto_approval() {
    echo -e "${BLUE}Testing auto-approval hook...${NC}"

    local HOOKS_DIR="$HOME/.claude/hooks"
    local TEST_DIR=$(mktemp -d)

    # Create a test state file
    mkdir -p "$TEST_DIR/.claude"
    cat > "$TEST_DIR/.claude/appfix-state.json" <<EOF
{
  "iteration": 1,
  "plan_mode_completed": true,
  "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

    # Run the auto-approval hook with empty stdin (simulating PermissionRequest)
    local RESULT=$(cd "$TEST_DIR" && echo "" | python3 "$HOOKS_DIR/appfix-auto-approve.py" 2>&1)

    # Cleanup
    rm -rf "$TEST_DIR"

    if echo "$RESULT" | grep -q '"behavior": "allow"'; then
        echo -e "  ${GREEN}✓ Auto-approval hook works${NC}"
        return 0
    else
        echo -e "  ${RED}✗ Auto-approval hook failed${NC}"
        echo "    Expected: {\"hookSpecificOutput\": {...\"behavior\": \"allow\"...}}"
        echo "    Got: $RESULT"
        return 1
    fi
}

verify_optional_tools() {
    echo -e "${BLUE}Checking optional tools...${NC}"

    # Surf CLI - needed for /appfix web verification
    echo -n "  Surf CLI: "
    if command -v surf &> /dev/null; then
        echo -e "${GREEN}installed${NC}"
    else
        echo -e "${YELLOW}not found (optional - needed for /appfix web verification)${NC}"
        echo "    Install: npm install -g @nicobailon/surf-cli"
    fi

    # GitHub CLI - needed for PR creation and deployment workflows
    echo -n "  GitHub CLI (gh): "
    if command -v gh &> /dev/null; then
        GH_VERSION=$(gh --version 2>&1 | head -1 | cut -d' ' -f3)
        echo -e "${GREEN}$GH_VERSION${NC}"
    else
        echo -e "${YELLOW}not found (optional - needed for PR/deployment workflows)${NC}"
        echo "    Install: https://cli.github.com/"
    fi

    # Always return 0 - these are optional
    return 0
}

run_full_verification() {
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  CLAUDE CODE TOOLKIT VERIFICATION${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo ""

    local FAILED=0

    verify_python || FAILED=1
    verify_hooks_config || FAILED=1
    verify_hook_imports || FAILED=1
    verify_state_detection || FAILED=1
    verify_auto_approval || FAILED=1
    verify_optional_tools

    echo ""
    if [ $FAILED -eq 0 ]; then
        echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
        echo -e "${GREEN}  ✓ ALL CHECKS PASSED${NC}"
        echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
        echo ""
        echo -e "${YELLOW}IMPORTANT: Restart Claude Code for hooks to take effect!${NC}"
        echo ""
        echo "Next steps:"
        echo "  1. Start Claude Code: claude"
        echo "  2. Verify hooks load: Look for 'SessionStart:' message"
        echo "  3. Try /appfix or /godo in a project"
        echo ""
    else
        echo -e "${RED}═══════════════════════════════════════════════════════════${NC}"
        echo -e "${RED}  ✗ VERIFICATION FAILED${NC}"
        echo -e "${RED}═══════════════════════════════════════════════════════════${NC}"
        echo ""
        echo "Run ./scripts/doctor.sh for detailed diagnostics"
        return 1
    fi

    return 0
}

# ═══════════════════════════════════════════════════════════════════════════
# REMOTE INSTALLATION
# ═══════════════════════════════════════════════════════════════════════════

install_remote() {
    echo -e "${GREEN}Claude Code Toolkit Remote Installer${NC}"
    echo "======================================"
    echo ""
    echo "Installing to: $REMOTE_HOST"
    echo ""

    # Check SSH connectivity
    echo -e "${BLUE}Checking SSH connection...${NC}"
    if ! ssh -o ConnectTimeout=5 "$REMOTE_HOST" "echo 'Connected'" &>/dev/null; then
        echo -e "${RED}✗ Cannot connect to $REMOTE_HOST${NC}"
        echo "  Ensure SSH is configured in ~/.ssh/config"
        exit 1
    fi
    echo -e "  ${GREEN}✓ SSH connection OK${NC}"

    # Check if toolkit exists on remote
    echo -e "${BLUE}Checking remote toolkit location...${NC}"
    REMOTE_TOOLKIT=$(ssh "$REMOTE_HOST" "ls -d ~/claude-code-toolkit 2>/dev/null || echo 'NOT_FOUND'")

    if [ "$REMOTE_TOOLKIT" = "NOT_FOUND" ]; then
        echo -e "  ${YELLOW}Toolkit not found on remote. Syncing from local...${NC}"
        # Sync the toolkit to remote
        rsync -avz --delete \
            --exclude '.git' \
            --exclude 'node_modules' \
            --exclude '__pycache__' \
            "$REPO_DIR/" "$REMOTE_HOST:~/claude-code-toolkit/"
        echo -e "  ${GREEN}✓ Toolkit synced to ~/claude-code-toolkit/${NC}"
    else
        echo -e "  ${GREEN}✓ Toolkit exists at $REMOTE_TOOLKIT${NC}"
    fi

    # Run installer on remote (without verification to avoid double output)
    echo ""
    echo -e "${BLUE}Running installer on remote...${NC}"
    ssh "$REMOTE_HOST" 'cd ~/claude-code-toolkit && bash -c "
        # Backup existing config
        if [ -d ~/.claude ] || [ -L ~/.claude ]; then
            BACKUP_DIR=~/.claude.backup.\$(date +%s)
            echo \"Backing up existing ~/.claude to \$BACKUP_DIR\"
            mv ~/.claude \"\$BACKUP_DIR\"
        fi

        # Create ~/.claude directory
        mkdir -p ~/.claude

        # Create symlinks
        echo \"Creating symlinks...\"
        ln -sf ~/claude-code-toolkit/config/settings.json ~/.claude/settings.json && echo \"  ✓ settings.json\"
        ln -sf ~/claude-code-toolkit/config/commands ~/.claude/commands && echo \"  ✓ commands/\"
        ln -sf ~/claude-code-toolkit/config/hooks ~/.claude/hooks && echo \"  ✓ hooks/\"
        ln -sf ~/claude-code-toolkit/config/skills ~/.claude/skills && echo \"  ✓ skills/\"

        # Make hooks executable
        chmod +x ~/claude-code-toolkit/config/hooks/*.py 2>/dev/null
        echo \"  ✓ hooks executable\"
        echo \"\"
        echo \"Installation complete!\"
    "'

    # Run verification on remote
    echo ""
    echo -e "${BLUE}Running verification on remote...${NC}"
    ssh "$REMOTE_HOST" 'python3 -c "
import os, sys
hooks_dir = os.path.expanduser(\"~/.claude/hooks\")
sys.path.insert(0, hooks_dir)

print(\"Checking hook imports...\")
try:
    from _common import is_autonomous_mode_active, is_appfix_active, is_godo_active
    print(\"  ✓ _common.py imports work\")
except Exception as e:
    print(f\"  ✗ Import failed: {e}\")
    sys.exit(1)

print(\"Checking state detection...\")
import tempfile, json, datetime
test_dir = tempfile.mkdtemp()
os.makedirs(f\"{test_dir}/.claude\", exist_ok=True)
with open(f\"{test_dir}/.claude/appfix-state.json\", \"w\") as f:
    json.dump({
        \"iteration\": 1,
        \"plan_mode_completed\": True,
        \"started_at\": datetime.datetime.now(datetime.timezone.utc).strftime(\"%Y-%m-%dT%H:%M:%SZ\")
    }, f)

if is_appfix_active(test_dir):
    print(\"  ✓ State file detection works\")
else:
    print(\"  ✗ State file detection failed\")
    sys.exit(1)

import shutil
shutil.rmtree(test_dir)

print(\"Checking auto-approval hook...\")
import subprocess
test_dir = tempfile.mkdtemp()
os.makedirs(f\"{test_dir}/.claude\", exist_ok=True)
with open(f\"{test_dir}/.claude/appfix-state.json\", \"w\") as f:
    json.dump({
        \"iteration\": 1,
        \"plan_mode_completed\": True,
        \"started_at\": datetime.datetime.now(datetime.timezone.utc).strftime(\"%Y-%m-%dT%H:%M:%SZ\")
    }, f)

hook_path = os.path.join(hooks_dir, \"appfix-auto-approve.py\")
result = subprocess.run(
    [\"python3\", hook_path],
    cwd=test_dir,
    input=\"\",
    capture_output=True,
    text=True
)
shutil.rmtree(test_dir)

if \"allow\" in result.stdout:
    print(\"  ✓ Auto-approval hook works\")
else:
    print(f\"  ✗ Auto-approval failed: {result.stdout} {result.stderr}\")
    sys.exit(1)

print(\"\")
print(\"═\" * 50)
print(\"  ✓ ALL CHECKS PASSED\")
print(\"═\" * 50)
"'

    echo ""
    echo -e "${GREEN}Remote installation complete!${NC}"
    echo ""
    echo "To use Claude on $REMOTE_HOST:"
    echo "  ssh $REMOTE_HOST"
    echo "  claude  # or claude-motium if using token wrapper"
}

# ═══════════════════════════════════════════════════════════════════════════
# MAIN INSTALLATION
# ═══════════════════════════════════════════════════════════════════════════

# Handle remote installation
if [ "$REMOTE" = true ]; then
    install_remote
    exit 0
fi

# Handle uninstall
if [ "$UNINSTALL" = true ]; then
    echo -e "${GREEN}Claude Code Toolkit Uninstaller${NC}"
    echo "================================="
    echo ""

    REMOVED=0

    # Only remove symlinks that point to THIS repo
    for ITEM in settings.json hooks commands skills; do
        SPATH="$HOME/.claude/$ITEM"
        if [ -L "$SPATH" ]; then
            TARGET=$(readlink "$SPATH" 2>/dev/null || echo "")
            if echo "$TARGET" | grep -q "$(basename "$REPO_DIR")"; then
                rm -f "$SPATH"
                echo -e "  ${GREEN}✓ Removed symlink: $ITEM → $TARGET${NC}"
                REMOVED=$((REMOVED + 1))
            else
                echo -e "  ${YELLOW}⚠ Skipped $ITEM (points to: $TARGET, not this toolkit)${NC}"
            fi
        elif [ -e "$SPATH" ]; then
            echo -e "  ${YELLOW}⚠ Skipped $ITEM (not a symlink)${NC}"
        fi
    done

    if [ $REMOVED -eq 0 ]; then
        echo -e "  ${YELLOW}No toolkit symlinks found to remove.${NC}"
    else
        echo ""
        echo -e "${GREEN}Removed $REMOVED symlink(s).${NC}"
    fi

    echo ""
    echo "Note: ~/.claude/ directory preserved (contains state files, plans, memories)."

    # Check for backups
    BACKUPS=$(ls -d "$HOME/.claude.backup."* 2>/dev/null | head -3)
    if [ -n "$BACKUPS" ]; then
        echo ""
        echo "Backups available:"
        for BACKUP in $BACKUPS; do
            echo "  $BACKUP"
        done
        echo ""
        echo "To restore a backup: mv <backup> ~/.claude"
    fi

    exit 0
fi

# Handle verify-only mode
if [ "$VERIFY_ONLY" = true ]; then
    run_full_verification
    exit $?
fi

# Main installation flow
echo -e "${GREEN}Claude Code Toolkit Installer${NC}"
echo "==============================="
echo ""
echo "This will install Claude Code Toolkit by creating symlinks"
echo "from ~/.claude/ to $CONFIG_DIR"
echo ""

# Check if config directory exists
if [ ! -d "$CONFIG_DIR" ]; then
    echo -e "${RED}Error: Config directory not found at $CONFIG_DIR${NC}"
    exit 1
fi

# Check Python first
if ! verify_python; then
    echo -e "${RED}Python 3 is required. Install it first.${NC}"
    exit 1
fi

# Confirm unless --force or non-interactive (stdin not a terminal)
if [ "$FORCE" = false ] && [ -t 0 ]; then
    read -p "Continue? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Cancelled."
        exit 0
    fi
fi

# Backup existing config
if [ -d "$HOME/.claude" ] || [ -L "$HOME/.claude" ]; then
    # Check if it's already a symlink to this repo
    if [ -L "$HOME/.claude/settings.json" ]; then
        CURRENT_TARGET=$(readlink "$HOME/.claude/settings.json" 2>/dev/null || echo "")
        if [ "$CURRENT_TARGET" = "$CONFIG_DIR/settings.json" ]; then
            echo -e "${YELLOW}Already installed (symlinks point here). Skipping backup.${NC}"
        else
            BACKUP_DIR="$HOME/.claude.backup.$(date +%s)"
            echo -e "${YELLOW}Backing up existing ~/.claude to $BACKUP_DIR${NC}"
            mv "$HOME/.claude" "$BACKUP_DIR"
        fi
    else
        BACKUP_DIR="$HOME/.claude.backup.$(date +%s)"
        echo -e "${YELLOW}Backing up existing ~/.claude to $BACKUP_DIR${NC}"
        mv "$HOME/.claude" "$BACKUP_DIR"
    fi
fi

# Create ~/.claude directory if it doesn't exist
if [ ! -d "$HOME/.claude" ]; then
    echo "Creating ~/.claude directory..."
    mkdir -p "$HOME/.claude"
fi

# Create symlinks
echo "Creating symlinks..."

# Settings file
if [ -f "$CONFIG_DIR/settings.json" ]; then
    rm -f "$HOME/.claude/settings.json"
    ln -sf "$CONFIG_DIR/settings.json" "$HOME/.claude/settings.json"
    echo "  ✓ settings.json"
fi

# Commands directory
if [ -d "$CONFIG_DIR/commands" ]; then
    rm -f "$HOME/.claude/commands"
    ln -sf "$CONFIG_DIR/commands" "$HOME/.claude/commands"
    echo "  ✓ commands/"
fi

# Hooks directory
if [ -d "$CONFIG_DIR/hooks" ]; then
    rm -f "$HOME/.claude/hooks"
    ln -sf "$CONFIG_DIR/hooks" "$HOME/.claude/hooks"
    echo "  ✓ hooks/"
fi

# Skills directory
if [ -d "$CONFIG_DIR/skills" ]; then
    rm -f "$HOME/.claude/skills"
    ln -sf "$CONFIG_DIR/skills" "$HOME/.claude/skills"
    echo "  ✓ skills/"
fi

# Make hooks executable
echo "Making hooks executable..."
if [ -d "$CONFIG_DIR/hooks" ]; then
    chmod +x "$CONFIG_DIR/hooks"/*.py 2>/dev/null || true
    echo "  ✓ hooks/*.py"
fi

# Initialize auto-update state file
echo "Initializing auto-update state..."
TOOLKIT_STATE="$HOME/.claude/toolkit-update-state.json"
if [ ! -f "$TOOLKIT_STATE" ]; then
    cat > "$TOOLKIT_STATE" << EOF
{
  "last_check_timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "last_check_result": "up_to_date",
  "settings_hash_at_session_start": null,
  "pending_restart_reason": null,
  "update_history": []
}
EOF
    echo "  ✓ initialized toolkit-update-state.json"
else
    echo "  ✓ toolkit-update-state.json already exists"
fi

echo ""
echo -e "${GREEN}Symlinks created!${NC}"
echo ""

# Run verification
run_full_verification

# Show uninstall instructions
echo "To uninstall:"
echo "  rm -rf ~/.claude"
if [ -n "$BACKUP_DIR" ]; then
    echo "  mv $BACKUP_DIR ~/.claude  # restore backup"
fi
echo ""
