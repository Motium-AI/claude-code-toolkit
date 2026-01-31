#!/usr/bin/env python3
"""
PreToolUse hook to enforce plan mode on first iteration of build/repair.

This hook BLOCKS Edit/Write tools until plan mode has been completed.
Also detects stale sessions (>30 min old) and treats them as new problems.

Hook event: PreToolUse
Matcher: Edit|Write
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import log_debug
from _state import get_autonomous_state, is_autonomous_mode_active

STALE_SESSION_THRESHOLD = timedelta(minutes=30)

BLOCK_MESSAGE = """
PLAN MODE REQUIRED - FIRST ITERATION

This is the first iteration of an autonomous skill (/build or /repair).
You MUST explore the codebase and create a plan before making code changes.

REQUIRED WORKFLOW (Phase 0.5):
1. Call EnterPlanMode
2. Explore codebase architecture, recent commits, configs
3. Write implementation plan to the plan file
4. Call ExitPlanMode

THEN your edit will be allowed.
""".strip()


def is_plan_file(file_path: str) -> bool:
    if not file_path:
        return False
    return "/plans/" in file_path or file_path.endswith("/plans")


def is_workflow_artifact(file_path: str) -> bool:
    if not file_path:
        return False
    return "/.claude/" in file_path or file_path.startswith(".claude/")


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        log_debug("Failed to parse JSON input", hook_name="plan-mode-enforcer", error=e)
        sys.exit(0)

    cwd = input_data.get("cwd", "") or os.getcwd()
    tool_name = input_data.get("tool_name", "")
    session_id = input_data.get("session_id", "")
    tool_input = input_data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if tool_name not in ("Edit", "Write"):
        sys.exit(0)

    if is_plan_file(file_path):
        sys.exit(0)

    if is_workflow_artifact(file_path):
        log_debug(f"Allowing {tool_name} to .claude/ workflow artifact", hook_name="plan-mode-enforcer")
        sys.exit(0)

    if not is_autonomous_mode_active(cwd, session_id):
        sys.exit(0)

    state, state_type = get_autonomous_state(cwd, session_id)
    if not state:
        sys.exit(0)

    plan_mode_completed = state.get("plan_mode_completed", False)
    iteration = state.get("iteration", 1)
    last_activity = state.get("last_activity_at", "")

    # Check if session is stale (indicates new problem, not continuation)
    is_stale = False
    if last_activity:
        try:
            last_dt = datetime.fromisoformat(last_activity.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            if now - last_dt > STALE_SESSION_THRESHOLD:
                is_stale = True
                log_debug("Session is stale - treating as new problem", hook_name="plan-mode-enforcer",
                          parsed_data={"last_activity": last_activity})
        except (ValueError, TypeError) as e:
            log_debug(f"Failed to parse last_activity_at: {e}", hook_name="plan-mode-enforcer")

    # Only enforce on first iteration OR stale sessions (new problem)
    if iteration > 1 and not is_stale:
        sys.exit(0)

    if plan_mode_completed:
        sys.exit(0)

    log_debug(f"Blocking {tool_name} - plan mode not completed", hook_name="plan-mode-enforcer",
              parsed_data={"state_type": state_type, "iteration": iteration, "is_stale": is_stale})

    output = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                     "permissionDecisionReason": BLOCK_MESSAGE}}
    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
