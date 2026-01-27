#!/usr/bin/env python3
"""
PreToolUse hook to enforce plan mode on first iteration of godo/appfix.

This hook BLOCKS Edit/Write tools until plan mode has been completed (indicated
by plan_mode_completed: true in the state file). This ensures Claude follows
the Phase 0.5 workflow before making code changes.

IMPORTANT: Uses PreToolUse (not PermissionRequest) because PreToolUse fires
before EVERY tool execution, while PermissionRequest only fires when a
permission dialog would be shown.

Hook event: PreToolUse
Matcher: Edit|Write

Exit codes:
  0 - Decision made (deny via hookSpecificOutput or silent passthrough)
"""
import json
import sys
from pathlib import Path

# Add hooks directory to path for shared imports
sys.path.insert(0, str(Path(__file__).parent))
from _common import get_autonomous_state, is_autonomous_mode_active, log_debug


BLOCK_MESSAGE = """
╔═══════════════════════════════════════════════════════════════════════════════╗
║  ⚠️  PLAN MODE REQUIRED - FIRST ITERATION                                     ║
╚═══════════════════════════════════════════════════════════════════════════════╝

This is the first iteration of godo/appfix. You MUST explore the codebase
and create a plan before making code changes.

┌─────────────────────────────────────────────────────────────────────────────────┐
│  REQUIRED WORKFLOW (Phase 0.5):                                                 │
│                                                                                 │
│  1. Call EnterPlanMode                                                          │
│  2. Explore codebase architecture, recent commits, configs                      │
│  3. Write implementation plan to the plan file                                  │
│  4. Call ExitPlanMode                                                           │
│                                                                                 │
│  THEN your edit will be allowed.                                                │
└─────────────────────────────────────────────────────────────────────────────────┘

WHY THIS MATTERS:
- Understanding the codebase prevents breaking changes
- Plan mode forces you to think before coding
- Multi-file changes need architectural context

The state file will be updated automatically when you exit plan mode.
""".strip()


def is_plan_file(file_path: str) -> bool:
    """Check if the file is a plan file that should be allowed during plan mode."""
    if not file_path:
        return False
    # Plan files are in ~/.claude/plans/ or .claude/plans/
    return "/plans/" in file_path or file_path.endswith("/plans")


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        log_debug("Failed to parse JSON input", hook_name="plan-mode-enforcer", error=e)
        sys.exit(0)

    # PreToolUse uses tool_name (not toolName)
    cwd = input_data.get("cwd", "")
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    # Only process Edit/Write tools
    if tool_name not in ("Edit", "Write"):
        sys.exit(0)  # Silent passthrough

    # CRITICAL: Always allow writes to plan files during plan mode
    # This allows Claude to write its implementation plan
    if is_plan_file(file_path):
        sys.exit(0)  # Allow plan file writes

    # Only process if autonomous mode is active (godo or appfix)
    if not is_autonomous_mode_active(cwd):
        sys.exit(0)  # Not in godo/appfix mode, no enforcement

    # Check if plan mode has been completed
    state, state_type = get_autonomous_state(cwd)
    if not state:
        sys.exit(0)  # No state file, passthrough

    plan_mode_completed = state.get("plan_mode_completed", False)
    iteration = state.get("iteration", 1)

    # Only enforce on first iteration
    if iteration > 1:
        sys.exit(0)  # Subsequent iterations don't require plan mode again

    # Check if plan mode has been completed
    if plan_mode_completed:
        sys.exit(0)  # Plan mode done, allow edit

    # Block the edit with instructions
    log_debug(
        f"Blocking {tool_name} - plan mode not completed",
        hook_name="plan-mode-enforcer",
        parsed_data={"state_type": state_type, "iteration": iteration},
    )

    # PreToolUse uses permissionDecision: "deny" (not behavior: "block")
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": BLOCK_MESSAGE,
        }
    }

    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
