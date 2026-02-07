#!/usr/bin/env python3
"""
PermissionRequest hook: auto-approve ExitPlanMode when in bypass permissions.

Plan mode's approval gate blocks autonomous execution even with
bypassPermissions enabled (known Claude Code bug: GitHub #5466/#7136).
This hook works around it by approving ExitPlanMode via the
PermissionRequest hook when autonomous mode is active OR when the
session's permission_mode is bypassPermissions.

Hook event: PermissionRequest
Matcher: ExitPlanMode
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _common import log_debug
from _session import is_autonomous_mode_active


def main():
    stdin_data = sys.stdin.read()
    if not stdin_data.strip():
        sys.exit(0)

    try:
        input_data = json.loads(stdin_data)
    except json.JSONDecodeError:
        sys.exit(0)

    cwd = input_data.get("cwd", os.getcwd())
    session_id = input_data.get("session_id", "")
    permission_mode = input_data.get("permission_mode", "")

    # Auto-approve if bypass permissions OR autonomous mode
    should_approve = (
        permission_mode == "bypassPermissions"
        or is_autonomous_mode_active(cwd, session_id)
    )

    if not should_approve:
        sys.exit(0)

    log_debug(
        f"Auto-approving ExitPlanMode (permission_mode={permission_mode})",
        hook_name="plan-auto-approve",
    )

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PermissionRequest",
            "decision": {"behavior": "allow"},
        }
    }))
    sys.exit(0)


if __name__ == "__main__":
    main()
