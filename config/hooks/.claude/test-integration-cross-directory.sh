#!/bin/bash
#
# Integration test for cross-directory auto-approval fix.
#
# This test simulates:
# 1. Starting appfix in directory A
# 2. Creating a plan and exiting plan mode
# 3. Moving to directory B (not under A)
# 4. Verifying that ExitPlanMode is auto-approved (not blocked)
#
# Run from the claude-code-toolkit directory.

set -e

echo "========================================"
echo "Cross-Directory Auto-Approval Integration Test"
echo "========================================"

# Setup test directories
TEST_DIR_A="/tmp/test-appfix-dir-a-$$"
TEST_DIR_B="/tmp/test-appfix-dir-b-$$"

mkdir -p "$TEST_DIR_A/.claude"
mkdir -p "$TEST_DIR_B"

cleanup() {
    echo ""
    echo "Cleaning up..."
    rm -rf "$TEST_DIR_A" "$TEST_DIR_B"
    rm -f ~/.claude/appfix-state.json
    rm -f ~/.claude/godo-state.json
    echo "Done."
}
trap cleanup EXIT

# Get session ID (we'll simulate one)
SESSION_ID="integration-test-$(date +%s)"

echo ""
echo "Test setup:"
echo "  Directory A: $TEST_DIR_A"
echo "  Directory B: $TEST_DIR_B"
echo "  Session ID: $SESSION_ID"

# Step 1: Create state files as if appfix was started in directory A
echo ""
echo "Step 1: Creating appfix state in directory A..."

NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Project-level state in directory A
cat > "$TEST_DIR_A/.claude/appfix-state.json" << EOF
{
  "iteration": 1,
  "started_at": "$NOW",
  "last_activity_at": "$NOW",
  "session_id": "$SESSION_ID",
  "skill_type": "web",
  "plan_mode_completed": true,
  "coordinator": true,
  "services": {},
  "fixes_applied": [],
  "verification_evidence": null
}
EOF

# User-level state
cat > ~/.claude/appfix-state.json << EOF
{
  "started_at": "$NOW",
  "last_activity_at": "$NOW",
  "session_id": "$SESSION_ID",
  "origin_project": "$TEST_DIR_A",
  "plan_mode_completed": true
}
EOF

echo "  Created: $TEST_DIR_A/.claude/appfix-state.json"
echo "  Created: ~/.claude/appfix-state.json"

# Step 2: Test that auto-approval works in directory B
echo ""
echo "Step 2: Testing auto-approval hooks from directory B..."

# Simulate hook input for pretooluse-auto-approve
HOOK_INPUT=$(cat << EOF
{
  "cwd": "$TEST_DIR_B",
  "tool_name": "ExitPlanMode",
  "session_id": "$SESSION_ID"
}
EOF
)

echo "  Input to pretooluse-auto-approve.py:"
echo "$HOOK_INPUT" | head -5

# Run the hook
cd "$(dirname "$0")/.."
HOOK_OUTPUT=$(echo "$HOOK_INPUT" | python3 pretooluse-auto-approve.py 2>&1)
HOOK_EXIT_CODE=$?

echo ""
echo "  Hook output: $HOOK_OUTPUT"
echo "  Exit code: $HOOK_EXIT_CODE"

# Parse the output
if echo "$HOOK_OUTPUT" | grep -q '"permissionDecision": "allow"'; then
    echo ""
    echo "✓ SUCCESS: Auto-approval hook returned 'allow' for directory B!"
    echo "  This means the cross-directory fix is working."
else
    echo ""
    echo "✗ FAILURE: Auto-approval hook did NOT return 'allow'!"
    echo "  The cross-directory fix may not be working correctly."
    exit 1
fi

# Step 3: Verify plan-mode-enforcer doesn't block when plan_mode_completed is true
echo ""
echo "Step 3: Testing plan-mode-enforcer from directory B..."

ENFORCER_INPUT=$(cat << EOF
{
  "cwd": "$TEST_DIR_B",
  "tool_name": "Edit",
  "tool_input": {"file_path": "$TEST_DIR_B/test.py"},
  "session_id": "$SESSION_ID"
}
EOF
)

ENFORCER_OUTPUT=$(echo "$ENFORCER_INPUT" | python3 plan-mode-enforcer.py 2>&1)
ENFORCER_EXIT_CODE=$?

echo "  Enforcer output: $ENFORCER_OUTPUT"
echo "  Exit code: $ENFORCER_EXIT_CODE"

# If no output and exit 0, it means passthrough (allowed)
if [ -z "$ENFORCER_OUTPUT" ] && [ "$ENFORCER_EXIT_CODE" -eq 0 ]; then
    echo ""
    echo "✓ SUCCESS: Plan-mode-enforcer allowed the edit (passthrough)!"
else
    echo ""
    echo "  Note: Output present, checking if it's a block..."
    if echo "$ENFORCER_OUTPUT" | grep -q '"permissionDecision": "deny"'; then
        echo "✗ FAILURE: Plan-mode-enforcer blocked the edit!"
        exit 1
    else
        echo "✓ SUCCESS: Plan-mode-enforcer did not block."
    fi
fi

echo ""
echo "========================================"
echo "ALL INTEGRATION TESTS PASSED!"
echo "========================================"
echo ""
echo "The cross-directory auto-approval fix is working correctly."
echo "Sessions can now move to new directories and maintain auto-approval."
