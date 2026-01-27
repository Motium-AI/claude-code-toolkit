#!/usr/bin/env python3
"""
PermissionRequest hook to auto-approve ExitPlanMode during appfix sessions.

When APPFIX_ACTIVE=true, this hook auto-approves the ExitPlanMode permission
request, bypassing the "Would you like to proceed?" dialog.

This is the CRITICAL hook that enables truly autonomous plan mode exit.
Without it, appfix gets stuck waiting for user confirmation.

Hook event: PermissionRequest
Matcher: ExitPlanMode

Exit codes:
  0 - Decision made (allow or deny via hookSpecificOutput)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def is_appfix_active(cwd: str) -> bool:
    """Check if appfix is active via env var OR state file."""
    # Method 1: Environment variable (backwards compatibility)
    if os.environ.get("APPFIX_ACTIVE", "").lower() in ("true", "1", "yes"):
        return True

    # Method 2: State file exists in project
    if cwd:
        state_file = Path(cwd) / ".claude" / "appfix-state.json"
        if state_file.exists():
            return True

    return False


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    cwd = input_data.get("cwd", "")

    # Only process ExitPlanMode
    if tool_name != "ExitPlanMode":
        sys.exit(0)

    if not is_appfix_active(cwd):
        # Not in appfix mode - use standard behavior (show dialog)
        sys.exit(0)

    # Appfix is active - auto-approve the plan mode exit
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PermissionRequest",
            "decision": {
                "behavior": "allow"
            }
        }
    }

    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
