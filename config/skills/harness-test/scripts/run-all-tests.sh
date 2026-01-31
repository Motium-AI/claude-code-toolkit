#!/usr/bin/env bash
# =============================================================================
# Run All Relevant Test Cases for Modified Harness Files
# =============================================================================
#
# Runs test cases that are relevant to the modified harness files.
# Writes results to .claude/harness-test-state.json
#
# Usage:
#   ./run-all-tests.sh <sandbox-id> [--all] [--parallel]
#
# Flags:
#   --all       Run all test cases, not just relevant ones
#   --parallel  Create one sandbox per test and run all simultaneously
#
# =============================================================================

set -euo pipefail

SANDBOX_ID="${1:?Usage: $0 <sandbox-id> [--all] [--parallel]}"
shift

# Parse remaining flags
RUN_ALL=""
PARALLEL=""
for arg in "$@"; do
    case "$arg" in
        --all) RUN_ALL="--all" ;;
        --parallel) PARALLEL="true" ;;
    esac
done

SANDBOX_BASE="/tmp/claude-sandboxes"
SANDBOX_ROOT="$SANDBOX_BASE/$SANDBOX_ID"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
TEST_CASES_DIR="$SKILL_DIR/test-cases"

# Verify sandbox exists
if [[ ! -d "$SANDBOX_ROOT" ]]; then
    echo "ERROR: Sandbox not found: $SANDBOX_ID" >&2
    exit 1
fi

# Load sandbox metadata
PROJECT_SOURCE=$(jq -r '.project_source' "$SANDBOX_ROOT/metadata.json")
SANDBOX_PROJECT=$(jq -r '.project_worktree' "$SANDBOX_ROOT/metadata.json")

echo "========================================"
echo "Harness Test Runner"
echo "========================================"
echo "Sandbox: $SANDBOX_ID"
echo "Project: $PROJECT_SOURCE"
[[ "$PARALLEL" == "true" ]] && echo "Mode:    PARALLEL (one sandbox per test)"
echo ""

# Get modified harness files
HARNESS_FILES=$("$SCRIPT_DIR/detect-harness-changes.sh" "$PROJECT_SOURCE" || true)

if [[ -z "$HARNESS_FILES" ]] && [[ "$RUN_ALL" != "--all" ]]; then
    echo "No harness files modified. Use --all to run all tests."
    exit 0
fi

if [[ -n "$HARNESS_FILES" ]]; then
    echo "Modified harness files:"
    echo "$HARNESS_FILES" | while read -r file; do
        [[ -n "$file" ]] && echo "  - $file"
    done
    echo ""
else
    echo "Running all test cases (no specific file filter)."
    echo ""
fi

# Determine which test cases to run
TEST_CASES=()
for test_file in "$TEST_CASES_DIR"/*.json; do
    if [[ -f "$test_file" ]]; then
        TEST_NAME=$(basename "$test_file" .json)
        TEST_CASES+=("$TEST_NAME")
    fi
done

if [[ ${#TEST_CASES[@]} -eq 0 ]]; then
    echo "No test cases found in $TEST_CASES_DIR"
    exit 0
fi

echo "Running ${#TEST_CASES[@]} test case(s):"
for tc in "${TEST_CASES[@]}"; do
    echo "  - $tc"
done
echo ""

# Initialize counters
START_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)
RESULTS="[]"
PASSED=0
FAILED=0
SKIPPED=0

# =============================================================================
# PARALLEL EXECUTION
# =============================================================================
if [[ "$PARALLEL" == "true" ]]; then
    echo "Creating ${#TEST_CASES[@]} parallel sandboxes..."

    # Arrays for tracking (indexed, not associative — bash 3.2 compatible)
    SANDBOX_IDS=()
    RESULT_FILES=()
    LOG_FILES=()
    PIDS=()

    for i in "${!TEST_CASES[@]}"; do
        TEST_NAME="${TEST_CASES[$i]}"

        # Create per-test sandbox (suppress setup output, tail -1 for clean sandbox ID)
        TSID=$("$SCRIPT_DIR/setup-harness-sandbox.sh" "$PROJECT_SOURCE" 2>/dev/null | tail -1)
        SANDBOX_IDS+=("$TSID")

        RESULT_FILE="/tmp/harness-result-${TSID}.json"
        LOG_FILE="/tmp/harness-log-${TSID}.log"
        RESULT_FILES+=("$RESULT_FILE")
        LOG_FILES+=("$LOG_FILE")

        # Launch test in background (stdout=JSON result, stderr=log)
        "$SCRIPT_DIR/run-test-case.sh" "$TSID" "$TEST_NAME" \
            >"$RESULT_FILE" 2>"$LOG_FILE" &
        PIDS+=($!)

        echo "  [$((i+1))/${#TEST_CASES[@]}] $TEST_NAME -> $TSID (PID $!)"
    done

    echo ""
    echo "All ${#PIDS[@]} tests launched. Waiting for completion..."
    echo ""

    # Wait for all tests to finish
    for i in "${!PIDS[@]}"; do
        wait "${PIDS[$i]}" 2>/dev/null || true
    done

    echo "All tests completed. Collecting results..."
    echo ""

    # Collect results from each test
    for i in "${!TEST_CASES[@]}"; do
        TEST_NAME="${TEST_CASES[$i]}"
        RESULT_FILE="${RESULT_FILES[$i]}"
        LOG_FILE="${LOG_FILES[$i]}"

        echo "----------------------------------------"
        # Print the stderr log (status messages from run-test-case.sh)
        cat "$LOG_FILE" 2>/dev/null || true

        # Parse the JSON result (stdout from run-test-case.sh)
        RESULT=$(cat "$RESULT_FILE" 2>/dev/null || echo '')
        if [[ -z "$RESULT" ]] || ! echo "$RESULT" | jq . >/dev/null 2>&1; then
            RESULT=$(jq -cn --arg name "$TEST_NAME" '{"name":$name,"status":"error","description":"Failed to parse result"}')
        fi

        STATUS=$(echo "$RESULT" | jq -r '.status // "error"')
        case "$STATUS" in
            passed) PASSED=$((PASSED + 1)) ;;
            failed) FAILED=$((FAILED + 1)) ;;
            *) SKIPPED=$((SKIPPED + 1)) ;;
        esac

        RESULTS=$(echo "$RESULTS" | jq ". + [$RESULT]")

        # Cleanup temp files
        rm -f "$RESULT_FILE" "$LOG_FILE"
    done

    # Cleanup per-test sandboxes
    echo ""
    echo "Cleaning up ${#SANDBOX_IDS[@]} parallel sandboxes..."
    for TSID in "${SANDBOX_IDS[@]}"; do
        "$SCRIPT_DIR/cleanup-sandbox.sh" "$TSID" >/dev/null 2>&1 || true
    done
    echo "Cleanup complete."

# =============================================================================
# SEQUENTIAL EXECUTION (default)
# =============================================================================
else
    for TEST_NAME in "${TEST_CASES[@]}"; do
        echo "----------------------------------------"
        RESULT=$("$SCRIPT_DIR/run-test-case.sh" "$SANDBOX_ID" "$TEST_NAME" 2>&1 | tail -1)

        STATUS=$(echo "$RESULT" | jq -r '.status // "error"')

        case "$STATUS" in
            passed)
                PASSED=$((PASSED + 1))
                ;;
            failed)
                FAILED=$((FAILED + 1))
                ;;
            *)
                SKIPPED=$((SKIPPED + 1))
                ;;
        esac

        RESULTS=$(echo "$RESULTS" | jq ". + [$RESULT]")
    done
fi

echo ""
echo "========================================"
echo "Test Results Summary"
echo "========================================"
TOTAL=$((PASSED + FAILED + SKIPPED))
echo "Total:   $TOTAL"
echo "Passed:  $PASSED"
echo "Failed:  $FAILED"
echo "Skipped: $SKIPPED"
echo ""

# Determine overall status
if [[ $FAILED -eq 0 ]] && [[ $TOTAL -gt 0 ]]; then
    OVERALL_STATUS="passed"
    echo "OVERALL: PASSED"
else
    OVERALL_STATUS="failed"
    echo "OVERALL: FAILED"
fi

# Write state file
mkdir -p "$PROJECT_SOURCE/.claude"
STATE_FILE="$PROJECT_SOURCE/.claude/harness-test-state.json"

jq -n \
    --arg started_at "$START_TIME" \
    --arg sandbox_id "$SANDBOX_ID" \
    --arg trigger "manual" \
    --argjson harness_files "$(echo "$HARNESS_FILES" | jq -R -s 'split("\n") | map(select(. != ""))')" \
    --argjson test_cases_run "$RESULTS" \
    --argjson total "$TOTAL" \
    --argjson passed "$PASSED" \
    --argjson failed "$FAILED" \
    --argjson skipped "$SKIPPED" \
    --arg overall_status "$OVERALL_STATUS" \
    '{
        started_at: $started_at,
        sandbox_id: $sandbox_id,
        trigger: $trigger,
        harness_files_modified: $harness_files,
        test_cases_run: $test_cases_run,
        summary: {
            total: $total,
            passed: $passed,
            failed: $failed,
            skipped: $skipped
        },
        overall_status: $overall_status
    }' > "$STATE_FILE"

echo ""
echo "Results written to: $STATE_FILE"

# Exit with appropriate code
if [[ "$OVERALL_STATUS" == "passed" ]]; then
    exit 0
else
    exit 1
fi
