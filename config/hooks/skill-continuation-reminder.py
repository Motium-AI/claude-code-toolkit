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
from _session import is_autonomous_mode_active, get_mode


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
    mode = get_mode(cwd) or "unknown"
    MODE_INFO = {
        "repair": ("REPAIR", "fix-verify"),
        "melt": ("MELT", "task execution"),
        "go": ("GO", "fast execution"),
        "episode": ("EPISODE", "episode generation"),
        "burndown": ("BURNDOWN", "debt elimination"),
        "improve": ("IMPROVE", "improvement"),
    }
    if mode not in MODE_INFO:
        sys.exit(0)
    mode_name, loop_type = MODE_INFO[mode]

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
