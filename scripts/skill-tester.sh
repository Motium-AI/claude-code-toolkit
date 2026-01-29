#!/usr/bin/env bash
# =============================================================================
# Skill Tester - Automated Claude Code Skill Testing Framework
# =============================================================================
#
# Tests Claude Code skills by spawning isolated sessions in headless mode
# or tmux panes with proper git isolation.
#
# Prerequisites:
#   - Claude Code CLI installed and authenticated
#   - tmux installed (brew install tmux) for interactive mode
#   - Hooks installed via scripts/install.sh
#
# Usage:
#   bash scripts/skill-tester.sh --skill appfix              # Test a skill
#   bash scripts/skill-tester.sh --skill appfix --mode tmux  # Interactive test
#   bash scripts/skill-tester.sh --list                       # List available skills
#   bash scripts/skill-tester.sh --help                       # Show help
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
PROMPTS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILLS_DIR="$HOME/.claude/skills"
HOOKS_DIR="$HOME/.claude/hooks"
MODEL="${SKILL_TEST_MODEL:-haiku}"
TIMEOUT="${SKILL_TEST_TIMEOUT:-180}"
MODE="headless"  # headless or tmux
SKILL=""
PROMPT=""
OBSERVE=false
DRY_RUN=false
CLEANUP=true
TEST_DIR=""

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --skill|-s) SKILL="$2"; shift 2 ;;
        --mode|-m) MODE="$2"; shift 2 ;;
        --prompt|-p) PROMPT="$2"; shift 2 ;;
        --model) MODEL="$2"; shift 2 ;;
        --timeout) TIMEOUT="$2"; shift 2 ;;
        --observe|-o) OBSERVE=true; shift ;;
        --dry-run) DRY_RUN=true; shift ;;
        --no-cleanup) CLEANUP=false; shift ;;
        --test-dir) TEST_DIR="$2"; shift 2 ;;
        --list|-l)
            echo -e "${BLUE}Available skills:${NC}"
            for skill_dir in "$SKILLS_DIR"/*; do
                if [[ -f "$skill_dir/SKILL.md" ]]; then
                    skill_name=$(basename "$skill_dir")
                    desc=$(grep -m1 '^description:' "$skill_dir/SKILL.md" 2>/dev/null | sed 's/description: //' | head -c 60)
                    echo -e "  ${GREEN}$skill_name${NC}: $desc"
                fi
            done
            exit 0
            ;;
        --help|-h)
            cat << 'EOF'
Skill Tester - Automated Claude Code Skill Testing Framework

USAGE:
  skill-tester.sh [OPTIONS]

OPTIONS:
  --skill, -s SKILL   Skill to test (required unless using --prompt)
  --mode, -m MODE     Test mode: headless (default) or tmux
  --prompt, -p TEXT   Custom prompt (overrides skill default)
  --model MODEL       Model to use (default: haiku)
  --timeout SECONDS   Timeout in seconds (default: 180)
  --observe, -o       Keep tmux session open for observation
  --dry-run           Show what would run without executing
  --no-cleanup        Don't remove test directory after completion
  --test-dir DIR      Use specific directory instead of temp
  --list, -l          List available skills
  --help, -h          Show this help

EXAMPLES:
  # Test appfix skill in headless mode
  skill-tester.sh --skill appfix

  # Test godo skill with custom prompt
  skill-tester.sh --skill godo --prompt "Create a hello world function"

  # Interactive test with tmux observation
  skill-tester.sh --skill appfix --mode tmux --observe

  # Test in existing directory
  skill-tester.sh --skill appfix --test-dir /path/to/project --no-cleanup

ENVIRONMENT:
  SKILL_TEST_MODEL    Default model (haiku)
  SKILL_TEST_TIMEOUT  Default timeout in seconds (180)
EOF
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
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

log_info() {
    echo -e "  ${NC}$1${NC}"
}

log_success() {
    echo -e "${GREEN}  ✓ $1${NC}"
}

log_error() {
    echo -e "${RED}  ✗ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}  ! $1${NC}"
}

# Create isolated test directory
create_test_sandbox() {
    local test_name="$1"
    local tmpdir

    if [[ -n "$TEST_DIR" ]]; then
        tmpdir="$TEST_DIR"
        mkdir -p "$tmpdir"
    else
        tmpdir="$(mktemp -d "/tmp/skill-test-${test_name}-XXXXXX")"
    fi

    # Initialize as git repo if not already
    if [[ ! -d "$tmpdir/.git" ]]; then
        (cd "$tmpdir" && git init -q && git commit --allow-empty -m "init" -q)
    fi

    echo "$tmpdir"
}

# Create skill-specific state files
create_skill_state() {
    local tmpdir="$1"
    local skill="$2"

    mkdir -p "$tmpdir/.claude"

    case "$skill" in
        appfix)
            cat > "$tmpdir/.claude/appfix-state.json" << 'EOF'
{
    "iteration": 1,
    "started_at": "2026-01-28T10:00:00Z",
    "plan_mode_completed": false,
    "parallel_mode": false,
    "agent_id": null,
    "worktree_path": null,
    "coordinator": true,
    "services": {},
    "fixes_applied": [],
    "verification_evidence": null
}
EOF
            ;;
        godo)
            cat > "$tmpdir/.claude/godo-state.json" << 'EOF'
{
    "iteration": 1,
    "started_at": "2026-01-28T10:00:00Z",
    "plan_mode_completed": false,
    "parallel_mode": false,
    "task_description": null,
    "verification_evidence": null
}
EOF
            ;;
        *)
            # Generic state for unknown skills
            log_warning "No specific state template for skill '$skill'"
            ;;
    esac
}

# Run test in headless mode
run_headless_test() {
    local tmpdir="$1"
    local prompt="$2"

    log_info "Running headless test..."
    log_info "  Directory: $tmpdir"
    log_info "  Model: $MODEL"
    log_info "  Timeout: ${TIMEOUT}s"
    log_info "  Prompt: ${prompt:0:80}..."

    if $DRY_RUN; then
        log_warning "DRY RUN: Would execute:"
        echo "  timeout $TIMEOUT claude -p \"$prompt\" \\"
        echo "    --dangerously-skip-permissions \\"
        echo "    --no-session-persistence \\"
        echo "    --output-format json \\"
        echo "    --model $MODEL \\"
        echo "    --add-dir \"$tmpdir\""
        return 0
    fi

    # Run with timeout
    local start_time=$(date +%s)

    (cd "$tmpdir" && timeout "$TIMEOUT" claude -p "$prompt" \
        --dangerously-skip-permissions \
        --no-session-persistence \
        --output-format json \
        --model "$MODEL" \
        2>"$tmpdir/stderr.log" \
        >"$tmpdir/stdout.log") || true

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    log_info "Execution completed in ${duration}s"

    # Parse results
    if [[ -f "$tmpdir/stdout.log" ]]; then
        local result=$(jq -r '.result // "No result"' "$tmpdir/stdout.log" 2>/dev/null || echo "Parse error")
        local session_id=$(jq -r '.session_id // "unknown"' "$tmpdir/stdout.log" 2>/dev/null || echo "unknown")
        local total_cost=$(jq -r '.total_cost_usd // 0' "$tmpdir/stdout.log" 2>/dev/null || echo "0")

        log_info "Session ID: $session_id"
        log_info "Cost: \$$total_cost"
        echo -e "${CYAN}Result:${NC}"
        echo "$result" | head -20
    else
        log_error "No stdout captured"
    fi

    if [[ -f "$tmpdir/stderr.log" ]] && [[ -s "$tmpdir/stderr.log" ]]; then
        log_warning "Stderr output:"
        head -10 "$tmpdir/stderr.log"
    fi
}

# Run test in tmux mode
run_tmux_test() {
    local tmpdir="$1"
    local prompt="$2"
    local session_name="skill-test-$(date +%s)"

    log_info "Running tmux test..."
    log_info "  Directory: $tmpdir"
    log_info "  Session: $session_name"
    log_info "  Prompt: ${prompt:0:80}..."

    if $DRY_RUN; then
        log_warning "DRY RUN: Would create tmux session '$session_name'"
        return 0
    fi

    # Kill existing session if any
    tmux kill-session -t "$session_name" 2>/dev/null || true

    # Create new tmux session
    tmux new-session -d -s "$session_name" -x 200 -y 50

    # Navigate to test directory
    tmux send-keys -t "$session_name" "cd '$tmpdir'" Enter
    sleep 1

    # Start Claude
    tmux send-keys -t "$session_name" "claude --dangerously-skip-permissions" Enter
    sleep 5  # Wait for Claude to initialize

    # Send test prompt
    tmux send-keys -t "$session_name" "$prompt" Enter

    echo -e "${CYAN}tmux session started: $session_name${NC}"
    echo -e "  Attach: ${GREEN}tmux attach -t $session_name${NC}"
    echo -e "  Kill:   ${RED}tmux kill-session -t $session_name${NC}"
    echo -e "  Dir:    $tmpdir"

    if $OBSERVE; then
        log_info "Waiting for completion (Ctrl+C to stop waiting)..."

        # Poll for completion
        local elapsed=0
        while [[ $elapsed -lt $TIMEOUT ]]; do
            # Capture output
            tmux capture-pane -t "$session_name" -p -S -500 > "$tmpdir/tmux-output.txt"

            # Check for completion markers
            if grep -q "Task completed" "$tmpdir/tmux-output.txt" 2>/dev/null || \
               grep -q "Job complete" "$tmpdir/tmux-output.txt" 2>/dev/null; then
                log_success "Skill completed!"
                break
            fi

            sleep 5
            elapsed=$((elapsed + 5))
        done

        if [[ $elapsed -ge $TIMEOUT ]]; then
            log_warning "Timeout reached"
        fi
    else
        log_info "Session running in background. Use --observe to wait for completion."
    fi
}

# Verify test outcomes
verify_outcomes() {
    local tmpdir="$1"
    local skill="$2"

    log_header "Verification"

    local pass_count=0
    local fail_count=0

    # Check completion checkpoint
    if [[ -f "$tmpdir/.claude/completion-checkpoint.json" ]]; then
        local is_complete=$(jq -r '.self_report.is_job_complete // false' "$tmpdir/.claude/completion-checkpoint.json" 2>/dev/null)
        if [[ "$is_complete" == "true" ]]; then
            log_success "Completion checkpoint: job marked complete"
            pass_count=$((pass_count + 1))
        else
            log_error "Completion checkpoint: job not marked complete (is_job_complete=$is_complete)"
            fail_count=$((fail_count + 1))
        fi
    else
        log_warning "No completion checkpoint found"
    fi

    # Check skill-specific state
    case "$skill" in
        appfix)
            if [[ -f "$tmpdir/.claude/appfix-state.json" ]]; then
                local plan_completed=$(jq -r '.plan_mode_completed // false' "$tmpdir/.claude/appfix-state.json" 2>/dev/null)
                log_info "Appfix state: plan_mode_completed=$plan_completed"
            fi
            ;;
        godo)
            if [[ -f "$tmpdir/.claude/godo-state.json" ]]; then
                local task=$(jq -r '.task_description // "null"' "$tmpdir/.claude/godo-state.json" 2>/dev/null)
                log_info "Godo state: task=$task"
            fi
            ;;
    esac

    # List created files
    log_info "Files in test directory:"
    (cd "$tmpdir" && find . -type f -not -path "./.git/*" | head -20)

    echo ""
    echo -e "Results: ${GREEN}$pass_count passed${NC}, ${RED}$fail_count failed${NC}"

    return $fail_count
}

# Cleanup test artifacts
cleanup_test() {
    local tmpdir="$1"

    if $CLEANUP && [[ -z "$TEST_DIR" ]]; then
        log_info "Cleaning up test directory..."
        rm -rf "$tmpdir"
    else
        log_info "Test directory preserved: $tmpdir"
    fi
}

# =============================================================================
# Main
# =============================================================================

log_header "Skill Tester"

# Validation
if [[ -z "$SKILL" ]] && [[ -z "$PROMPT" ]]; then
    log_error "Either --skill or --prompt is required"
    exit 1
fi

if [[ "$MODE" == "tmux" ]] && ! command -v tmux &>/dev/null; then
    log_error "tmux not found. Install with: brew install tmux"
    exit 1
fi

if ! command -v claude &>/dev/null; then
    log_error "claude CLI not found. Install from https://claude.ai/code"
    exit 1
fi

# Determine test prompt
if [[ -n "$SKILL" ]]; then
    SKILL_DIR="$SKILLS_DIR/$SKILL"
    if [[ ! -d "$SKILL_DIR" ]]; then
        log_error "Skill not found: $SKILL"
        log_info "Run with --list to see available skills"
        exit 1
    fi

    # Use provided prompt or default to skill invocation
    PROMPT="${PROMPT:-/$SKILL}"
    log_info "Testing skill: $SKILL"
fi

log_info "Mode: $MODE"
log_info "Prompt: $PROMPT"

# Create test environment
TEST_SANDBOX=$(create_test_sandbox "${SKILL:-custom}")
log_success "Test sandbox created: $TEST_SANDBOX"

# Create skill state if applicable
if [[ -n "$SKILL" ]]; then
    create_skill_state "$TEST_SANDBOX" "$SKILL"
    log_success "Skill state initialized"
fi

# Run test
if [[ "$MODE" == "tmux" ]]; then
    run_tmux_test "$TEST_SANDBOX" "$PROMPT"
else
    run_headless_test "$TEST_SANDBOX" "$PROMPT"
fi

# Verify (only for headless mode or after tmux observation)
if [[ "$MODE" == "headless" ]] || $OBSERVE; then
    verify_outcomes "$TEST_SANDBOX" "$SKILL" || true
fi

# Cleanup
cleanup_test "$TEST_SANDBOX"

log_header "Done"
