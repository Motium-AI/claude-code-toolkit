#!/usr/bin/env python3
"""
PermissionRequest hook for ALL tools during autonomous execution modes.

Auto-approves tool permissions when godo or appfix mode is detected,
enabling truly autonomous execution without permission prompts.

Detection: Checks for .claude/godo-state.json or .claude/appfix-state.json
           in cwd, or GODO_ACTIVE/APPFIX_ACTIVE env vars.

Hook event: PermissionRequest
Matcher: * (wildcard - matches all tools)
"""
import json
import os
import sys
from pathlib import Path

# Add hooks directory to path for shared imports
sys.path.insert(0, str(Path(__file__).parent))
from _common import is_autonomous_mode_active, log_debug


def main():
    # Try to read stdin, but handle empty input
    stdin_data = sys.stdin.read()

    if stdin_data.strip():
        try:
            input_data = json.loads(stdin_data)
            cwd = input_data.get("cwd", os.getcwd())
        except json.JSONDecodeError as e:
            log_debug("Failed to parse JSON input, using getcwd()",
                     hook_name="appfix-auto-approve", error=str(e))
            cwd = os.getcwd()
    else:
        # No stdin input - use current working directory
        cwd = os.getcwd()
        log_debug("No stdin input, using getcwd()", hook_name="appfix-auto-approve")

    # Only process if autonomous mode is active (godo or appfix)
    if not is_autonomous_mode_active(cwd):
        log_debug(f"Autonomous mode not active for cwd={cwd}",
                 hook_name="appfix-auto-approve")
        sys.exit(0)  # Silent passthrough - normal approval flow

    # Auto-approve the tool
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PermissionRequest",
            "decision": {
                "behavior": "allow"
            }
        }
    }

    log_debug(f"Auto-approving (cwd={cwd})", hook_name="appfix-auto-approve")
    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
