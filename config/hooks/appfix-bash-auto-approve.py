#!/usr/bin/env python3
"""
PermissionRequest hook for Bash commands during appfix.

Auto-approves Bash commands when appfix mode is detected, enabling
truly autonomous execution without permission prompts.

Detection: Checks for .claude/appfix-state.json in cwd or APPFIX_ACTIVE env var.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def is_appfix_active(cwd: str) -> bool:
    """Check if appfix mode is active via state file or env var."""
    # Primary: Check for state file in project
    state_file = Path(cwd) / ".claude" / "appfix-state.json"
    if state_file.exists():
        return True

    # Fallback: Check environment variable
    if os.environ.get("APPFIX_ACTIVE", "").lower() == "true":
        return True

    return False


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    cwd = input_data.get("cwd", "")
    tool_name = input_data.get("tool_name", "")

    # Only handle Bash permission requests
    if tool_name != "Bash":
        sys.exit(0)

    # Only auto-approve if appfix is active
    if not is_appfix_active(cwd):
        sys.exit(0)

    # Auto-approve the Bash command
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
