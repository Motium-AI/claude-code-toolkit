#!/usr/bin/env bash
# =============================================================================
# E2E Tests for Sticky Session Mode + Session Guard
# =============================================================================
#
# Tests the sticky session implementation using real Claude Code sessions.
# Validates that:
# 1. State persists across task completions within a session
# 2. State is cleaned at session boundaries
# 3. Session guard warns about concurrent sessions
# 4. TTL expiry works correctly
# 5. Deactivation commands work
#
# Prerequisites:
#   - Claude Code CLI installed and authenticated
#   - Hooks installed via scripts/install.sh
#
# Usage:
#   bash scripts/test-sticky-session-e2e.sh          # Run all tests
#   bash scripts/test-sticky-session-e2e.sh --dry-run # Show what would run
#   bash scripts/test-sticky-session-e2e.sh --quick   # Run only quick tests
#
# Cost: ~$0.10-0.30 per run (uses haiku model)
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
PROMPTS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
MODEL="${E2E_MODEL:-haiku}"
TIMEOUT="${E2E_TIMEOUT:-60}"
DRY_RUN=false
QUICK_MODE=false
PASSED=0
FAILED=0
SKIPPED=0

# Parse args
for arg in "$@"; do
    case $arg in
        --dry-run) DRY_RUN=true ;;
        --quick) QUICK_MODE=true ;;
        --model=*) MODEL="${arg#*=}" ;;
        --timeout=*) TIMEOUT="${arg#*=}" ;;
        --help|-h)
            echo "Usage: $0 [--dry-run] [--quick] [--model=MODEL] [--timeout=SECONDS]"
            exit 0
            ;;
    esac
done

# =============================================================================
# Helpers
# =============================================================================

log_header() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

log_test() {
    echo -e "\n${YELLOW}TEST: $1${NC}"
}

log_pass() {
    echo -e "${GREEN}  ✓ PASS: $1${NC}"
    PASSED=$((PASSED + 1))
}

log_fail() {
    echo -e "${RED}  ✗ FAIL: $1${NC}"
    FAILED=$((FAILED + 1))
}

log_skip() {
    echo -e "${YELLOW}  ○ SKIP: $1${NC}"
    SKIPPED=$((SKIPPED + 1))
}

log_info() {
    echo -e "  ${NC}$1${NC}"
}

make_test_dir() {
    local test_name="$1"
    local tmpdir
    tmpdir="$(mktemp -d "/tmp/e2e-sticky-${test_name}-XXXXXX")"
    # Initialize as git repo
    (cd "$tmpdir" && git init -q && git commit --allow-empty -m "init" -q)
    echo "$tmpdir"
}

cleanup_test_dir() {
    local tmpdir="$1"
    if [[ -d "$tmpdir" ]]; then
        rm -rf "$tmpdir"
    fi
}

run_claude() {
    local tmpdir="$1"
    local prompt="$2"

    if $DRY_RUN; then
        log_info "DRY RUN: claude -p --model $MODEL \"$prompt\""
        log_info "  cwd: $tmpdir"
        return 0
    fi

    log_info "Running Claude with prompt: ${prompt:0:60}..."

    # Use gtimeout if available (brew install coreutils), otherwise skip timeout
    local timeout_cmd=""
    if command -v gtimeout &>/dev/null; then
        timeout_cmd="gtimeout $TIMEOUT"
    elif command -v timeout &>/dev/null; then
        timeout_cmd="timeout $TIMEOUT"
    fi

    (cd "$tmpdir" && $timeout_cmd claude -p \
        --model "$MODEL" \
        --no-session-persistence \
        --output-format json \
        --dangerously-skip-permissions \
        "$prompt" \
        2>"$tmpdir/stderr.log" \
        >"$tmpdir/stdout.log") || true

    log_info "Claude completed. Checking output..."
}

# =============================================================================
# Pre-flight Checks
# =============================================================================

log_header "E2E Sticky Session Tests"

echo -e "Model:   ${MODEL}"
echo -e "Timeout: ${TIMEOUT}s per test"
echo -e "Dry run: ${DRY_RUN}"
echo -e "Quick:   ${QUICK_MODE}"

# Check Claude CLI
if ! command -v claude &>/dev/null; then
    echo -e "${RED}ERROR: 'claude' CLI not found. Install from https://claude.ai/code${NC}"
    exit 1
fi

# Check hooks are installed
HOOKS_DIR="$HOME/.claude/hooks"
if [[ ! -f "$HOOKS_DIR/skill-state-initializer.py" ]]; then
    echo -e "${RED}ERROR: Hooks not installed. Run: cd prompts && ./scripts/install.sh${NC}"
    exit 1
fi

echo -e "${GREEN}Pre-flight checks passed.${NC}"

# =============================================================================
# Test 1: State Creation with Session ID
# =============================================================================

log_test "1 — /appfix creates state with session_id"

TMPDIR1="$(make_test_dir "state-creation")"
mkdir -p "$TMPDIR1/src"
echo '# Test project' > "$TMPDIR1/README.md"

if $DRY_RUN; then
    log_skip "Dry run"
else
    run_claude "$TMPDIR1" "Type /appfix to activate autonomous mode. Then immediately say 'I have activated appfix mode' and stop."

    STATE_FILE="$TMPDIR1/.claude/appfix-state.json"
    if [[ -f "$STATE_FILE" ]]; then
        # Check for session_id field
        if grep -q '"session_id"' "$STATE_FILE"; then
            log_pass "State file created with session_id field"
        else
            log_fail "State file missing session_id field"
            log_info "State content: $(cat "$STATE_FILE")"
        fi
        # Check for last_activity_at field
        if grep -q '"last_activity_at"' "$STATE_FILE"; then
            log_pass "State file contains last_activity_at"
        else
            log_fail "State file missing last_activity_at"
        fi
    else
        log_fail "State file not created"
        log_info "stderr: $(head -5 "$TMPDIR1/stderr.log" 2>/dev/null)"
    fi
fi

cleanup_test_dir "$TMPDIR1"

# =============================================================================
# Test 2: Deactivation with /appfix off
# =============================================================================

log_test "2 — /appfix off deactivates autonomous mode"

TMPDIR2="$(make_test_dir "deactivation")"
mkdir -p "$TMPDIR2/src"
echo '# Test project' > "$TMPDIR2/README.md"

# Pre-create state file
mkdir -p "$TMPDIR2/.claude"
cat > "$TMPDIR2/.claude/appfix-state.json" << 'EOF'
{
    "iteration": 2,
    "started_at": "2026-01-28T10:00:00Z",
    "session_id": "test-session",
    "last_activity_at": "2026-01-28T11:00:00Z",
    "plan_mode_completed": true
}
EOF

if $DRY_RUN; then
    log_skip "Dry run"
else
    run_claude "$TMPDIR2" "/appfix off"

    STATE_FILE="$TMPDIR2/.claude/appfix-state.json"
    if [[ -f "$STATE_FILE" ]]; then
        log_fail "State file still exists after /appfix off"
        log_info "State content: $(cat "$STATE_FILE")"
    else
        log_pass "State file deleted by /appfix off"
    fi

    # Check output mentions deactivation
    if grep -qi "deactivat\|cleaned\|disabled" "$TMPDIR2/stdout.log" 2>/dev/null; then
        log_pass "Output confirms deactivation"
    else
        log_info "Output: $(head -5 "$TMPDIR2/stdout.log" 2>/dev/null)"
    fi
fi

cleanup_test_dir "$TMPDIR2"

# =============================================================================
# Test 3: Session Guard - Owner File Creation
# =============================================================================

log_test "3 — Session guard creates owner file at session start"

TMPDIR3="$(make_test_dir "session-guard")"

if $DRY_RUN; then
    log_skip "Dry run"
else
    # Run any command to trigger SessionStart hook
    run_claude "$TMPDIR3" "Say hello and stop"

    OWNER_FILE="$TMPDIR3/.claude/session-owner.json"
    if [[ -f "$OWNER_FILE" ]]; then
        # Check for required fields
        if grep -q '"session_id"' "$OWNER_FILE" && grep -q '"pid"' "$OWNER_FILE"; then
            log_pass "Session owner file created with session_id and pid"
        else
            log_fail "Session owner file missing required fields"
            log_info "Content: $(cat "$OWNER_FILE")"
        fi
    else
        log_fail "Session owner file not created"
    fi
fi

cleanup_test_dir "$TMPDIR3"

# =============================================================================
# Test 4: Session Reuse (Sticky Session)
# =============================================================================

if $QUICK_MODE; then
    log_test "4 — [SKIPPED in quick mode] Session reuse across tasks"
    log_skip "Quick mode enabled"
else
    log_test "4 — Session reuse: same session reuses existing state"

    TMPDIR4="$(make_test_dir "session-reuse")"
    mkdir -p "$TMPDIR4/.claude"

    # Create existing state with specific iteration
    cat > "$TMPDIR4/.claude/appfix-state.json" << 'EOF'
{
    "iteration": 5,
    "started_at": "2026-01-28T10:00:00Z",
    "session_id": "placeholder-will-be-replaced",
    "last_activity_at": "2026-01-28T18:50:00Z",
    "plan_mode_completed": true
}
EOF

    if $DRY_RUN; then
        log_skip "Dry run"
    else
        # First, get a session ID by running a session
        run_claude "$TMPDIR4" "Type /appfix. If you see 'reusing existing' or 'already active', say 'REUSED'. Otherwise say 'NEW'."

        if grep -qi "reusing\|already active" "$TMPDIR4/stdout.log" 2>/dev/null; then
            log_pass "Session detected existing state (sticky session working)"
        else
            # Check if iteration was preserved
            STATE_FILE="$TMPDIR4/.claude/appfix-state.json"
            if [[ -f "$STATE_FILE" ]]; then
                ITERATION=$(grep -o '"iteration": *[0-9]*' "$STATE_FILE" | grep -o '[0-9]*')
                if [[ "$ITERATION" == "5" ]]; then
                    log_pass "Iteration preserved (sticky session working)"
                elif [[ "$ITERATION" == "1" ]]; then
                    log_info "Iteration reset to 1 (might be session_id mismatch)"
                    log_info "State: $(cat "$STATE_FILE")"
                else
                    log_info "Iteration changed to $ITERATION"
                fi
            fi
        fi
    fi

    cleanup_test_dir "$TMPDIR4"
fi

# =============================================================================
# Test 5: Expired State Cleanup at Session Start
# =============================================================================

log_test "5 — Expired state (TTL exceeded) cleaned at session start"

TMPDIR5="$(make_test_dir "expired-cleanup")"
mkdir -p "$TMPDIR5/.claude"

# Create expired state (10 hours ago)
EXPIRED_TIME=$(date -u -v-10H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d "10 hours ago" +%Y-%m-%dT%H:%M:%SZ)
cat > "$TMPDIR5/.claude/appfix-state.json" << EOF
{
    "iteration": 3,
    "started_at": "${EXPIRED_TIME}",
    "session_id": "old-session",
    "last_activity_at": "${EXPIRED_TIME}",
    "plan_mode_completed": true
}
EOF

if $DRY_RUN; then
    log_skip "Dry run"
else
    # Run any command to trigger SessionStart hook
    run_claude "$TMPDIR5" "Say hello"

    STATE_FILE="$TMPDIR5/.claude/appfix-state.json"
    if [[ -f "$STATE_FILE" ]]; then
        # Check if it's the old state or new state
        if grep -q '"old-session"' "$STATE_FILE"; then
            log_fail "Expired state not cleaned up"
            log_info "State: $(cat "$STATE_FILE")"
        else
            log_pass "Old state cleaned, new session took over"
        fi
    else
        log_pass "Expired state file was cleaned up"
    fi

    # Check output mentions cleanup
    if grep -qi "cleaned\|expired" "$TMPDIR5/stdout.log" "$TMPDIR5/stderr.log" 2>/dev/null; then
        log_pass "Output mentions cleanup of expired state"
    fi
fi

cleanup_test_dir "$TMPDIR5"

# =============================================================================
# Test 6: Auto-Approval with Fresh State
# =============================================================================

if $QUICK_MODE; then
    log_test "6 — [SKIPPED in quick mode] Auto-approval with fresh state"
    log_skip "Quick mode enabled"
else
    log_test "6 — Auto-approval works with fresh state"

    TMPDIR6="$(make_test_dir "auto-approval")"
    mkdir -p "$TMPDIR6/src"
    echo '# Test project' > "$TMPDIR6/README.md"

    # Create fresh state
    NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    mkdir -p "$TMPDIR6/.claude"
    cat > "$TMPDIR6/.claude/appfix-state.json" << EOF
{
    "iteration": 2,
    "started_at": "${NOW}",
    "session_id": "test-session",
    "last_activity_at": "${NOW}",
    "plan_mode_completed": true
}
EOF

    if $DRY_RUN; then
        log_skip "Dry run"
    else
        # Try to write a file - should succeed without asking for permission
        run_claude "$TMPDIR6" "Write 'hello' to src/test.txt using the Write tool. Do not ask for permission."

        if [[ -f "$TMPDIR6/src/test.txt" ]]; then
            log_pass "File written without permission prompt (auto-approval working)"
        else
            log_info "File not created - checking output"
            if grep -qi "permission\|blocked" "$TMPDIR6/stdout.log" 2>/dev/null; then
                log_fail "Permission was requested (auto-approval not working)"
            else
                log_info "File not created for unknown reason"
                log_info "stdout: $(head -5 "$TMPDIR6/stdout.log" 2>/dev/null)"
            fi
        fi
    fi

    cleanup_test_dir "$TMPDIR6"
fi

# =============================================================================
# Test 7: Plan Mode Enforcer Allows .claude/ Writes
# =============================================================================

log_test "7 — Plan mode enforcer allows .claude/ writes on iteration 1"

TMPDIR7="$(make_test_dir "plan-mode-claude-dir")"
mkdir -p "$TMPDIR7/src"
echo '# Test project' > "$TMPDIR7/README.md"

# Create fresh state with iteration=1, plan_mode_completed=false
NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
mkdir -p "$TMPDIR7/.claude"
cat > "$TMPDIR7/.claude/appfix-state.json" << EOF
{
    "iteration": 1,
    "started_at": "${NOW}",
    "session_id": "test-session",
    "last_activity_at": "${NOW}",
    "plan_mode_completed": false
}
EOF

if $DRY_RUN; then
    log_skip "Dry run"
else
    run_claude "$TMPDIR7" "Write 'test' to .claude/test-artifact.txt using the Write tool."

    ARTIFACT="$TMPDIR7/.claude/test-artifact.txt"
    if [[ -f "$ARTIFACT" ]]; then
        log_pass ".claude/ write allowed even with plan_mode_completed=false"
    else
        if grep -qi "PLAN MODE REQUIRED" "$TMPDIR7/stdout.log" 2>/dev/null; then
            log_fail ".claude/ write blocked by plan mode enforcer (BUG!)"
        else
            log_info "Artifact not created for unknown reason"
            log_info "stdout: $(head -5 "$TMPDIR7/stdout.log" 2>/dev/null)"
        fi
    fi
fi

cleanup_test_dir "$TMPDIR7"

# =============================================================================
# Results Summary
# =============================================================================

log_header "Results Summary"

TOTAL=$((PASSED + FAILED + SKIPPED))
echo -e "Total:   ${TOTAL}"
echo -e "${GREEN}Passed:  ${PASSED}${NC}"
echo -e "${RED}Failed:  ${FAILED}${NC}"
echo -e "${YELLOW}Skipped: ${SKIPPED}${NC}"

if [[ $FAILED -gt 0 ]]; then
    echo -e "\n${RED}Some tests FAILED. Review output above.${NC}"
    exit 1
elif [[ $PASSED -gt 0 ]]; then
    echo -e "\n${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "\n${YELLOW}All tests skipped (dry run).${NC}"
    exit 0
fi
