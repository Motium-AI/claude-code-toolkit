#!/usr/bin/env bash
# =============================================================================
# Skill Tester - Test Claude Code skills in isolated sessions
# =============================================================================
#
# Usage:
#   bash test-skill.sh <skill-trigger> "<test-prompt>"
#   bash test-skill.sh /heavy "What database should I use?"
#   bash test-skill.sh --list                    # List available skills
#   bash test-skill.sh --dry-run /heavy "..."   # Show what would run
#
# Examples:
#   bash test-skill.sh /heavy "Redis vs PostgreSQL?"
#   bash test-skill.sh /godo "Create hello.py"
#   bash test-skill.sh /frontend-design "Create a button"
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

# Config
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
MODEL="${SKILL_TEST_MODEL:-haiku}"
TIMEOUT="${SKILL_TEST_TIMEOUT:-180}"
DRY_RUN=false
VERBOSE=false

# Parse args
POSITIONAL_ARGS=()
for arg in "$@"; do
    case $arg in
        --dry-run) DRY_RUN=true ;;
        --verbose|-v) VERBOSE=true ;;
        --model=*) MODEL="${arg#*=}" ;;
        --timeout=*) TIMEOUT="${arg#*=}" ;;
        --list)
            echo "Available skills:"
            for skill_dir in "$SKILLS_DIR"/*/; do
                if [[ -f "${skill_dir}SKILL.md" ]]; then
                    skill_name=$(basename "$skill_dir")
                    # Extract description from SKILL.md
                    desc=$(grep -m1 "^description:" "${skill_dir}SKILL.md" 2>/dev/null | cut -d: -f2- | sed 's/^ *//' | head -c 60)
                    echo -e "  ${GREEN}/${skill_name}${NC} - ${desc}..."
                fi
            done
            exit 0
            ;;
        --help|-h)
            echo "Usage: $0 [options] <skill-trigger> \"<test-prompt>\""
            echo ""
            echo "Options:"
            echo "  --dry-run      Show what would run without executing"
            echo "  --verbose      Show full output"
            echo "  --model=MODEL  Model to use (default: haiku)"
            echo "  --timeout=SEC  Timeout in seconds (default: 180)"
            echo "  --list         List available skills"
            echo ""
            echo "Examples:"
            echo "  $0 /heavy \"Redis vs PostgreSQL?\""
            echo "  $0 --model=sonnet /godo \"Create hello.py\""
            exit 0
            ;;
        -*) echo "Unknown option: $arg"; exit 1 ;;
        *) POSITIONAL_ARGS+=("$arg") ;;
    esac
done

# Validate args
if [[ ${#POSITIONAL_ARGS[@]} -lt 2 ]]; then
    echo -e "${RED}Error: Missing arguments${NC}"
    echo "Usage: $0 <skill-trigger> \"<test-prompt>\""
    echo "Example: $0 /heavy \"What database should I use?\""
    exit 1
fi

SKILL_TRIGGER="${POSITIONAL_ARGS[0]}"
TEST_PROMPT="${POSITIONAL_ARGS[1]}"

# =============================================================================
# Main
# =============================================================================

log_header() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

log_header "Skill Tester"
echo -e "Skill:   ${CYAN}${SKILL_TRIGGER}${NC}"
echo -e "Prompt:  ${TEST_PROMPT:0:60}..."
echo -e "Model:   ${MODEL}"
echo -e "Timeout: ${TIMEOUT}s"
echo -e "Dry run: ${DRY_RUN}"

# Pre-flight checks
if ! command -v claude &>/dev/null; then
    echo -e "${RED}ERROR: 'claude' CLI not found${NC}"
    exit 1
fi

if ! command -v jq &>/dev/null; then
    echo -e "${YELLOW}WARNING: 'jq' not found - JSON parsing will be limited${NC}"
fi

# Create isolated test environment
TESTDIR=$(mktemp -d "/tmp/skill-test-${SKILL_TRIGGER//\//-}-XXXXXX")
echo -e "\nTest dir: ${TESTDIR}"

# Setup test environment
cd "$TESTDIR"
git init -q && git commit --allow-empty -m "init" -q
mkdir -p src .claude
echo '# Test project' > README.md

# Create state files if needed for autonomous skills
SKILL_NAME="${SKILL_TRIGGER#/}"
case "$SKILL_NAME" in
    godo|appfix)
        echo -e "${YELLOW}Creating ${SKILL_NAME} state file...${NC}"
        cat > ".claude/${SKILL_NAME}-state.json" << EOF
{
    "iteration": 1,
    "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "plan_mode_completed": true,
    "parallel_mode": false,
    "agent_id": null,
    "worktree_path": null,
    "coordinator": true,
    "task": "$TEST_PROMPT"
}
EOF
        ;;
esac

# Build full prompt
FULL_PROMPT="${SKILL_TRIGGER} ${TEST_PROMPT}"

if $DRY_RUN; then
    echo -e "\n${YELLOW}DRY RUN - Would execute:${NC}"
    echo -e "  cd $TESTDIR"
    echo -e "  timeout $TIMEOUT claude -p \\"
    echo -e "    --model $MODEL \\"
    echo -e "    --no-session-persistence \\"
    echo -e "    --output-format json \\"
    echo -e "    --dangerously-skip-permissions \\"
    echo -e "    \"$FULL_PROMPT\""
    echo -e "\n${CYAN}Test directory preserved at: $TESTDIR${NC}"
    exit 0
fi

# Run the test
echo -e "\n${CYAN}Running skill test...${NC}"
START_TIME=$(date +%s)

timeout "$TIMEOUT" claude -p \
    --model "$MODEL" \
    --no-session-persistence \
    --output-format json \
    --dangerously-skip-permissions \
    "$FULL_PROMPT" \
    2>"$TESTDIR/stderr.log" \
    >"$TESTDIR/stdout.log" \
    || EXIT_CODE=$?

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

EXIT_CODE=${EXIT_CODE:-0}

# Report results
log_header "Results"

echo -e "Duration:  ${DURATION}s"
echo -e "Exit code: ${EXIT_CODE}"

# Check for created files
CREATED_FILES=$(find "$TESTDIR" -type f -newer "$TESTDIR/.git" ! -path "$TESTDIR/.git/*" ! -name "*.log" 2>/dev/null | head -10)
if [[ -n "$CREATED_FILES" ]]; then
    echo -e "\n${GREEN}Created files:${NC}"
    echo "$CREATED_FILES" | while read -r f; do
        echo -e "  $f"
    done
fi

# Show output summary
if [[ -f "$TESTDIR/stdout.log" ]] && [[ -s "$TESTDIR/stdout.log" ]]; then
    if command -v jq &>/dev/null; then
        RESULT=$(jq -r '.result // .error // "No result field"' "$TESTDIR/stdout.log" 2>/dev/null | head -c 500)
    else
        RESULT=$(head -c 500 "$TESTDIR/stdout.log")
    fi

    echo -e "\n${CYAN}Output preview:${NC}"
    echo "$RESULT" | head -20

    if $VERBOSE; then
        echo -e "\n${CYAN}Full stdout:${NC}"
        cat "$TESTDIR/stdout.log"
    fi
fi

# Show errors
if [[ -f "$TESTDIR/stderr.log" ]] && [[ -s "$TESTDIR/stderr.log" ]]; then
    echo -e "\n${YELLOW}Stderr:${NC}"
    cat "$TESTDIR/stderr.log" | head -20
fi

# Pass/Fail determination
if [[ $EXIT_CODE -eq 0 ]]; then
    echo -e "\n${GREEN}TEST PASSED${NC}"
else
    echo -e "\n${RED}TEST FAILED (exit code: $EXIT_CODE)${NC}"
fi

# Cleanup prompt
echo -e "\n${CYAN}Test artifacts at: $TESTDIR${NC}"
echo -e "Cleanup with: rm -rf $TESTDIR"
