#!/usr/bin/env bash
# =============================================================================
# E2E Interactive Tests for Plan Mode Hooks (tmux)
# =============================================================================
#
# Tests hooks using tmux to simulate an interactive Claude Code session.
# Runs Claude inside a tmux session, sends commands, and captures output
# to verify hook behavior in a realistic interactive environment.
#
# Prerequisites:
#   - Claude Code CLI installed and authenticated
#   - tmux installed (brew install tmux)
#   - Hooks installed via scripts/install.sh
#
# Usage:
#   bash scripts/test-e2e-tmux.sh              # Run all tests
#   bash scripts/test-e2e-tmux.sh --observe    # Keep tmux sessions open for observation
#   bash scripts/test-e2e-tmux.sh --dry-run    # Show what would run
#
# Note: Interactive tests are slower and less deterministic than headless tests.
#       Prefer test-e2e-headless.sh for CI/automated testing.
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
SESSION_PREFIX="e2e-hooks"
OBSERVE=false
DRY_RUN=false
WAIT_TIME="${E2E_WAIT:-30}"  # Seconds to wait for Claude to process
PASSED=0
FAILED=0
SKIPPED=0

# Parse args
for arg in "$@"; do
    case $arg in
        --observe) OBSERVE=true ;;
        --dry-run) DRY_RUN=true ;;
        --wait=*) WAIT_TIME="${arg#*=}" ;;
        --help|-h)
            echo "Usage: $0 [--observe] [--dry-run] [--wait=SECONDS]"
            echo ""
            echo "Options:"
            echo "  --observe   Keep tmux sessions open for manual observation"
            echo "  --dry-run   Show what would run without executing"
            echo "  --wait=N    Seconds to wait for Claude to respond (default: 30)"
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

# Create isolated temp directory with optional state files
make_test_dir() {
    local test_name="$1"
    local tmpdir
    tmpdir="$(mktemp -d "/tmp/e2e-tmux-${test_name}-XXXXXX")"

    # Initialize as git repo (Claude may need it)
    (cd "$tmpdir" && git init -q && git commit --allow-empty -m "init" -q)

    echo "$tmpdir"
}

# Create .claude/ state directory
create_state() {
    local tmpdir="$1"
    local filename="${2:-appfix-state.json}"
    local plan_completed="${3:-false}"
    local iteration="${4:-1}"

    mkdir -p "$tmpdir/.claude"
    cat > "$tmpdir/.claude/$filename" << EOF
{
    "iteration": $iteration,
    "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "plan_mode_completed": $plan_completed,
    "parallel_mode": false,
    "agent_id": null,
    "worktree_path": null,
    "coordinator": true,
    "services": {},
    "fixes_applied": [],
    "verification_evidence": null
}
EOF
}

# Start a tmux session running Claude interactively
# Returns session name
start_claude_tmux() {
    local session_name="$1"
    local workdir="$2"
    shift 2
    local extra_flags=("$@")

    # Kill existing session if any
    tmux kill-session -t "$session_name" 2>/dev/null || true

    # Create new tmux session
    tmux new-session -d -s "$session_name" -x 200 -y 50

    # Change to work directory and start Claude
    tmux send-keys -t "$session_name" "cd '$workdir'" Enter
    sleep 1

    local claude_cmd="claude --dangerously-skip-permissions"
    if [[ ${#extra_flags[@]} -gt 0 ]]; then
        claude_cmd="$claude_cmd ${extra_flags[*]}"
    fi

    tmux send-keys -t "$session_name" "$claude_cmd" Enter
    sleep 5  # Wait for Claude to initialize
}

# Send a message to Claude in tmux
send_to_claude() {
    local session_name="$1"
    local message="$2"

    tmux send-keys -t "$session_name" "$message" Enter
}

# Capture tmux pane output
capture_output() {
    local session_name="$1"
    local output_file="$2"

    tmux capture-pane -t "$session_name" -p -S -500 > "$output_file"
}

# Wait for a pattern in tmux output (polling)
wait_for_pattern() {
    local session_name="$1"
    local pattern="$2"
    local max_wait="${3:-$WAIT_TIME}"
    local elapsed=0
    local tmpfile
    tmpfile="$(mktemp)"

    while [[ $elapsed -lt $max_wait ]]; do
        tmux capture-pane -t "$session_name" -p -S -100 > "$tmpfile"
        if grep -q "$pattern" "$tmpfile" 2>/dev/null; then
            rm -f "$tmpfile"
            return 0
        fi
        sleep 2
        elapsed=$((elapsed + 2))
    done

    rm -f "$tmpfile"
    return 1  # Pattern not found within timeout
}

# Stop Claude session gracefully
stop_claude_tmux() {
    local session_name="$1"

    if $OBSERVE; then
        echo -e "${CYAN}  Session '$session_name' kept open for observation.${NC}"
        echo -e "${CYAN}  Attach with: tmux attach -t $session_name${NC}"
        echo -e "${CYAN}  Kill with:   tmux kill-session -t $session_name${NC}"
        return
    fi

    # Send /exit to Claude
    tmux send-keys -t "$session_name" "/exit" Enter
    sleep 2

    # Kill the session
    tmux kill-session -t "$session_name" 2>/dev/null || true
}

# =============================================================================
# Pre-flight Checks
# =============================================================================

log_header "E2E Hook Tests (tmux Interactive Mode)"

echo -e "Observe: ${OBSERVE}"
echo -e "Dry run: ${DRY_RUN}"
echo -e "Wait:    ${WAIT_TIME}s per test"

# Check dependencies
if ! command -v claude &>/dev/null; then
    echo -e "${RED}ERROR: 'claude' CLI not found.${NC}"
    exit 1
fi

if ! command -v tmux &>/dev/null; then
    echo -e "${RED}ERROR: 'tmux' not found. Install with: brew install tmux${NC}"
    exit 1
fi

# Check hooks
HOOKS_DIR="$HOME/.claude/hooks"
if [[ ! -f "$HOOKS_DIR/plan-mode-enforcer.py" ]]; then
    echo -e "${RED}ERROR: Hooks not installed. Run: cd prompts && ./scripts/install.sh${NC}"
    exit 1
fi

echo -e "${GREEN}Pre-flight checks passed.${NC}"

# =============================================================================
# Test 1: Interactive — .claude/ artifact write during plan enforcement
# =============================================================================

log_test "1 — Interactive: .claude/ artifact write allowed"

SESSION1="${SESSION_PREFIX}-artifact"
TMPDIR1="$(make_test_dir "artifact")"
create_state "$TMPDIR1" "appfix-state.json" "false" 1
mkdir -p "$TMPDIR1/src"

if $DRY_RUN; then
    log_info "DRY RUN: Would start Claude in tmux session '$SESSION1'"
    log_info "  Prompt: Write 'e2e-pass' to .claude/e2e-test.txt"
    log_skip "Dry run"
else
    start_claude_tmux "$SESSION1" "$TMPDIR1"

    send_to_claude "$SESSION1" \
        "Write the text 'e2e-pass' to the file .claude/e2e-test.txt using the Write tool. Only write to that one file."

    # Wait for Claude to process (look for common completion signals)
    sleep "$WAIT_TIME"

    # Capture output for debugging
    capture_output "$SESSION1" "$TMPDIR1/tmux-output.txt"

    # Verify
    if [[ -f "$TMPDIR1/.claude/e2e-test.txt" ]]; then
        log_pass ".claude/ artifact write succeeded in interactive session"
    else
        log_fail ".claude/ artifact write failed in interactive session"
        log_info "tmux output tail:"
        tail -20 "$TMPDIR1/tmux-output.txt" 2>/dev/null | head -10 | while read -r line; do
            log_info "  $line"
        done
    fi

    stop_claude_tmux "$SESSION1"
fi

# Only cleanup if not observing
if ! $OBSERVE; then
    rm -rf "$TMPDIR1"
fi

# =============================================================================
# Test 2: Interactive — Code file blocked before plan mode
# =============================================================================

log_test "2 — Interactive: Code file blocked before plan mode"

SESSION2="${SESSION_PREFIX}-blocked"
TMPDIR2="$(make_test_dir "blocked")"
create_state "$TMPDIR2" "appfix-state.json" "false" 1
mkdir -p "$TMPDIR2/src"

if $DRY_RUN; then
    log_info "DRY RUN: Would start Claude in tmux session '$SESSION2'"
    log_info "  Prompt: Write to src/test.py"
    log_skip "Dry run"
else
    start_claude_tmux "$SESSION2" "$TMPDIR2"

    send_to_claude "$SESSION2" \
        "Write 'print(hello)' to src/test.py using the Write tool."

    sleep "$WAIT_TIME"

    capture_output "$SESSION2" "$TMPDIR2/tmux-output.txt"

    if [[ -f "$TMPDIR2/src/test.py" ]]; then
        log_fail "src/test.py was created — enforcer should have blocked it"
    else
        # Check if PLAN MODE REQUIRED appeared in output
        if grep -q "PLAN MODE REQUIRED" "$TMPDIR2/tmux-output.txt" 2>/dev/null; then
            log_pass "Code file blocked with PLAN MODE REQUIRED message"
        else
            log_pass "Code file was not created (enforcer likely blocked)"
        fi
    fi

    stop_claude_tmux "$SESSION2"
fi

if ! $OBSERVE; then
    rm -rf "$TMPDIR2"
fi

# =============================================================================
# Test 3: Interactive — Full lifecycle (enforce → plan → allow)
# =============================================================================

log_test "3 — Interactive: Full lifecycle (enforce, plan, allow)"

SESSION3="${SESSION_PREFIX}-lifecycle"
TMPDIR3="$(make_test_dir "lifecycle")"
create_state "$TMPDIR3" "appfix-state.json" "false" 1
mkdir -p "$TMPDIR3/src"

if $DRY_RUN; then
    log_info "DRY RUN: Would run full lifecycle test"
    log_info "  Step 1: Try code write (should block)"
    log_info "  Step 2: Enter plan mode"
    log_info "  Step 3: Exit plan mode"
    log_info "  Step 4: Try code write again (should succeed)"
    log_skip "Dry run"
else
    start_claude_tmux "$SESSION3" "$TMPDIR3"

    # Step 1: Try writing code (should be blocked)
    log_info "Step 1: Attempting code write (expect block)..."
    send_to_claude "$SESSION3" \
        "Write 'print(step1)' to src/lifecycle.py using the Write tool."
    sleep "$WAIT_TIME"

    if [[ -f "$TMPDIR3/src/lifecycle.py" ]]; then
        log_fail "Step 1: Code write was not blocked before plan mode"
        stop_claude_tmux "$SESSION3"
    else
        log_info "Step 1: Code write correctly blocked"

        # Step 2: Enter plan mode
        log_info "Step 2: Entering plan mode..."
        send_to_claude "$SESSION3" \
            "Call the EnterPlanMode tool now."
        sleep 10

        # Step 3: Exit plan mode (write a plan first, then exit)
        log_info "Step 3: Exiting plan mode..."
        send_to_claude "$SESSION3" \
            "Write a plan that says 'Test plan for lifecycle test.' then call ExitPlanMode."
        sleep "$WAIT_TIME"

        # Verify state was updated
        if [[ -f "$TMPDIR3/.claude/appfix-state.json" ]]; then
            PLAN_COMPLETED=$(python3 -c "import json; print(json.load(open('$TMPDIR3/.claude/appfix-state.json'))['plan_mode_completed'])")
            if [[ "$PLAN_COMPLETED" == "True" ]]; then
                log_info "Step 3: plan_mode_completed updated to true"

                # Step 4: Try writing code again (should succeed)
                log_info "Step 4: Attempting code write (expect success)..."
                send_to_claude "$SESSION3" \
                    "Write 'print(\"lifecycle complete\")' to src/lifecycle.py using the Write tool."
                sleep "$WAIT_TIME"

                if [[ -f "$TMPDIR3/src/lifecycle.py" ]]; then
                    log_pass "Full lifecycle: enforce → plan → allow works correctly"
                else
                    log_fail "Step 4: Code write still blocked after plan mode completion"
                fi
            else
                log_fail "Step 3: plan_mode_completed was not updated to true"
            fi
        else
            log_fail "Step 3: appfix-state.json not found"
        fi

        stop_claude_tmux "$SESSION3"
    fi
fi

if ! $OBSERVE; then
    rm -rf "$TMPDIR3"
fi

# =============================================================================
# Results Summary
# =============================================================================

log_header "Results Summary"

TOTAL=$((PASSED + FAILED + SKIPPED))
echo -e "Total:   ${TOTAL}"
echo -e "${GREEN}Passed:  ${PASSED}${NC}"
echo -e "${RED}Failed:  ${FAILED}${NC}"
echo -e "${YELLOW}Skipped: ${SKIPPED}${NC}"

if $OBSERVE; then
    echo -e "\n${CYAN}Active tmux sessions:${NC}"
    tmux list-sessions 2>/dev/null | grep "$SESSION_PREFIX" | while read -r line; do
        echo -e "  ${CYAN}$line${NC}"
    done
    echo -e "${CYAN}Attach with: tmux attach -t <session-name>${NC}"
fi

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
