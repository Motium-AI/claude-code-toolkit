#!/usr/bin/env python3
"""
PostToolUse hook for Skill tool - reminds Claude to continue autonomous workflows.

When appfix/build mode is active and Claude invokes a skill (like /heavy),
this hook fires after the skill completes to remind Claude that it's still
in an autonomous fix-verify loop and should continue.

Hook event: PostToolUse (matcher: Skill)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Add hooks directory to path for shared imports
sys.path.insert(0, str(Path(__file__).parent))
from _state import is_autonomous_mode_active, is_appfix_active, is_build_active, is_episode_active, is_go_active


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    cwd = input_data.get("cwd", "") or os.getcwd()

    if tool_name != "Skill":
        sys.exit(0)

    # Only inject context if in autonomous mode
    if not is_autonomous_mode_active(cwd):
        sys.exit(0)

    # Determine which mode is active for appropriate messaging
    if is_appfix_active(cwd):
        mode_name = "APPFIX"
        loop_type = "fix-verify"
    elif is_build_active(cwd):
        mode_name = "BUILD"
        loop_type = "task execution"
    elif is_go_active(cwd):
        mode_name = "GO"
        loop_type = "fast execution"
    elif is_episode_active(cwd):
        mode_name = "EPISODE"
        loop_type = "episode generation"
    else:
        sys.exit(0)

    context = f"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║  {mode_name} MODE STILL ACTIVE - SKILL COMPLETED                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝

The skill you invoked has completed. You are STILL in {mode_name} autonomous mode.

CONTINUE THE {loop_type.upper()} LOOP:
1. Apply any insights from the completed skill
2. Execute the planned changes (Edit tool)
3. Commit and push changes
4. Deploy if required
5. Verify in browser
6. Update completion checkpoint

Do NOT stop here. The {loop_type} loop continues until verification is complete.
"""

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": context,
        }
    }

    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
