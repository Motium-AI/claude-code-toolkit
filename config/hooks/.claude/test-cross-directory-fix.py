#!/usr/bin/env python3
"""
Test script to verify cross-directory auto-approval fix.

This script simulates the scenario where:
1. An appfix session starts in directory A
2. The session moves to directory B (not under A)
3. Auto-approval should still work because session_id matches

Run this from the config/hooks directory.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add hooks directory to path for shared imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from _common import (
    is_autonomous_mode_active,
    get_autonomous_state,
    _is_cwd_under_origin,
)


def create_test_user_state(session_id: str, origin_project: str):
    """Create a test user-level state file."""
    user_state = {
        "started_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "last_activity_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "session_id": session_id,
        "origin_project": origin_project,
        "plan_mode_completed": True,  # Simulate plan mode was completed
    }

    user_state_path = Path.home() / ".claude" / "appfix-state.json"
    user_state_path.parent.mkdir(parents=True, exist_ok=True)
    user_state_path.write_text(json.dumps(user_state, indent=2))
    print(f"Created user-level state: {user_state_path}")
    return user_state


def cleanup_test_state():
    """Remove test state file."""
    user_state_path = Path.home() / ".claude" / "appfix-state.json"
    if user_state_path.exists():
        user_state_path.unlink()
        print(f"Cleaned up: {user_state_path}")


def test_cross_directory_trust():
    """Test that session_id trust works across directories."""
    print("\n" + "=" * 60)
    print("Testing Cross-Directory Auto-Approval Fix")
    print("=" * 60)

    # Setup
    origin_project = "/tmp/test-origin-project"
    new_directory = "/tmp/test-new-directory"
    session_id = "test-session-12345"

    # Create test user state
    user_state = create_test_user_state(session_id, origin_project)

    try:
        # Test 1: Same session, different directory - should PASS
        print("\n[Test 1] Same session_id, different directory (should PASS)")
        result = _is_cwd_under_origin(new_directory, user_state, session_id)
        print(f"  _is_cwd_under_origin('{new_directory}', state, '{session_id}'): {result}")
        assert result == True, "FAILED: Same session should be trusted"
        print("  ✓ PASSED")

        # Test 2: No session_id, different directory - should FAIL
        print("\n[Test 2] No session_id, different directory (should FAIL)")
        result = _is_cwd_under_origin(new_directory, user_state, "")
        print(f"  _is_cwd_under_origin('{new_directory}', state, ''): {result}")
        assert result == False, "FAILED: No session should fall back to directory check"
        print("  ✓ PASSED")

        # Test 3: Different session_id, different directory - should FAIL
        print("\n[Test 3] Different session_id, different directory (should FAIL)")
        result = _is_cwd_under_origin(new_directory, user_state, "different-session")
        print(f"  _is_cwd_under_origin('{new_directory}', state, 'different-session'): {result}")
        assert result == False, "FAILED: Different session should not be trusted"
        print("  ✓ PASSED")

        # Test 4: is_autonomous_mode_active with session_id
        print("\n[Test 4] is_autonomous_mode_active with session_id (should PASS)")
        result = is_autonomous_mode_active(new_directory, session_id)
        print(f"  is_autonomous_mode_active('{new_directory}', '{session_id}'): {result}")
        assert result == True, "FAILED: Same session should activate autonomous mode"
        print("  ✓ PASSED")

        # Test 5: is_autonomous_mode_active without session_id
        print("\n[Test 5] is_autonomous_mode_active without session_id (should FAIL)")
        result = is_autonomous_mode_active(new_directory, "")
        print(f"  is_autonomous_mode_active('{new_directory}', ''): {result}")
        assert result == False, "FAILED: No session should not activate autonomous mode"
        print("  ✓ PASSED")

        # Test 6: get_autonomous_state with session_id
        print("\n[Test 6] get_autonomous_state with session_id (should return appfix)")
        state, state_type = get_autonomous_state(new_directory, session_id)
        print(f"  get_autonomous_state('{new_directory}', '{session_id}'): ({state is not None}, {state_type})")
        assert state is not None, "FAILED: Should find state"
        assert state_type == "appfix", f"FAILED: Should be 'appfix', got {state_type}"
        assert state.get("plan_mode_completed") == True, "FAILED: plan_mode_completed should be True"
        print("  ✓ PASSED")

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED!")
        print("=" * 60)

    finally:
        cleanup_test_state()


if __name__ == "__main__":
    test_cross_directory_trust()
