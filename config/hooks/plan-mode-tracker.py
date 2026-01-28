#!/usr/bin/env python3
"""
PostToolUse hook to track plan mode completion for godo/appfix.

When ExitPlanMode is called during godo/appfix, this hook updates the state
file to set plan_mode_completed: true, allowing subsequent Edit/Write tools
to proceed without being blocked by plan-mode-enforcer.py.

Hook event: PostToolUse
Matcher: ExitPlanMode

Output: No stdout on success (avoids hookSpecificOutput format issues).
        Warnings to stderr on failure.

Exit codes:
  0 - Always succeeds (informational hook)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Add hooks directory to path for shared imports
sys.path.insert(0, str(Path(__file__).parent))
from _common import (
    get_autonomous_state,
    log_debug,
    update_state_file,
)


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        log_debug("Failed to parse JSON input", hook_name="plan-mode-tracker", error=e)
        sys.exit(0)

    cwd = input_data.get("cwd", "") or os.getcwd()
    tool_name = input_data.get("tool_name", "")

    # Only process ExitPlanMode
    if tool_name != "ExitPlanMode":
        sys.exit(0)

    log_debug(
        "ExitPlanMode detected, searching for state file",
        hook_name="plan-mode-tracker",
        parsed_data={"cwd": cwd, "tool_name": tool_name},
    )

    # Check if autonomous mode is active
    state, state_type = get_autonomous_state(cwd)
    if not state:
        log_debug(
            "No autonomous state file found - not in godo/appfix mode",
            hook_name="plan-mode-tracker",
            parsed_data={"cwd": cwd},
        )
        sys.exit(0)

    # Determine state filename
    state_filename = f"{state_type}-state.json"

    # Update state file to mark plan mode as completed
    success = update_state_file(cwd, state_filename, {"plan_mode_completed": True})

    if success:
        log_debug(
            "Plan mode marked as completed",
            hook_name="plan-mode-tracker",
            parsed_data={
                "state_type": state_type,
                "state_file": state_filename,
                "cwd": cwd,
            },
        )
        # No stdout output - avoids hookSpecificOutput format issues with Claude Code.
        # The state file update is the only side effect needed.
    else:
        log_debug(
            "Failed to update state file",
            hook_name="plan-mode-tracker",
            parsed_data={
                "state_type": state_type,
                "state_file": state_filename,
                "cwd": cwd,
            },
        )
        # Warn on stderr (doesn't interfere with hook output parsing)
        print(
            f"[plan-mode-tracker] WARNING: Failed to update {state_filename} "
            f"with plan_mode_completed=true. You may need to manually update "
            f".claude/{state_filename}",
            file=sys.stderr,
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
