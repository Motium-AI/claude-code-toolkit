#!/usr/bin/env bash
# =============================================================================
# Claude Code Skill Sandbox Setup
# =============================================================================
#
# Creates an isolated sandbox environment for testing Claude Code skills
# without risking credential exposure, state corruption, or accidental deploys.
#
# SECURITY MEASURES:
#   1. Separate tmux server (-L sandbox-{id}) - env var isolation
#   2. Fake HOME directory - protects ~/.claude/.credentials-export.json
#   3. Mock gh/az commands - blocks dangerous operations
#   4. Git worktree isolation - separate branch for test commits
#   5. Environment scrubbing - removes real API keys
#
# Usage:
#   source sandbox-setup.sh create [--project-dir /path/to/repo]
#   source sandbox-setup.sh destroy <sandbox-id>
#   source sandbox-setup.sh list
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

# Defaults
SANDBOX_BASE="/tmp/claude-sandboxes"
REAL_CLAUDE_DIR="$HOME/.claude"

# =============================================================================
# Sandbox Creation
# =============================================================================

create_sandbox() {
    local project_dir="${1:-$(pwd)}"
    local sandbox_id="sandbox-$(date +%s)-$(openssl rand -hex 4)"
    local sandbox_root="$SANDBOX_BASE/$sandbox_id"
    local fake_home="$sandbox_root/fake-home"
    local fake_claude_dir="$fake_home/.claude"
    local project_worktree="$sandbox_root/project"
    local mock_bin="$sandbox_root/bin"

    echo -e "${BLUE}Creating sandbox: ${CYAN}$sandbox_id${NC}"

    # Create directory structure
    mkdir -p "$sandbox_root"
    mkdir -p "$fake_home"
    mkdir -p "$fake_claude_dir"
    mkdir -p "$mock_bin"

    # =========================================================================
    # SECURITY LAYER 1: Fake Credentials File
    # =========================================================================
    echo -e "${YELLOW}[1/5] Creating fake credentials file...${NC}"
    cat > "$fake_claude_dir/.credentials-export.json" << 'EOF'
{
  "claudeAiOauth": {
    "accessToken": "sk-ant-SANDBOX-FAKE-TOKEN-DO-NOT-USE-000000000000000000000000000000000000000000000000000000",
    "refreshToken": "sk-ant-SANDBOX-FAKE-REFRESH-DO-NOT-USE-00000000000000000000000000000000000000000000000000",
    "expiresAt": 0,
    "scopes": ["sandbox:test:only"],
    "subscriptionType": "sandbox",
    "rateLimitTier": "sandbox"
  },
  "_warning": "THIS IS A FAKE CREDENTIALS FILE FOR SANDBOX TESTING. THESE TOKENS DO NOT WORK."
}
EOF
    chmod 600 "$fake_claude_dir/.credentials-export.json"

    # =========================================================================
    # SECURITY LAYER 2: Copy Settings (Hooks Enabled)
    # =========================================================================
    echo -e "${YELLOW}[2/5] Copying settings and symlinking hooks/skills...${NC}"

    # Copy settings.json if it exists
    if [[ -f "$REAL_CLAUDE_DIR/settings.json" ]]; then
        cp "$REAL_CLAUDE_DIR/settings.json" "$fake_claude_dir/settings.json"
    fi

    # Symlink hooks, skills, and commands (read-only access is safe)
    if [[ -d "$REAL_CLAUDE_DIR/hooks" ]]; then
        ln -s "$REAL_CLAUDE_DIR/hooks" "$fake_claude_dir/hooks"
    fi
    if [[ -d "$REAL_CLAUDE_DIR/skills" ]]; then
        ln -s "$REAL_CLAUDE_DIR/skills" "$fake_claude_dir/skills"
    fi
    if [[ -d "$REAL_CLAUDE_DIR/commands" ]]; then
        ln -s "$REAL_CLAUDE_DIR/commands" "$fake_claude_dir/commands"
    fi

    # =========================================================================
    # SECURITY LAYER 3: Mock Dangerous Commands
    # =========================================================================
    echo -e "${YELLOW}[3/5] Creating mock commands (gh, az)...${NC}"

    # Mock gh command
    cat > "$mock_bin/gh" << 'GHEOF'
#!/usr/bin/env bash
# Mock gh command for sandbox - blocks dangerous operations

BLOCKED_LOG="${SANDBOX_DIR}/blocked-commands.log"

log_blocked() {
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] BLOCKED: gh $*" >> "$BLOCKED_LOG"
    echo "SANDBOX: Command blocked for safety: gh $*" >&2
}

case "$1" in
    workflow)
        case "$2" in
            run|dispatch)
                log_blocked "$@"
                echo "ERROR: gh workflow run is blocked in sandbox mode" >&2
                exit 1
                ;;
            *)
                # Allow read-only workflow commands
                exec /usr/local/bin/gh "$@" 2>/dev/null || exec /opt/homebrew/bin/gh "$@"
                ;;
        esac
        ;;
    pr)
        case "$2" in
            create|merge)
                log_blocked "$@"
                echo "ERROR: gh pr create/merge is blocked in sandbox mode" >&2
                exit 1
                ;;
            *)
                exec /usr/local/bin/gh "$@" 2>/dev/null || exec /opt/homebrew/bin/gh "$@"
                ;;
        esac
        ;;
    release)
        case "$2" in
            create|delete)
                log_blocked "$@"
                echo "ERROR: gh release create/delete is blocked in sandbox mode" >&2
                exit 1
                ;;
            *)
                exec /usr/local/bin/gh "$@" 2>/dev/null || exec /opt/homebrew/bin/gh "$@"
                ;;
        esac
        ;;
    *)
        # Allow other gh commands (pr view, issue view, run list, etc.)
        exec /usr/local/bin/gh "$@" 2>/dev/null || exec /opt/homebrew/bin/gh "$@"
        ;;
esac
GHEOF
    chmod +x "$mock_bin/gh"

    # Mock az command
    cat > "$mock_bin/az" << 'AZEOF'
#!/usr/bin/env bash
# Mock az command for sandbox - blocks dangerous operations

BLOCKED_LOG="${SANDBOX_DIR}/blocked-commands.log"

log_blocked() {
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] BLOCKED: az $*" >> "$BLOCKED_LOG"
    echo "SANDBOX: Command blocked for safety: az $*" >&2
}

case "$1" in
    containerapp)
        case "$2" in
            update|create|delete|restart)
                log_blocked "$@"
                echo "ERROR: az containerapp modifications are blocked in sandbox mode" >&2
                exit 1
                ;;
            revision)
                case "$3" in
                    activate|deactivate)
                        log_blocked "$@"
                        echo "ERROR: az containerapp revision changes are blocked in sandbox mode" >&2
                        exit 1
                        ;;
                    *)
                        exec /usr/local/bin/az "$@" 2>/dev/null || exec /opt/homebrew/bin/az "$@"
                        ;;
                esac
                ;;
            *)
                exec /usr/local/bin/az "$@" 2>/dev/null || exec /opt/homebrew/bin/az "$@"
                ;;
        esac
        ;;
    webapp)
        case "$2" in
            create|delete|restart|deployment)
                log_blocked "$@"
                echo "ERROR: az webapp modifications are blocked in sandbox mode" >&2
                exit 1
                ;;
            *)
                exec /usr/local/bin/az "$@" 2>/dev/null || exec /opt/homebrew/bin/az "$@"
                ;;
        esac
        ;;
    keyvault)
        case "$2" in
            secret)
                case "$3" in
                    set|delete)
                        log_blocked "$@"
                        echo "ERROR: az keyvault secret modifications are blocked in sandbox mode" >&2
                        exit 1
                        ;;
                    *)
                        exec /usr/local/bin/az "$@" 2>/dev/null || exec /opt/homebrew/bin/az "$@"
                        ;;
                esac
                ;;
            *)
                exec /usr/local/bin/az "$@" 2>/dev/null || exec /opt/homebrew/bin/az "$@"
                ;;
        esac
        ;;
    *)
        # Allow other az commands (account show, login --help, etc.)
        exec /usr/local/bin/az "$@" 2>/dev/null || exec /opt/homebrew/bin/az "$@"
        ;;
esac
AZEOF
    chmod +x "$mock_bin/az"

    # =========================================================================
    # SECURITY LAYER 4: Git Worktree Isolation
    # =========================================================================
    echo -e "${YELLOW}[4/5] Creating git worktree...${NC}"

    if [[ -d "$project_dir/.git" ]] || git -C "$project_dir" rev-parse --git-dir &>/dev/null; then
        # Create worktree from project
        local branch_name="sandbox/$sandbox_id"
        (
            cd "$project_dir"
            git branch -D "$branch_name" 2>/dev/null || true
            git worktree add -b "$branch_name" "$project_worktree" HEAD 2>/dev/null || {
                # Fallback: create worktree without new branch
                git worktree add "$project_worktree" HEAD --detach
            }
        )
    else
        # Create fresh git repo
        mkdir -p "$project_worktree"
        (cd "$project_worktree" && git init -q && git commit --allow-empty -m "Sandbox init" -q)
    fi

    # Create .claude directory in worktree
    mkdir -p "$project_worktree/.claude"

    # =========================================================================
    # SECURITY LAYER 5: Environment Variables
    # =========================================================================
    echo -e "${YELLOW}[5/5] Preparing environment file...${NC}"

    cat > "$sandbox_root/env.sh" << ENVEOF
# Sandbox Environment Configuration
# Source this file: source $sandbox_root/env.sh

# Sandbox identification
export SANDBOX_MODE=true
export SANDBOX_ID="$sandbox_id"
export SANDBOX_DIR="$sandbox_root"
export CLAUDE_SANDBOX=true

# HOME override (CRITICAL: protects real credentials)
export REAL_HOME="\$HOME"
export HOME="$fake_home"

# PATH override (mock commands first)
export REAL_PATH="\$PATH"
export PATH="$mock_bin:\$PATH"

# Project directory
export SANDBOX_PROJECT="$project_worktree"

# SCRUB SENSITIVE ENVIRONMENT VARIABLES
unset ANTHROPIC_API_KEY
unset OPENAI_API_KEY
unset GITHUB_TOKEN
unset GH_TOKEN
unset AZURE_CLIENT_SECRET
unset AZURE_CLIENT_ID
unset AZURE_TENANT_ID
unset AWS_SECRET_ACCESS_KEY
unset AWS_ACCESS_KEY_ID
unset AWS_SESSION_TOKEN
unset DATABASE_URL
unset POSTGRES_PASSWORD
unset LOGFIRE_READ_TOKEN
unset LOGFIRE_WRITE_TOKEN
unset BULLHORN_CLIENT_SECRET

# Claude-specific
unset CLAUDE_ACCESS_TOKEN
unset CLAUDE_REFRESH_TOKEN
unset CLAUDE_API_KEY

echo "Sandbox environment loaded: $sandbox_id"
echo "  HOME=\$HOME"
echo "  PROJECT=\$SANDBOX_PROJECT"
echo "  Mock commands: gh, az"
ENVEOF

    # Create sandbox metadata
    cat > "$sandbox_root/metadata.json" << METAEOF
{
    "sandbox_id": "$sandbox_id",
    "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "project_source": "$project_dir",
    "project_worktree": "$project_worktree",
    "fake_home": "$fake_home",
    "mock_bin": "$mock_bin",
    "tmux_socket": "sandbox-$sandbox_id"
}
METAEOF

    # Create empty blocked commands log
    touch "$sandbox_root/blocked-commands.log"

    echo -e "\n${GREEN}Sandbox created successfully!${NC}"
    echo -e "\n${CYAN}Sandbox ID:${NC}       $sandbox_id"
    echo -e "${CYAN}Sandbox Root:${NC}     $sandbox_root"
    echo -e "${CYAN}Fake HOME:${NC}        $fake_home"
    echo -e "${CYAN}Project Worktree:${NC} $project_worktree"
    echo -e "${CYAN}tmux Socket:${NC}      sandbox-$sandbox_id"

    echo -e "\n${YELLOW}To use the sandbox:${NC}"
    echo -e "  1. Start tmux:     tmux -L sandbox-$sandbox_id new-session -s test"
    echo -e "  2. Load env:       source $sandbox_root/env.sh"
    echo -e "  3. Go to project:  cd \$SANDBOX_PROJECT"
    echo -e "  4. Run Claude:     claude --dangerously-skip-permissions"
    echo -e "\n${YELLOW}One-liner:${NC}"
    echo -e "  tmux -L sandbox-$sandbox_id new-session -s test 'source $sandbox_root/env.sh && cd \$SANDBOX_PROJECT && claude --dangerously-skip-permissions; exec bash'"

    # Return sandbox ID
    echo "$sandbox_id"
}

# =============================================================================
# Sandbox Destruction
# =============================================================================

destroy_sandbox() {
    local sandbox_id="$1"
    local sandbox_root="$SANDBOX_BASE/$sandbox_id"

    if [[ ! -d "$sandbox_root" ]]; then
        echo -e "${RED}Sandbox not found: $sandbox_id${NC}"
        return 1
    fi

    echo -e "${YELLOW}Destroying sandbox: $sandbox_id${NC}"

    # Kill tmux server
    tmux -L "sandbox-$sandbox_id" kill-server 2>/dev/null || true

    # Get project source for worktree cleanup
    local project_source=""
    if [[ -f "$sandbox_root/metadata.json" ]]; then
        project_source=$(jq -r '.project_source' "$sandbox_root/metadata.json" 2>/dev/null || true)
    fi

    # Remove git worktree
    if [[ -n "$project_source" ]] && [[ -d "$project_source/.git" ]]; then
        (
            cd "$project_source"
            git worktree remove --force "$sandbox_root/project" 2>/dev/null || true
            git branch -D "sandbox/$sandbox_id" 2>/dev/null || true
        )
    fi

    # Remove sandbox directory
    rm -rf "$sandbox_root"

    echo -e "${GREEN}Sandbox destroyed: $sandbox_id${NC}"
}

# =============================================================================
# List Sandboxes
# =============================================================================

list_sandboxes() {
    if [[ ! -d "$SANDBOX_BASE" ]]; then
        echo "No sandboxes found"
        return 0
    fi

    echo -e "${BLUE}Active Sandboxes:${NC}"
    echo ""

    local found=0
    for sandbox_dir in "$SANDBOX_BASE"/sandbox-*; do
        if [[ -d "$sandbox_dir" ]]; then
            found=1
            local sandbox_id=$(basename "$sandbox_dir")
            local metadata_file="$sandbox_dir/metadata.json"
            local created_at=""
            local project=""

            if [[ -f "$metadata_file" ]]; then
                created_at=$(jq -r '.created_at // "unknown"' "$metadata_file" 2>/dev/null)
                project=$(jq -r '.project_source // "unknown"' "$metadata_file" 2>/dev/null)
            fi

            # Check if tmux server is running
            local tmux_status="stopped"
            if tmux -L "sandbox-$sandbox_id" list-sessions &>/dev/null; then
                tmux_status="${GREEN}running${NC}"
            else
                tmux_status="${YELLOW}stopped${NC}"
            fi

            echo -e "  ${CYAN}$sandbox_id${NC}"
            echo -e "    Created:  $created_at"
            echo -e "    Project:  $project"
            echo -e "    tmux:     $tmux_status"
            echo ""
        fi
    done

    if [[ $found -eq 0 ]]; then
        echo "  No sandboxes found"
    fi
}

# =============================================================================
# Main
# =============================================================================

case "${1:-}" in
    create)
        shift
        create_sandbox "${1:-$(pwd)}"
        ;;
    destroy)
        shift
        if [[ -z "${1:-}" ]]; then
            echo "Usage: $0 destroy <sandbox-id>"
            exit 1
        fi
        destroy_sandbox "$1"
        ;;
    list)
        list_sandboxes
        ;;
    *)
        echo "Usage: $0 <command> [args]"
        echo ""
        echo "Commands:"
        echo "  create [project-dir]  Create a new sandbox (default: current dir)"
        echo "  destroy <sandbox-id>  Destroy a sandbox"
        echo "  list                  List all sandboxes"
        echo ""
        echo "Examples:"
        echo "  $0 create"
        echo "  $0 create /path/to/project"
        echo "  $0 destroy sandbox-1706438445-a1b2c3d4"
        echo "  $0 list"
        exit 1
        ;;
esac
