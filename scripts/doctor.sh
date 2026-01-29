#!/bin/bash
#
# Claude Code Toolkit Doctor
#
# Comprehensive diagnostics for troubleshooting hook and skill issues.
# Run this when /appfix or /godo isn't working as expected.
#
# Usage:
#   ./scripts/doctor.sh              # Run all diagnostics
#   ./scripts/doctor.sh --project    # Check project-specific issues
#   ./scripts/doctor.sh --fix        # Attempt automatic fixes
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Parse arguments
FIX_MODE=false
PROJECT_MODE=false
PROJECT_DIR="."

while [[ $# -gt 0 ]]; do
    case $1 in
        --fix)
            FIX_MODE=true
            shift
            ;;
        --project)
            PROJECT_MODE=true
            PROJECT_DIR="${2:-.}"
            shift 2 2>/dev/null || shift
            ;;
        *)
            PROJECT_DIR="$1"
            shift
            ;;
    esac
done

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  CLAUDE CODE TOOLKIT DOCTOR${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "Timestamp: $(date -Iseconds)"
echo -e "User: $(whoami)"
echo -e "Host: $(hostname)"
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 1: ENVIRONMENT CHECKS
# ═══════════════════════════════════════════════════════════════════════════

echo -e "${BLUE}1. ENVIRONMENT${NC}"
echo "───────────────────────────────────────────────────────────────"

# Python
echo -n "  Python 3: "
if command -v python3 &> /dev/null; then
    PYTHON_VERSION_FULL=$(python3 --version 2>&1)
    PYTHON_VERSION_NUM=$(echo "$PYTHON_VERSION_FULL" | cut -d' ' -f2)
    PY_MAJOR=$(echo "$PYTHON_VERSION_NUM" | cut -d. -f1)
    PY_MINOR=$(echo "$PYTHON_VERSION_NUM" | cut -d. -f2)
    if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 8 ]; }; then
        echo -e "${RED}$PYTHON_VERSION_FULL (need 3.8+)${NC}"
        echo "    → Upgrade Python: https://www.python.org/downloads/"
    else
        echo -e "${GREEN}$PYTHON_VERSION_FULL${NC}"
    fi
else
    echo -e "${RED}NOT FOUND${NC}"
    echo "    → Install Python 3: https://www.python.org/downloads/"
fi

# Git
echo -n "  Git: "
if command -v git &> /dev/null; then
    GIT_VERSION=$(git --version | cut -d' ' -f3)
    echo -e "${GREEN}$GIT_VERSION${NC}"
else
    echo -e "${RED}NOT FOUND${NC}"
fi

# Claude Code
echo -n "  Claude Code: "
if command -v claude &> /dev/null; then
    CLAUDE_VERSION=$(claude --version 2>&1 | head -1 || echo "installed")
    echo -e "${GREEN}$CLAUDE_VERSION${NC}"
else
    echo -e "${RED}NOT FOUND${NC}"
    echo "    → Install: https://claude.ai/code"
fi

echo ""

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 1b: OPTIONAL TOOLS
# ═══════════════════════════════════════════════════════════════════════════

echo -e "${BLUE}1b. OPTIONAL TOOLS${NC}"
echo "───────────────────────────────────────────────────────────────"

# Surf CLI
echo -n "  Surf CLI: "
if command -v surf &> /dev/null; then
    echo -e "${GREEN}installed${NC}"
else
    echo -e "${YELLOW}not found${NC}"
    echo "    → Needed for /appfix web verification"
    echo "    → Install: npm install -g @nicobailon/surf-cli"
fi

# GitHub CLI
echo -n "  GitHub CLI (gh): "
if command -v gh &> /dev/null; then
    GH_VERSION=$(gh --version 2>&1 | head -1 | cut -d' ' -f3)
    echo -e "${GREEN}$GH_VERSION${NC}"
else
    echo -e "${YELLOW}not found${NC}"
    echo "    → Needed for PR creation and deployment workflows"
    echo "    → Install: https://cli.github.com/"
fi

# jq (useful for debugging state files)
echo -n "  jq: "
if command -v jq &> /dev/null; then
    JQ_VERSION=$(jq --version 2>&1)
    echo -e "${GREEN}$JQ_VERSION${NC}"
else
    echo -e "${YELLOW}not found${NC}"
    echo "    → Useful for inspecting state files during debugging"
fi

echo ""

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 2: TOOLKIT INSTALLATION
# ═══════════════════════════════════════════════════════════════════════════

echo -e "${BLUE}2. TOOLKIT INSTALLATION${NC}"
echo "───────────────────────────────────────────────────────────────"

CLAUDE_DIR="$HOME/.claude"

# Check ~/.claude exists
echo -n "  ~/.claude directory: "
if [ -d "$CLAUDE_DIR" ]; then
    echo -e "${GREEN}EXISTS${NC}"
else
    echo -e "${RED}MISSING${NC}"
    if [ "$FIX_MODE" = true ]; then
        mkdir -p "$CLAUDE_DIR"
        echo "    → Created ~/.claude"
    fi
fi

# Check symlinks
check_symlink() {
    local NAME=$1
    local SPATH="$CLAUDE_DIR/$NAME"
    echo -n "  $NAME: "
    if [ -L "$SPATH" ]; then
        # Use ls -l to get symlink target (works on both macOS and Linux)
        TARGET=$(ls -l "$SPATH" 2>/dev/null | sed 's/.*-> //')
        if [ -e "$SPATH" ]; then
            echo -e "${GREEN}→ $TARGET${NC}"
        else
            echo -e "${RED}BROKEN SYMLINK → $TARGET${NC}"
        fi
    elif [ -e "$SPATH" ]; then
        echo -e "${YELLOW}EXISTS (not symlink)${NC}"
    else
        echo -e "${RED}MISSING${NC}"
    fi
}

check_symlink "settings.json"
check_symlink "hooks"
check_symlink "commands"
check_symlink "skills"

echo ""

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 3: HOOK CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

echo -e "${BLUE}3. HOOK CONFIGURATION${NC}"
echo "───────────────────────────────────────────────────────────────"

SETTINGS="$CLAUDE_DIR/settings.json"

if [ ! -f "$SETTINGS" ]; then
    echo -e "  ${RED}settings.json not found!${NC}"
else
    # Check for each hook event type
    for event in SessionStart Stop PreToolUse PostToolUse PermissionRequest UserPromptSubmit; do
        echo -n "  $event: "
        COUNT=$(grep -c "\"$event\"" "$SETTINGS" 2>/dev/null || echo "0")
        if [ "$COUNT" -gt 0 ]; then
            echo -e "${GREEN}configured${NC}"
        else
            echo -e "${YELLOW}not configured${NC}"
        fi
    done
fi

echo ""

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 4: HOOK SCRIPTS
# ═══════════════════════════════════════════════════════════════════════════

echo -e "${BLUE}4. HOOK SCRIPTS${NC}"
echo "───────────────────────────────────────────────────────────────"

HOOKS_DIR="$CLAUDE_DIR/hooks"

if [ ! -d "$HOOKS_DIR" ]; then
    echo -e "  ${RED}Hooks directory not found!${NC}"
else
    # Check key hook files
    KEY_HOOKS=(
        "_common.py:Shared utilities"
        "appfix-auto-approve.py:Auto-approval for appfix/godo"
        "plan-mode-enforcer.py:Blocks Edit/Write on first iteration"
        "stop-validator.py:Completion checkpoint validation"
        "checkpoint-invalidator.py:Resets stale checkpoint flags"
        "session-snapshot.py:Captures session start state"
    )

    for entry in "${KEY_HOOKS[@]}"; do
        HOOK="${entry%%:*}"
        DESC="${entry#*:}"
        echo -n "  $HOOK: "
        if [ -f "$HOOKS_DIR/$HOOK" ]; then
            # Check syntax
            if python3 -c "import ast; ast.parse(open('$HOOKS_DIR/$HOOK').read())" 2>/dev/null; then
                # Check if executable
                if [ -x "$HOOKS_DIR/$HOOK" ]; then
                    echo -e "${GREEN}OK${NC}"
                else
                    echo -e "${YELLOW}not executable${NC}"
                    if [ "$FIX_MODE" = true ]; then
                        chmod +x "$HOOKS_DIR/$HOOK"
                        echo "    → Fixed: made executable"
                    fi
                fi
            else
                echo -e "${RED}SYNTAX ERROR${NC}"
                echo "    → Run: python3 -c \"import ast; ast.parse(open('$HOOKS_DIR/$HOOK').read())\""
            fi
        else
            echo -e "${RED}MISSING${NC}"
        fi
    done

    # Test _common.py imports
    echo ""
    echo -n "  _common.py imports: "
    if python3 -c "import sys; sys.path.insert(0, '$HOOKS_DIR'); from _common import is_autonomous_mode_active" 2>/dev/null; then
        echo -e "${GREEN}OK${NC}"
    else
        echo -e "${RED}FAILED${NC}"
        echo "    → Run: python3 -c \"import sys; sys.path.insert(0, '$HOOKS_DIR'); from _common import is_autonomous_mode_active\""
    fi
fi

echo ""

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 5: STATE FILE DETECTION
# ═══════════════════════════════════════════════════════════════════════════

echo -e "${BLUE}5. STATE FILE DETECTION${NC}"
echo "───────────────────────────────────────────────────────────────"

# Check user-level state files
echo "  User-level (~/.claude/):"
for STATE_FILE in appfix-state.json godo-state.json; do
    echo -n "    $STATE_FILE: "
    if [ -f "$CLAUDE_DIR/$STATE_FILE" ]; then
        echo -e "${GREEN}EXISTS${NC}"
        # Show key fields
        if command -v jq &> /dev/null; then
            ORIGIN=$(jq -r '.origin_project // "N/A"' "$CLAUDE_DIR/$STATE_FILE" 2>/dev/null)
            echo "      origin_project: $ORIGIN"
        fi
    else
        echo -e "${YELLOW}not present${NC}"
    fi
done

# Check project-level state files
echo ""
echo "  Project-level ($PROJECT_DIR/.claude/):"
PROJECT_CLAUDE="$PROJECT_DIR/.claude"
if [ -d "$PROJECT_CLAUDE" ]; then
    for STATE_FILE in appfix-state.json godo-state.json; do
        echo -n "    $STATE_FILE: "
        if [ -f "$PROJECT_CLAUDE/$STATE_FILE" ]; then
            echo -e "${GREEN}EXISTS${NC}"
            # Show key fields
            if command -v jq &> /dev/null; then
                ITERATION=$(jq -r '.iteration // "N/A"' "$PROJECT_CLAUDE/$STATE_FILE" 2>/dev/null)
                PLAN_MODE=$(jq -r '.plan_mode_completed // "N/A"' "$PROJECT_CLAUDE/$STATE_FILE" 2>/dev/null)
                echo "      iteration: $ITERATION, plan_mode_completed: $PLAN_MODE"
            fi
        else
            echo -e "${YELLOW}not present${NC}"
        fi
    done
else
    echo -e "    ${YELLOW}No .claude/ directory in project${NC}"
fi

# Test detection function
echo ""
echo -n "  Detection test: "
if [ -d "$HOOKS_DIR" ]; then
    TEST_DIR=$(mktemp -d)
    mkdir -p "$TEST_DIR/.claude"
    cat > "$TEST_DIR/.claude/appfix-state.json" <<EOF
{
  "iteration": 1,
  "plan_mode_completed": true,
  "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

    RESULT=$(python3 -c "
import sys
sys.path.insert(0, '$HOOKS_DIR')
from _common import is_autonomous_mode_active
print(is_autonomous_mode_active('$TEST_DIR'))
" 2>&1)

    rm -rf "$TEST_DIR"

    if [ "$RESULT" = "True" ]; then
        echo -e "${GREEN}WORKING${NC}"
    else
        echo -e "${RED}FAILED (got: $RESULT)${NC}"
    fi
else
    echo -e "${YELLOW}skipped (no hooks dir)${NC}"
fi

echo ""

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 6: AUTO-APPROVAL HOOK TEST
# ═══════════════════════════════════════════════════════════════════════════

echo -e "${BLUE}6. AUTO-APPROVAL HOOK${NC}"
echo "───────────────────────────────────────────────────────────────"

AUTO_APPROVE="$HOOKS_DIR/appfix-auto-approve.py"

if [ ! -f "$AUTO_APPROVE" ]; then
    echo -e "  ${RED}appfix-auto-approve.py not found!${NC}"
else
    # Test with state file present
    TEST_DIR=$(mktemp -d)
    mkdir -p "$TEST_DIR/.claude"
    cat > "$TEST_DIR/.claude/appfix-state.json" <<EOF
{
  "iteration": 1,
  "plan_mode_completed": true,
  "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

    echo -n "  With state file (empty stdin): "
    RESULT=$(cd "$TEST_DIR" && echo "" | python3 "$AUTO_APPROVE" 2>&1)
    if echo "$RESULT" | grep -q '"behavior": "allow"'; then
        echo -e "${GREEN}ALLOWS${NC}"
    else
        echo -e "${RED}FAILS${NC}"
        echo "    Output: $RESULT"
    fi

    echo -n "  With state file (JSON stdin): "
    RESULT=$(cd "$TEST_DIR" && echo '{"cwd": "'$TEST_DIR'"}' | python3 "$AUTO_APPROVE" 2>&1)
    if echo "$RESULT" | grep -q '"behavior": "allow"'; then
        echo -e "${GREEN}ALLOWS${NC}"
    else
        echo -e "${RED}FAILS${NC}"
        echo "    Output: $RESULT"
    fi

    rm -rf "$TEST_DIR"

    # Test without state file
    TEST_DIR=$(mktemp -d)
    echo -n "  Without state file: "
    RESULT=$(cd "$TEST_DIR" && echo "" | python3 "$AUTO_APPROVE" 2>&1)
    if [ -z "$RESULT" ]; then
        echo -e "${GREEN}SILENT (passthrough)${NC}"
    else
        echo -e "${YELLOW}OUTPUT: $RESULT${NC}"
    fi
    rm -rf "$TEST_DIR"
fi

echo ""

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 7: PLAN MODE ENFORCER TEST
# ═══════════════════════════════════════════════════════════════════════════

echo -e "${BLUE}7. PLAN MODE ENFORCER${NC}"
echo "───────────────────────────────────────────────────────────────"

PLAN_ENFORCER="$HOOKS_DIR/plan-mode-enforcer.py"

if [ ! -f "$PLAN_ENFORCER" ]; then
    echo -e "  ${RED}plan-mode-enforcer.py not found!${NC}"
else
    # Test with plan_mode_completed: false
    TEST_DIR=$(mktemp -d)
    mkdir -p "$TEST_DIR/.claude"
    cat > "$TEST_DIR/.claude/appfix-state.json" <<EOF
{
  "iteration": 1,
  "plan_mode_completed": false,
  "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

    echo -n "  With plan_mode_completed=false: "
    RESULT=$(echo '{"tool_name": "Edit", "cwd": "'$TEST_DIR'"}' | python3 "$PLAN_ENFORCER" 2>&1)
    if echo "$RESULT" | grep -q 'permissionDecision'; then
        echo -e "${GREEN}BLOCKS (as expected)${NC}"
    else
        echo -e "${YELLOW}ALLOWS (unexpected for iteration 1)${NC}"
    fi

    # Test with plan_mode_completed: true
    cat > "$TEST_DIR/.claude/appfix-state.json" <<EOF
{
  "iteration": 1,
  "plan_mode_completed": true,
  "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

    echo -n "  With plan_mode_completed=true: "
    RESULT=$(echo '{"tool_name": "Edit", "cwd": "'$TEST_DIR'"}' | python3 "$PLAN_ENFORCER" 2>&1)
    if [ -z "$RESULT" ]; then
        echo -e "${GREEN}ALLOWS (passthrough)${NC}"
    else
        echo -e "${YELLOW}OUTPUT: $RESULT${NC}"
    fi

    rm -rf "$TEST_DIR"
fi

echo ""

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 8: DEBUG LOG
# ═══════════════════════════════════════════════════════════════════════════

echo -e "${BLUE}8. DEBUG LOG${NC}"
echo "───────────────────────────────────────────────────────────────"

DEBUG_LOG="/tmp/claude-hooks-debug.log"

echo -n "  Debug log location: "
if [ -f "$DEBUG_LOG" ]; then
    SIZE=$(ls -lh "$DEBUG_LOG" | awk '{print $5}')
    LINES=$(wc -l < "$DEBUG_LOG")
    echo -e "${GREEN}$DEBUG_LOG ($SIZE, $LINES lines)${NC}"
    echo ""
    echo "  Last 10 entries:"
    tail -50 "$DEBUG_LOG" | grep -A5 "^===" | tail -20 | sed 's/^/    /'
else
    echo -e "${YELLOW}not found (no hook errors logged)${NC}"
fi

echo ""

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 9: PROJECT READINESS (--project mode)
# ═══════════════════════════════════════════════════════════════════════════

if [ "$PROJECT_MODE" = true ]; then
    echo -e "${BLUE}9. PROJECT READINESS${NC}"
    echo "───────────────────────────────────────────────────────────────"
    echo "  Project: $(cd "$PROJECT_DIR" && pwd)"
    echo ""

    # Project type detection
    echo -n "  Project type: "
    TYPES=""
    [ -f "$PROJECT_DIR/package.json" ] && TYPES="${TYPES}Node.js "
    [ -f "$PROJECT_DIR/pyproject.toml" ] || [ -f "$PROJECT_DIR/setup.py" ] && TYPES="${TYPES}Python "
    [ -f "$PROJECT_DIR/tsconfig.json" ] && TYPES="${TYPES}TypeScript "
    [ -f "$PROJECT_DIR/go.mod" ] && TYPES="${TYPES}Go "
    [ -f "$PROJECT_DIR/Cargo.toml" ] && TYPES="${TYPES}Rust "
    [ -f "$PROJECT_DIR/next.config.js" ] || [ -f "$PROJECT_DIR/next.config.mjs" ] || [ -f "$PROJECT_DIR/next.config.ts" ] && TYPES="${TYPES}Next.js "
    [ -f "$PROJECT_DIR/docker-compose.yml" ] || [ -f "$PROJECT_DIR/docker-compose.yaml" ] && TYPES="${TYPES}Docker "
    if [ -n "$TYPES" ]; then
        echo -e "${GREEN}$TYPES${NC}"
    else
        echo -e "${YELLOW}unknown${NC}"
    fi

    # Documentation files
    echo ""
    echo "  Documentation files:"

    check_project_file() {
        local FILE=$1
        local DESC=$2
        local REQUIRED=$3
        echo -n "    $FILE: "
        if [ -f "$PROJECT_DIR/$FILE" ]; then
            echo -e "${GREEN}exists${NC}"
        elif [ "$REQUIRED" = "required" ]; then
            echo -e "${RED}MISSING${NC} ($DESC)"
        else
            echo -e "${YELLOW}not found${NC} ($DESC)"
        fi
    }

    check_project_file "CLAUDE.md" "project conventions for Claude Code" "recommended"
    check_project_file "docs/index.md" "documentation hub" "recommended"
    check_project_file ".claude/MEMORIES.md" "session context notes" "optional"
    check_project_file "docs/TECHNICAL_OVERVIEW.md" "architecture documentation" "optional"

    # Appfix-specific files
    echo ""
    echo "  /appfix readiness:"

    # Service topology
    echo -n "    service-topology.md: "
    if [ -f "$PROJECT_DIR/.claude/skills/appfix/references/service-topology.md" ]; then
        echo -e "${GREEN}exists${NC}"
    elif [ -f "$HOME/.claude/skills/appfix/references/service-topology.md" ]; then
        echo -e "${GREEN}exists (user-level)${NC}"
    else
        echo -e "${YELLOW}not found${NC} (needed for /appfix web smoke URLs)"
    fi

    # Environment file
    echo -n "    .env file: "
    if [ -f "$PROJECT_DIR/.env" ]; then
        # Check for common credential vars (names only, not values)
        ENV_VARS=""
        grep -q "TEST_EMAIL" "$PROJECT_DIR/.env" 2>/dev/null && ENV_VARS="${ENV_VARS}TEST_EMAIL "
        grep -q "TEST_PASSWORD" "$PROJECT_DIR/.env" 2>/dev/null && ENV_VARS="${ENV_VARS}TEST_PASSWORD "
        grep -q "LOGFIRE_READ_TOKEN" "$PROJECT_DIR/.env" 2>/dev/null && ENV_VARS="${ENV_VARS}LOGFIRE_READ_TOKEN "
        if [ -n "$ENV_VARS" ]; then
            echo -e "${GREEN}exists${NC} (has: $ENV_VARS)"
        else
            echo -e "${GREEN}exists${NC}"
        fi
    else
        echo -e "${YELLOW}not found${NC} (credentials for testing)"
    fi

    echo ""
fi

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 10: RECOMMENDATIONS
# ═══════════════════════════════════════════════════════════════════════════

echo -e "${BLUE}10. RECOMMENDATIONS${NC}"
echo "───────────────────────────────────────────────────────────────"

# Collect issues
ISSUES=()

if [ ! -d "$CLAUDE_DIR" ]; then
    ISSUES+=("Run the installer: ./scripts/install.sh")
fi

if [ ! -f "$SETTINGS" ]; then
    ISSUES+=("settings.json missing - reinstall toolkit")
fi

if [ ! -d "$HOOKS_DIR" ]; then
    ISSUES+=("hooks directory missing - reinstall toolkit")
fi

# Check for common issue: state file in wrong location
if [ -f "$HOME/.claude/appfix-state.json" ] && [ ! -f "$PROJECT_CLAUDE/appfix-state.json" ] 2>/dev/null; then
    ISSUES+=("User-level state exists but project-level missing. Create: mkdir -p .claude && echo '{\"iteration\": 1, \"plan_mode_completed\": false}' > .claude/appfix-state.json")
fi

if [ ${#ISSUES[@]} -eq 0 ]; then
    echo -e "  ${GREEN}No issues detected!${NC}"
    echo ""
    echo "  If hooks still aren't working:"
    echo "    1. Restart Claude Code (hooks are captured at session start)"
    echo "    2. Check that state files exist when running /appfix or /godo"
    echo "    3. Review debug log: tail -f /tmp/claude-hooks-debug.log"
else
    for issue in "${ISSUES[@]}"; do
        echo -e "  ${YELLOW}→ $issue${NC}"
    done
fi

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  DOCTOR COMPLETE${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# Exit with error if issues found
[ ${#ISSUES[@]} -eq 0 ] && exit 0 || exit 1
