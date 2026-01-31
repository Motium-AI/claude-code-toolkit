#!/usr/bin/env bash
# =============================================================================
# Run a Single Test Case in Harness Sandbox
# =============================================================================
#
# Executes a test case JSON file against a harness sandbox.
#
# Usage:
#   ./run-test-case.sh <sandbox-id> <test-case-name>
#
# Test case files are in: ~/.claude/skills/harness-test/test-cases/
#
# Output:
#   JSON object with test results
#
# =============================================================================

set -euo pipefail

SANDBOX_ID="${1:?Usage: $0 <sandbox-id> <test-case-name>}"
TEST_CASE_NAME="${2:?Usage: $0 <sandbox-id> <test-case-name>}"

SANDBOX_BASE="/tmp/claude-sandboxes"
SANDBOX_ROOT="$SANDBOX_BASE/$SANDBOX_ID"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
TEST_CASES_DIR="$SKILL_DIR/test-cases"

# Verify sandbox exists
if [[ ! -d "$SANDBOX_ROOT" ]]; then
    echo '{"status": "error", "message": "Sandbox not found: '"$SANDBOX_ID"'"}' >&2
    exit 1
fi

# Load sandbox metadata
SANDBOX_PROJECT=$(jq -r '.project_worktree' "$SANDBOX_ROOT/metadata.json")
FAKE_HOME=$(jq -r '.fake_home' "$SANDBOX_ROOT/metadata.json")
MOCK_BIN=$(jq -r '.mock_bin' "$SANDBOX_ROOT/metadata.json")

# Find test case file
TEST_CASE_FILE="$TEST_CASES_DIR/${TEST_CASE_NAME}.json"
if [[ ! -f "$TEST_CASE_FILE" ]]; then
    echo '{"status": "error", "message": "Test case not found: '"$TEST_CASE_NAME"'"}' >&2
    exit 1
fi

# Parse test case
TEST_CASE=$(cat "$TEST_CASE_FILE")
DESCRIPTION=$(echo "$TEST_CASE" | jq -r '.description // "No description"')
PROMPT=$(echo "$TEST_CASE" | jq -r '.prompt')
TIMEOUT=$(echo "$TEST_CASE" | jq -r '.timeout // 120')

echo "Running test: $TEST_CASE_NAME" >&2
echo "  Description: $DESCRIPTION" >&2
echo "  Timeout: ${TIMEOUT}s" >&2

# =============================================================================
# SETUP: Apply test case setup
# =============================================================================

# Create state files if specified
SETUP_STATE_FILE=$(echo "$TEST_CASE" | jq -r '.setup.state_file // empty')
SETUP_STATE_CONTENT=$(echo "$TEST_CASE" | jq -r '.setup.state_content // empty')

if [[ -n "$SETUP_STATE_FILE" ]] && [[ -n "$SETUP_STATE_CONTENT" ]]; then
    mkdir -p "$SANDBOX_PROJECT/.claude"
    echo "$SETUP_STATE_CONTENT" | jq '.' > "$SANDBOX_PROJECT/.claude/$SETUP_STATE_FILE"
    echo "  Created state file: .claude/$SETUP_STATE_FILE" >&2
fi

# Create files if specified
SETUP_FILES=$(echo "$TEST_CASE" | jq -r '.setup.files // {}')
if [[ "$SETUP_FILES" != "{}" ]]; then
    echo "$SETUP_FILES" | jq -r 'to_entries[] | "\(.key)|\(.value)"' | while IFS='|' read -r filepath content; do
        mkdir -p "$(dirname "$SANDBOX_PROJECT/$filepath")"
        echo "$content" > "$SANDBOX_PROJECT/$filepath"
        echo "  Created file: $filepath" >&2
    done
fi

# =============================================================================
# EXECUTE: Run Claude with test prompt
# =============================================================================

# macOS date doesn't support %3N, use python3 for millisecond precision
_millis() { python3 -c "import time; print(int(time.time()*1000))"; }
START_TIME=$(_millis)
STDOUT_FILE="$SANDBOX_ROOT/test-stdout.log"
STDERR_FILE="$SANDBOX_ROOT/test-stderr.log"

# Determine timeout command (macOS uses gtimeout from GNU coreutils)
TIMEOUT_CMD=""
if command -v timeout &>/dev/null; then
    TIMEOUT_CMD="timeout $TIMEOUT"
elif command -v gtimeout &>/dev/null; then
    TIMEOUT_CMD="gtimeout $TIMEOUT"
else
    echo "  WARNING: No timeout command found, running without timeout" >&2
fi

# Run Claude in sandbox environment (cd to project so hooks use correct CWD)
set +e
(
    cd "$SANDBOX_PROJECT"
    env HOME="$FAKE_HOME" \
        PATH="$MOCK_BIN:$PATH" \
        SANDBOX_MODE=true \
        SANDBOX_ID="$SANDBOX_ID" \
        SANDBOX_DIR="$SANDBOX_ROOT" \
        $TIMEOUT_CMD claude -p "$PROMPT" \
            --dangerously-skip-permissions \
            --no-session-persistence \
            --output-format json \
            --model haiku \
            >"$STDOUT_FILE" 2>"$STDERR_FILE"
)
EXIT_CODE=$?
set -e

END_TIME=$(_millis)
DURATION_MS=$((END_TIME - START_TIME))

echo "  Completed in ${DURATION_MS}ms (exit code: $EXIT_CODE)" >&2

# =============================================================================
# VERIFY: Check assertions
# =============================================================================

ASSERTIONS=$(echo "$TEST_CASE" | jq -r '.assertions // []')
ASSERTION_COUNT=$(echo "$ASSERTIONS" | jq 'length')
PASSED_COUNT=0
FAILED_ASSERTIONS="[]"

for i in $(seq 0 $((ASSERTION_COUNT - 1))); do
    ASSERTION=$(echo "$ASSERTIONS" | jq ".[$i]")
    ASSERTION_TYPE=$(echo "$ASSERTION" | jq -r '.type')

    case "$ASSERTION_TYPE" in
        file_exists)
            FILEPATH=$(echo "$ASSERTION" | jq -r '.path')
            if [[ -f "$SANDBOX_PROJECT/$FILEPATH" ]]; then
                PASSED_COUNT=$((PASSED_COUNT + 1))
                echo "  [PASS] file_exists: $FILEPATH" >&2
            else
                FAILED_ASSERTIONS=$(echo "$FAILED_ASSERTIONS" | jq ". + [{\"type\": \"$ASSERTION_TYPE\", \"path\": \"$FILEPATH\", \"reason\": \"File does not exist\"}]")
                echo "  [FAIL] file_exists: $FILEPATH" >&2
            fi
            ;;

        file_not_exists)
            FILEPATH=$(echo "$ASSERTION" | jq -r '.path')
            if [[ ! -f "$SANDBOX_PROJECT/$FILEPATH" ]]; then
                PASSED_COUNT=$((PASSED_COUNT + 1))
                echo "  [PASS] file_not_exists: $FILEPATH" >&2
            else
                FAILED_ASSERTIONS=$(echo "$FAILED_ASSERTIONS" | jq ". + [{\"type\": \"$ASSERTION_TYPE\", \"path\": \"$FILEPATH\", \"reason\": \"File exists but should not\"}]")
                echo "  [FAIL] file_not_exists: $FILEPATH" >&2
            fi
            ;;

        file_contains)
            FILEPATH=$(echo "$ASSERTION" | jq -r '.path')
            PATTERN=$(echo "$ASSERTION" | jq -r '.pattern')
            if [[ -f "$SANDBOX_PROJECT/$FILEPATH" ]] && grep -qE "$PATTERN" "$SANDBOX_PROJECT/$FILEPATH" 2>/dev/null; then
                PASSED_COUNT=$((PASSED_COUNT + 1))
                echo "  [PASS] file_contains: $FILEPATH =~ $PATTERN" >&2
            else
                FAILED_ASSERTIONS=$(echo "$FAILED_ASSERTIONS" | jq ". + [{\"type\": \"$ASSERTION_TYPE\", \"path\": \"$FILEPATH\", \"pattern\": \"$PATTERN\", \"reason\": \"File missing or pattern not found\"}]")
                echo "  [FAIL] file_contains: $FILEPATH =~ $PATTERN" >&2
            fi
            ;;

        output_contains)
            PATTERN=$(echo "$ASSERTION" | jq -r '.pattern')
            if grep -qE "$PATTERN" "$STDOUT_FILE" "$STDERR_FILE" 2>/dev/null; then
                PASSED_COUNT=$((PASSED_COUNT + 1))
                echo "  [PASS] output_contains: $PATTERN" >&2
            else
                FAILED_ASSERTIONS=$(echo "$FAILED_ASSERTIONS" | jq ". + [{\"type\": \"$ASSERTION_TYPE\", \"pattern\": \"$PATTERN\", \"reason\": \"Pattern not found in output\"}]")
                echo "  [FAIL] output_contains: $PATTERN" >&2
            fi
            ;;

        output_not_contains)
            PATTERN=$(echo "$ASSERTION" | jq -r '.pattern')
            if ! grep -qE "$PATTERN" "$STDOUT_FILE" "$STDERR_FILE" 2>/dev/null; then
                PASSED_COUNT=$((PASSED_COUNT + 1))
                echo "  [PASS] output_not_contains: $PATTERN" >&2
            else
                FAILED_ASSERTIONS=$(echo "$FAILED_ASSERTIONS" | jq ". + [{\"type\": \"$ASSERTION_TYPE\", \"pattern\": \"$PATTERN\", \"reason\": \"Pattern found in output but should not be\"}]")
                echo "  [FAIL] output_not_contains: $PATTERN" >&2
            fi
            ;;

        state_field)
            STATE_FILE=$(echo "$ASSERTION" | jq -r '.file')
            FIELD=$(echo "$ASSERTION" | jq -r '.field')
            EXPECTED=$(echo "$ASSERTION" | jq -r '.expected')
            ACTUAL=$(jq -r ".$FIELD" "$SANDBOX_PROJECT/.claude/$STATE_FILE" 2>/dev/null || echo "null")
            if [[ "$ACTUAL" == "$EXPECTED" ]]; then
                PASSED_COUNT=$((PASSED_COUNT + 1))
                echo "  [PASS] state_field: $STATE_FILE.$FIELD = $EXPECTED" >&2
            else
                FAILED_ASSERTIONS=$(echo "$FAILED_ASSERTIONS" | jq ". + [{\"type\": \"$ASSERTION_TYPE\", \"file\": \"$STATE_FILE\", \"field\": \"$FIELD\", \"expected\": \"$EXPECTED\", \"actual\": \"$ACTUAL\"}]")
                echo "  [FAIL] state_field: $STATE_FILE.$FIELD = $ACTUAL (expected $EXPECTED)" >&2
            fi
            ;;

        exit_code)
            EXPECTED_CODE=$(echo "$ASSERTION" | jq -r '.code')
            if [[ "$EXIT_CODE" -eq "$EXPECTED_CODE" ]]; then
                PASSED_COUNT=$((PASSED_COUNT + 1))
                echo "  [PASS] exit_code: $EXIT_CODE" >&2
            else
                FAILED_ASSERTIONS=$(echo "$FAILED_ASSERTIONS" | jq ". + [{\"type\": \"$ASSERTION_TYPE\", \"expected\": $EXPECTED_CODE, \"actual\": $EXIT_CODE}]")
                echo "  [FAIL] exit_code: $EXIT_CODE (expected $EXPECTED_CODE)" >&2
            fi
            ;;

        *)
            echo "  [SKIP] Unknown assertion type: $ASSERTION_TYPE" >&2
            ;;
    esac
done

# Determine overall status
if [[ "$PASSED_COUNT" -eq "$ASSERTION_COUNT" ]]; then
    STATUS="passed"
else
    STATUS="failed"
fi

# Output result as compact single-line JSON (required for tail -1 capture in run-all-tests.sh)
jq -cn \
    --arg name "$TEST_CASE_NAME" \
    --arg description "$DESCRIPTION" \
    --arg status "$STATUS" \
    --argjson duration_ms "$DURATION_MS" \
    --argjson exit_code "$EXIT_CODE" \
    --argjson passed "$PASSED_COUNT" \
    --argjson total "$ASSERTION_COUNT" \
    --argjson failed_assertions "$FAILED_ASSERTIONS" \
    '{
        name: $name,
        description: $description,
        status: $status,
        duration_ms: $duration_ms,
        exit_code: $exit_code,
        assertions: {
            passed: $passed,
            total: $total,
            failed: $failed_assertions
        }
    }'
