#!/usr/bin/env python3
"""
PermissionRequest hook for auto-approving permission dialogs during autonomous execution.

This hook runs when Claude Code is about to show a permission dialog (e.g., ExitPlanMode
confirmation). Unlike PreToolUse hooks which bypass the permission system entirely,
PermissionRequest hooks intercept the dialog itself.

The key difference from PreToolUse:
- PreToolUse output:       {"permissionDecision": "allow"}
- PermissionRequest output: {"decision": {"behavior": "allow"}}

Hook event: PermissionRequest
Matcher: * (wildcard - matches all permission dialogs)
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add hooks directory to path for shared imports
sys.path.insert(0, str(Path(__file__).parent))
from _common import (
    is_autonomous_mode_active,
    get_autonomous_state,
    is_state_expired,
    log_debug,
)

# Invocation log for debugging
INVOCATION_LOG = Path("/tmp/permissionrequest-auto-approve-invocations.log")


def log_invocation(message: str, cwd: str = "", tool_name: str = "") -> None:
    """Log invocation to file for debugging."""
    try:
        with open(INVOCATION_LOG, "a") as f:
            f.write(
                f"{datetime.now().isoformat()} - {message}, "
                f"pid={os.getpid()}, cwd={cwd}, tool={tool_name}\n"
            )
    except Exception:
        pass


def main():
    # Try to read stdin
    stdin_data = sys.stdin.read()

    if stdin_data.strip():
        try:
            input_data = json.loads(stdin_data)
            cwd = input_data.get("cwd", os.getcwd())
            tool_name = input_data.get("tool_name", "unknown")
            session_id = input_data.get("session_id", "")
        except json.JSONDecodeError as e:
            log_debug(
                "Failed to parse JSON input, using getcwd()",
                hook_name="permissionrequest-auto-approve",
                error=str(e),
            )
            cwd = os.getcwd()
            tool_name = "unknown"
            session_id = ""
    else:
        # No stdin input - use current working directory
        cwd = os.getcwd()
        tool_name = "unknown"
        session_id = ""
        log_debug(
            "No stdin input, using getcwd()", hook_name="permissionrequest-auto-approve"
        )

    log_invocation(f"Hook invoked for tool={tool_name}", cwd=cwd, tool_name=tool_name)

    # Only process if autonomous mode is active (godo or appfix)
    # Pass session_id to enable cross-directory trust for same session
    if not is_autonomous_mode_active(cwd, session_id):
        log_debug(
            f"Autonomous mode not active for cwd={cwd}",
            hook_name="permissionrequest-auto-approve",
        )
        log_invocation("Passthrough - autonomous mode not active", cwd=cwd, tool_name=tool_name)
        sys.exit(0)  # Silent passthrough - show normal permission dialog

    # Defense-in-depth: verify state is not expired (TTL check)
    state, state_type = get_autonomous_state(cwd, session_id)
    if state is None or is_state_expired(state):
        log_debug(
            f"State expired or missing (defense-in-depth TTL check), cwd={cwd}",
            hook_name="permissionrequest-auto-approve",
        )
        log_invocation("Passthrough - state expired", cwd=cwd, tool_name=tool_name)
        sys.exit(0)  # Expired state - no auto-approval

    # Auto-approve the permission dialog using PermissionRequest decision format
    # This uses {"decision": {"behavior": "allow"}} instead of {"permissionDecision": "allow"}
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PermissionRequest",
            "decision": {"behavior": "allow"},
        }
    }

    log_debug(
        f"Auto-approving permission dialog for tool={tool_name} (cwd={cwd}, mode={state_type})",
        hook_name="permissionrequest-auto-approve",
    )
    log_invocation(f"AUTO-APPROVED by {state_type} mode", cwd=cwd, tool_name=tool_name)
    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
