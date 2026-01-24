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
import json
import os
import sys


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")

    # Only process ExitPlanMode
    if tool_name != "ExitPlanMode":
        sys.exit(0)

    # Check if appfix is active
    appfix_active = os.environ.get("APPFIX_ACTIVE", "").lower() in ("true", "1", "yes")

    if not appfix_active:
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
