#!/usr/bin/env bash
# =============================================================================
# Setup Harness Sandbox
# =============================================================================
#
# Creates an isolated sandbox for testing Claude Code harness changes.
# Unlike the regular skill-sandbox, this sandbox:
#   - Symlinks hooks/skills/commands from the PROJECT (not ~/.claude/)
#   - Copies settings.json from the PROJECT
#   - Allows testing MODIFIED hooks before committing
#
# Usage:
#   ./setup-harness-sandbox.sh [project-dir]
#   Returns sandbox ID on success
#
# =============================================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
SANDBOX_BASE="/tmp/claude-sandboxes"
PROJECT_DIR="${1:-$(pwd)}"

# Verify this is a harness project
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if ! "$SCRIPT_DIR/detect-harness.sh" "$PROJECT_DIR" >/dev/null 2>&1; then
    echo -e "${RED}ERROR: Not a harness project: $PROJECT_DIR${NC}" >&2
    echo "Run from namshub directory or pass path as argument" >&2
    exit 1
fi

# Generate unique sandbox ID
SANDBOX_ID="harness-$(date +%s)-$(openssl rand -hex 4)"
SANDBOX_ROOT="$SANDBOX_BASE/$SANDBOX_ID"
FAKE_HOME="$SANDBOX_ROOT/fake-home"
FAKE_CLAUDE_DIR="$FAKE_HOME/.claude"
PROJECT_WORKTREE="$SANDBOX_ROOT/project"
MOCK_BIN="$SANDBOX_ROOT/bin"

echo -e "${BLUE}Creating harness sandbox: ${CYAN}$SANDBOX_ID${NC}" >&2

# Create directory structure
mkdir -p "$SANDBOX_ROOT"
mkdir -p "$FAKE_HOME"
mkdir -p "$FAKE_CLAUDE_DIR"
mkdir -p "$MOCK_BIN"

# =============================================================================
# STEP 1: Copy real credentials (needed for Claude CLI to authenticate)
# =============================================================================
echo -e "${YELLOW}[1/6] Setting up credentials...${NC}" >&2

# Copy real credentials so Claude can authenticate in the sandbox.
# Security is maintained through mock commands (gh, az) that block deployments/PRs.
REAL_CREDS="$HOME/.claude/.credentials-export.json"
if [[ -f "$REAL_CREDS" ]]; then
    cp "$REAL_CREDS" "$FAKE_CLAUDE_DIR/.credentials-export.json"
    chmod 600 "$FAKE_CLAUDE_DIR/.credentials-export.json"
    echo -e "  Copied real credentials to sandbox" >&2
else
    echo -e "${YELLOW}  WARNING: No credentials found at $REAL_CREDS${NC}" >&2
    echo -e "  Claude CLI will not be able to authenticate in sandbox" >&2
fi

# =============================================================================
# STEP 2: Create git worktree for project isolation
# =============================================================================
echo -e "${YELLOW}[2/6] Creating git worktree...${NC}" >&2

BRANCH_NAME="harness-sandbox/$SANDBOX_ID"
(
    cd "$PROJECT_DIR"
    git branch -D "$BRANCH_NAME" 2>/dev/null || true
    git worktree add -b "$BRANCH_NAME" "$PROJECT_WORKTREE" HEAD 2>/dev/null || {
        # Fallback: detached HEAD
        git worktree add "$PROJECT_WORKTREE" HEAD --detach 2>/dev/null
    }
)

# Create .claude directory in worktree
mkdir -p "$PROJECT_WORKTREE/.claude"

# =============================================================================
# STEP 3: Propagate uncommitted changes to worktree
# =============================================================================
echo -e "${YELLOW}[3/6] Propagating uncommitted changes...${NC}" >&2

"$SCRIPT_DIR/propagate-changes.sh" "$PROJECT_DIR" "$PROJECT_WORKTREE"

# =============================================================================
# STEP 4: Symlink hooks/skills/commands from PROJECT (not ~/.claude/)
# =============================================================================
echo -e "${YELLOW}[4/6] Symlinking harness config from project...${NC}" >&2

# This is the KEY DIFFERENCE from regular sandbox:
# We symlink to the PROJECT's config, not the real ~/.claude/
ln -s "$PROJECT_WORKTREE/config/hooks" "$FAKE_CLAUDE_DIR/hooks"
ln -s "$PROJECT_WORKTREE/config/skills" "$FAKE_CLAUDE_DIR/skills"
ln -s "$PROJECT_WORKTREE/config/commands" "$FAKE_CLAUDE_DIR/commands"

# Copy settings.json from project
if [[ -f "$PROJECT_WORKTREE/config/settings.json" ]]; then
    cp "$PROJECT_WORKTREE/config/settings.json" "$FAKE_CLAUDE_DIR/settings.json"
fi

# =============================================================================
# STEP 5: Create mock commands (gh, az)
# =============================================================================
echo -e "${YELLOW}[5/6] Creating mock commands...${NC}" >&2

# Mock gh command
cat > "$MOCK_BIN/gh" << 'GHEOF'
#!/usr/bin/env bash
BLOCKED_LOG="${SANDBOX_DIR}/blocked-commands.log"
log_blocked() {
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] BLOCKED: gh $*" >> "$BLOCKED_LOG"
    echo "HARNESS SANDBOX: Command blocked: gh $*" >&2
}
case "$1" in
    workflow)
        case "$2" in
            run|dispatch)
                log_blocked "$@"
                echo "ERROR: gh workflow run blocked in harness sandbox" >&2
                exit 1
                ;;
            *) exec /usr/local/bin/gh "$@" 2>/dev/null || exec /opt/homebrew/bin/gh "$@" ;;
        esac
        ;;
    pr)
        case "$2" in
            create|merge)
                log_blocked "$@"
                exit 1
                ;;
            *) exec /usr/local/bin/gh "$@" 2>/dev/null || exec /opt/homebrew/bin/gh "$@" ;;
        esac
        ;;
    *) exec /usr/local/bin/gh "$@" 2>/dev/null || exec /opt/homebrew/bin/gh "$@" ;;
esac
GHEOF
chmod +x "$MOCK_BIN/gh"

# Mock az command
cat > "$MOCK_BIN/az" << 'AZEOF'
#!/usr/bin/env bash
BLOCKED_LOG="${SANDBOX_DIR}/blocked-commands.log"
log_blocked() {
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] BLOCKED: az $*" >> "$BLOCKED_LOG"
    echo "HARNESS SANDBOX: Command blocked: az $*" >&2
}
case "$1" in
    containerapp|webapp)
        case "$2" in
            update|create|delete|restart|deployment)
                log_blocked "$@"
                exit 1
                ;;
            *) exec /usr/local/bin/az "$@" 2>/dev/null || exec /opt/homebrew/bin/az "$@" ;;
        esac
        ;;
    *) exec /usr/local/bin/az "$@" 2>/dev/null || exec /opt/homebrew/bin/az "$@" ;;
esac
AZEOF
chmod +x "$MOCK_BIN/az"

# =============================================================================
# STEP 6: Create environment file
# =============================================================================
echo -e "${YELLOW}[6/6] Creating environment file...${NC}" >&2

cat > "$SANDBOX_ROOT/env.sh" << ENVEOF
# Harness Sandbox Environment
# Source this file: source $SANDBOX_ROOT/env.sh

# Sandbox identification
export SANDBOX_MODE=true
export HARNESS_SANDBOX=true
export SANDBOX_ID="$SANDBOX_ID"
export SANDBOX_DIR="$SANDBOX_ROOT"

# HOME override (protects real credentials)
export REAL_HOME="\$HOME"
export HOME="$FAKE_HOME"

# PATH override (mock commands first)
export REAL_PATH="\$PATH"
export PATH="$MOCK_BIN:\$PATH"

# Project directory
export SANDBOX_PROJECT="$PROJECT_WORKTREE"

# Scrub sensitive environment variables (keep Claude auth — needed for API access)
# Security is maintained through mock commands (gh, az) and credential-file copy
unset OPENAI_API_KEY GITHUB_TOKEN GH_TOKEN
unset AZURE_CLIENT_SECRET AZURE_CLIENT_ID AZURE_TENANT_ID
unset AWS_SECRET_ACCESS_KEY AWS_ACCESS_KEY_ID AWS_SESSION_TOKEN
unset DATABASE_URL POSTGRES_PASSWORD

echo "Harness sandbox loaded: $SANDBOX_ID"
echo "  HOME=\$HOME"
echo "  PROJECT=\$SANDBOX_PROJECT"
echo "  Hooks from: \$HOME/.claude/hooks -> $PROJECT_WORKTREE/config/hooks"
ENVEOF

# Create metadata file
cat > "$SANDBOX_ROOT/metadata.json" << METAEOF
{
    "sandbox_id": "$SANDBOX_ID",
    "sandbox_type": "harness",
    "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "project_source": "$PROJECT_DIR",
    "project_worktree": "$PROJECT_WORKTREE",
    "fake_home": "$FAKE_HOME",
    "mock_bin": "$MOCK_BIN",
    "tmux_socket": "harness-$SANDBOX_ID"
}
METAEOF

# Create blocked commands log
touch "$SANDBOX_ROOT/blocked-commands.log"

# Print summary
echo -e "\n${GREEN}Harness sandbox created!${NC}" >&2
echo -e "${CYAN}Sandbox ID:${NC}       $SANDBOX_ID" >&2
echo -e "${CYAN}Sandbox Root:${NC}     $SANDBOX_ROOT" >&2
echo -e "${CYAN}Fake HOME:${NC}        $FAKE_HOME" >&2
echo -e "${CYAN}Project:${NC}          $PROJECT_WORKTREE" >&2
echo -e "${CYAN}tmux Socket:${NC}      harness-$SANDBOX_ID" >&2

echo -e "\n${YELLOW}Key difference from regular sandbox:${NC}" >&2
echo -e "  hooks/skills/commands symlinked from PROJECT, not ~/.claude/" >&2
echo -e "  This allows testing MODIFIED harness files" >&2

echo -e "\n${YELLOW}To use:${NC}" >&2
echo -e "  tmux -L harness-$SANDBOX_ID new-session -s test 'source $SANDBOX_ROOT/env.sh && cd \$SANDBOX_PROJECT && claude --dangerously-skip-permissions; exec bash'" >&2

# Output sandbox ID (this is the only stdout - captured by caller)
echo "$SANDBOX_ID"
