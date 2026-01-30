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
from datetime import datetime, timezone
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
    session_id = input_data.get("session_id", "")

    # Only process ExitPlanMode
    if tool_name != "ExitPlanMode":
        sys.exit(0)

    log_debug(
        "ExitPlanMode detected, searching for state file",
        hook_name="plan-mode-tracker",
        parsed_data={"cwd": cwd, "tool_name": tool_name},
    )

    # Check if autonomous mode is active
    # Pass session_id to enable cross-directory trust for same session
    state, state_type = get_autonomous_state(cwd, session_id)
    if not state:
        log_debug(
            "No autonomous state file found - not in godo/appfix mode",
            hook_name="plan-mode-tracker",
            parsed_data={"cwd": cwd},
        )
        sys.exit(0)

    # Determine state filename
    # Map state_type to filename (repair uses appfix-state.json for backward compat)
    STATE_TYPE_TO_FILENAME = {
        "forge": "forge-state.json",
        "repair": "appfix-state.json",
        "burndown": "burndown-state.json",
    }
    state_filename = STATE_TYPE_TO_FILENAME.get(state_type, f"{state_type}-state.json")

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

    # CRITICAL: Also mirror plan_mode_completed to user-level state
    # This enables cross-directory workflows where the session moves to a new
    # directory that has no project-level state file. The user-level state
    # becomes the "session passport" that carries workflow state across directories.
    #
    # MULTI-SESSION SUPPORT: Update BOTH the legacy root-level fields AND the
    # session entry in the sessions dict. This ensures backward compatibility
    # while supporting multiple parallel sessions.
    user_state_path = Path.home() / ".claude" / state_filename
    if user_state_path.exists():
        try:
            user_state = json.loads(user_state_path.read_text())
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

            # Update legacy root-level fields (backward compatibility)
            user_state["plan_mode_completed"] = True
            user_state["last_activity_at"] = now

            # Update session entry in sessions dict (multi-session support)
            if session_id and "sessions" in user_state:
                sessions = user_state.get("sessions", {})
                if session_id in sessions:
                    sessions[session_id]["plan_mode_completed"] = True
                    sessions[session_id]["last_activity_at"] = now
                    log_debug(
                        f"Updated session {session_id} in sessions dict",
                        hook_name="plan-mode-tracker",
                        parsed_data={"session_id": session_id},
                    )

            user_state_path.write_text(json.dumps(user_state, indent=2))
            log_debug(
                "Mirrored plan_mode_completed to user-level state",
                hook_name="plan-mode-tracker",
                parsed_data={"user_state_path": str(user_state_path)},
            )
        except (json.JSONDecodeError, IOError) as e:
            log_debug(
                "Failed to mirror plan_mode_completed to user-level state",
                hook_name="plan-mode-tracker",
                error=e,
            )

    sys.exit(0)


if __name__ == "__main__":
    main()
