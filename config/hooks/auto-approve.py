#!/usr/bin/env python3
"""
Unified Auto-Approve Hook (PreToolUse + PermissionRequest)

Single hook handles both event types during autonomous execution.
Replaces pretooluse-auto-approve.py + permissionrequest-auto-approve.py.

Hook events: PreToolUse (*), PermissionRequest (*)

Output format differs by event type:
  PreToolUse:        {"permissionDecision": "allow"}
  PermissionRequest: {"decision": {"behavior": "allow"}}
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _common import is_state_expired, log_debug
from _session import is_autonomous_mode_active, get_autonomous_state


def main():
    stdin_data = sys.stdin.read()
    if not stdin_data.strip():
        sys.exit(0)

    try:
        input_data = json.loads(stdin_data)
    except json.JSONDecodeError:
        sys.exit(0)

    cwd = input_data.get("cwd", os.getcwd())
    tool_name = input_data.get("tool_name", "unknown")
    session_id = input_data.get("session_id", "")
    hook_event = input_data.get("hook_event_name", "")

    if not is_autonomous_mode_active(cwd, session_id):
        sys.exit(0)

    state, mode = get_autonomous_state(cwd, session_id)
    if state is None or is_state_expired(state):
        sys.exit(0)

    # Detect event type and use correct output format
    if hook_event == "PermissionRequest":
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PermissionRequest",
                "decision": {"behavior": "allow"},
            }
        }
    else:
        # PreToolUse (default)
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
            }
        }

    log_debug(
        f"Auto-approving {hook_event or 'PreToolUse'} tool={tool_name} mode={mode}",
        hook_name="auto-approve",
    )
    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
