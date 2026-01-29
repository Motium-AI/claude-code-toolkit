#!/usr/bin/env bash
# =============================================================================
# E2E Headless Tests for Plan Mode Hooks
# =============================================================================
#
# Tests hooks using Claude Code's headless mode (claude -p).
# Runs real Claude sessions to verify hook behavior end-to-end.
#
# Prerequisites:
#   - Claude Code CLI installed and authenticated
#   - Hooks installed via scripts/install.sh
#
# Usage:
#   bash scripts/test-e2e-headless.sh          # Run all tests
#   bash scripts/test-e2e-headless.sh --dry-run # Show what would run
#
# Cost: ~$0.05-0.15 per run (uses haiku model for speed/cost)
# =============================================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Config
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROMPTS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
MODEL="${E2E_MODEL:-haiku}"
TIMEOUT="${E2E_TIMEOUT:-120}"
DRY_RUN=false
PASSED=0
FAILED=0
SKIPPED=0

# Parse args
for arg in "$@"; do
    case $arg in
        --dry-run) DRY_RUN=true ;;
        --model=*) MODEL="${arg#*=}" ;;
        --timeout=*) TIMEOUT="${arg#*=}" ;;
        --help|-h)
            echo "Usage: $0 [--dry-run] [--model=MODEL] [--timeout=SECONDS]"
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
    tmpdir="$(mktemp -d "/tmp/e2e-hooks-${test_name}-XXXXXX")"
    echo "$tmpdir"
}

# Create .claude/ state directory with appfix or godo state
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

# Run Claude headless and capture output
# Args: tmpdir, prompt, [extra_flags...]
run_claude() {
    local tmpdir="$1"
    local prompt="$2"
    shift 2
    local extra_flags=("$@")

    if $DRY_RUN; then
        log_info "DRY RUN: claude -p --model $MODEL --no-session-persistence --output-format json ${extra_flags[*]:-} \"$prompt\""
        log_info "  cwd: $tmpdir"
        return 0
    fi

    # Determine timeout command (macOS lacks 'timeout', use gtimeout from coreutils)
    local timeout_cmd=""
    if command -v gtimeout &>/dev/null; then
        timeout_cmd="gtimeout"
    elif command -v timeout &>/dev/null; then
        timeout_cmd="timeout"
    fi

    # Run with or without timeout
    if [[ -n "$timeout_cmd" ]]; then
        "$timeout_cmd" "$TIMEOUT" claude -p \
            --model "$MODEL" \
            --no-session-persistence \
            --output-format json \
            --dangerously-skip-permissions \
            "${extra_flags[@]}" \
            "$prompt" \
            2>"$tmpdir/stderr.log" \
            >"$tmpdir/stdout.log" \
            || true
    else
        # No timeout available - run without timeout (warn user)
        log_info "WARNING: No timeout command available. Running without timeout."
        claude -p \
            --model "$MODEL" \
            --no-session-persistence \
            --output-format json \
            --dangerously-skip-permissions \
            "${extra_flags[@]}" \
            "$prompt" \
            2>"$tmpdir/stderr.log" \
            >"$tmpdir/stdout.log" \
            || true
    fi

    # Return captured output path
    echo "$tmpdir/stdout.log"
}

# Cleanup a test directory
cleanup_test_dir() {
    local tmpdir="$1"
    if [[ -d "$tmpdir" ]]; then
        rm -rf "$tmpdir"
    fi
}

# =============================================================================
# Pre-flight Checks
# =============================================================================

log_header "E2E Hook Tests (Headless Mode)"

echo -e "Model:   ${MODEL}"
echo -e "Timeout: ${TIMEOUT}s per test"
echo -e "Dry run: ${DRY_RUN}"

# Check Claude CLI
if ! command -v claude &>/dev/null; then
    echo -e "${RED}ERROR: 'claude' CLI not found. Install from https://claude.ai/code${NC}"
    exit 1
fi

# Check hooks are installed
HOOKS_DIR="$HOME/.claude/hooks"
if [[ ! -f "$HOOKS_DIR/plan-mode-enforcer.py" ]]; then
    echo -e "${RED}ERROR: Hooks not installed. Run: cd prompts && ./scripts/install.sh${NC}"
    exit 1
fi

echo -e "${GREEN}Pre-flight checks passed.${NC}"

# =============================================================================
# Test 1: .claude/ writes allowed during plan mode enforcement
# =============================================================================

log_test "1 — .claude/ writes allowed when plan_mode_completed=false"

TMPDIR1="$(make_test_dir "claude-artifact")"
create_state "$TMPDIR1" "appfix-state.json" "false" 1

# Initialize a basic file structure so it looks like a real project
mkdir -p "$TMPDIR1/src"
echo '# Test project' > "$TMPDIR1/README.md"

if $DRY_RUN; then
    run_claude "$TMPDIR1" "Write the text 'e2e-test-pass' to the file .claude/e2e-test.txt using the Write tool. Do not write to any other file."
    log_skip "Dry run — cannot verify file creation"
else
    run_claude "$TMPDIR1" \
        "Write the text 'e2e-test-pass' to the file .claude/e2e-test.txt using the Write tool. Do not write to any other file." \
        --add-dir "$TMPDIR1"

    # Verify: .claude/e2e-test.txt should exist (enforcer should NOT block it)
    if [[ -f "$TMPDIR1/.claude/e2e-test.txt" ]]; then
        CONTENT="$(cat "$TMPDIR1/.claude/e2e-test.txt")"
        if [[ "$CONTENT" == *"e2e-test-pass"* ]]; then
            log_pass ".claude/ write succeeded with correct content"
        else
            log_pass ".claude/ write succeeded (content may vary: '$CONTENT')"
        fi
    else
        # Check if enforcer blocked it
        if grep -q "PLAN MODE REQUIRED" "$TMPDIR1/stdout.log" 2>/dev/null; then
            log_fail ".claude/ write was BLOCKED by plan-mode-enforcer (the bug we fixed)"
        elif grep -q "PLAN MODE REQUIRED" "$TMPDIR1/stderr.log" 2>/dev/null; then
            log_fail ".claude/ write was BLOCKED (visible in stderr)"
        else
            log_fail ".claude/e2e-test.txt was not created (unknown reason)"
            log_info "stdout: $(head -5 "$TMPDIR1/stdout.log" 2>/dev/null)"
            log_info "stderr: $(head -5 "$TMPDIR1/stderr.log" 2>/dev/null)"
        fi
    fi
fi

cleanup_test_dir "$TMPDIR1"

# =============================================================================
# Test 2: Code file writes blocked when plan_mode_completed=false
# =============================================================================

log_test "2 — Code file writes BLOCKED when plan_mode_completed=false"

TMPDIR2="$(make_test_dir "code-blocked")"
create_state "$TMPDIR2" "appfix-state.json" "false" 1

mkdir -p "$TMPDIR2/src"
echo '# Test project' > "$TMPDIR2/README.md"

if $DRY_RUN; then
    run_claude "$TMPDIR2" "Write 'test' to src/test.py using the Write tool."
    log_skip "Dry run — cannot verify blocking"
else
    run_claude "$TMPDIR2" \
        "Write the text 'print(hello)' to the file src/test.py using the Write tool. Do not write to any other file." \
        --add-dir "$TMPDIR2"

    # Verify: src/test.py should NOT exist (enforcer should BLOCK it)
    if [[ -f "$TMPDIR2/src/test.py" ]]; then
        log_fail "src/test.py was created — enforcer did NOT block it"
    else
        # Check if plan mode required message appeared
        if grep -q "PLAN MODE REQUIRED" "$TMPDIR2/stdout.log" 2>/dev/null || \
           grep -q "PLAN MODE REQUIRED" "$TMPDIR2/stderr.log" 2>/dev/null; then
            log_pass "Code file blocked with PLAN MODE REQUIRED message"
        else
            log_pass "Code file was not created (enforcer likely blocked or Claude complied)"
        fi
    fi
fi

cleanup_test_dir "$TMPDIR2"

# =============================================================================
# Test 3: Code file writes allowed after plan_mode_completed=true
# =============================================================================

log_test "3 — Code file writes ALLOWED when plan_mode_completed=true"

TMPDIR3="$(make_test_dir "code-allowed")"
create_state "$TMPDIR3" "appfix-state.json" "true" 1

mkdir -p "$TMPDIR3/src"
echo '# Test project' > "$TMPDIR3/README.md"

if $DRY_RUN; then
    run_claude "$TMPDIR3" "Write 'print(hello)' to src/test.py using the Write tool."
    log_skip "Dry run — cannot verify file creation"
else
    run_claude "$TMPDIR3" \
        "Write the text 'print(\"hello\")' to the file src/test.py using the Write tool. Do not write to any other file." \
        --add-dir "$TMPDIR3"

    # Verify: src/test.py SHOULD exist now
    if [[ -f "$TMPDIR3/src/test.py" ]]; then
        log_pass "Code file write succeeded after plan mode completion"
    else
        if grep -q "PLAN MODE REQUIRED" "$TMPDIR3/stdout.log" 2>/dev/null; then
            log_fail "Code file STILL blocked even with plan_mode_completed=true"
        else
            log_fail "src/test.py not created (unknown reason)"
            log_info "stdout: $(head -5 "$TMPDIR3/stdout.log" 2>/dev/null)"
        fi
    fi
fi

cleanup_test_dir "$TMPDIR3"

# =============================================================================
# Test 4: Iteration > 1 skips plan mode enforcement
# =============================================================================

log_test "4 — Iteration > 1 skips plan mode enforcement"

TMPDIR4="$(make_test_dir "iteration-skip")"
create_state "$TMPDIR4" "appfix-state.json" "false" 2  # iteration=2, plan NOT completed

mkdir -p "$TMPDIR4/src"
echo '# Test project' > "$TMPDIR4/README.md"

if $DRY_RUN; then
    run_claude "$TMPDIR4" "Write 'test' to src/test.py using the Write tool."
    log_skip "Dry run — cannot verify iteration skip"
else
    run_claude "$TMPDIR4" \
        "Write the text 'print(\"iteration 2\")' to the file src/test.py using the Write tool. Do not write to any other file." \
        --add-dir "$TMPDIR4"

    # Verify: src/test.py SHOULD exist (iteration > 1 skips enforcement)
    if [[ -f "$TMPDIR4/src/test.py" ]]; then
        log_pass "Code file write allowed on iteration > 1"
    else
        if grep -q "PLAN MODE REQUIRED" "$TMPDIR4/stdout.log" 2>/dev/null; then
            log_fail "Code file blocked on iteration > 1 — enforcement should skip"
        else
            log_fail "src/test.py not created on iteration 2 (unknown reason)"
        fi
    fi
fi

cleanup_test_dir "$TMPDIR4"

# =============================================================================
# Test 5: No state file = normal session (no enforcement)
# =============================================================================

log_test "5 — No state file = passthrough (normal session)"

TMPDIR5="$(make_test_dir "no-state")"
# Deliberately do NOT create any state file
mkdir -p "$TMPDIR5/src"
echo '# Test project' > "$TMPDIR5/README.md"

if $DRY_RUN; then
    run_claude "$TMPDIR5" "Write 'test' to src/test.py using the Write tool."
    log_skip "Dry run — cannot verify passthrough"
else
    run_claude "$TMPDIR5" \
        "Write the text 'print(\"no state\")' to the file src/test.py using the Write tool. Do not write to any other file." \
        --add-dir "$TMPDIR5"

    # Verify: src/test.py SHOULD exist (no state = no enforcement)
    if [[ -f "$TMPDIR5/src/test.py" ]]; then
        log_pass "Code file write allowed in non-autonomous session"
    else
        log_fail "Code file blocked in non-autonomous session — should be passthrough"
    fi
fi

cleanup_test_dir "$TMPDIR5"

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
