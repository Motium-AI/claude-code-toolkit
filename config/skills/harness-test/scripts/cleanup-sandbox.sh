#!/usr/bin/env bash
# =============================================================================
# Cleanup Harness Sandbox
# =============================================================================
#
# Destroys a harness sandbox and cleans up all associated resources.
#
# Usage:
#   ./cleanup-sandbox.sh <sandbox-id>
#
# =============================================================================

set -euo pipefail

SANDBOX_ID="${1:?Usage: $0 <sandbox-id>}"

SANDBOX_BASE="/tmp/claude-sandboxes"
SANDBOX_ROOT="$SANDBOX_BASE/$SANDBOX_ID"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

if [[ ! -d "$SANDBOX_ROOT" ]]; then
    echo -e "${RED}Sandbox not found: $SANDBOX_ID${NC}"
    exit 1
fi

echo -e "${YELLOW}Cleaning up harness sandbox: $SANDBOX_ID${NC}"

# Kill tmux server if running
if tmux -L "harness-$SANDBOX_ID" list-sessions &>/dev/null; then
    echo "Killing tmux server..."
    tmux -L "harness-$SANDBOX_ID" kill-server 2>/dev/null || true
fi

# Get project source for worktree cleanup
PROJECT_SOURCE=""
if [[ -f "$SANDBOX_ROOT/metadata.json" ]]; then
    PROJECT_SOURCE=$(jq -r '.project_source // empty' "$SANDBOX_ROOT/metadata.json" 2>/dev/null || true)
fi

# Remove git worktree
if [[ -n "$PROJECT_SOURCE" ]] && [[ -d "$PROJECT_SOURCE/.git" ]]; then
    echo "Removing git worktree..."
    (
        cd "$PROJECT_SOURCE"
        git worktree remove --force "$SANDBOX_ROOT/project" 2>/dev/null || true
        git branch -D "harness-sandbox/$SANDBOX_ID" 2>/dev/null || true
    )
fi

# Remove sandbox directory
echo "Removing sandbox directory..."
rm -rf "$SANDBOX_ROOT"

echo -e "${GREEN}Sandbox cleaned up: $SANDBOX_ID${NC}"
