#!/usr/bin/env python3
"""
PostToolUse hook for ExitPlanMode - injects autonomous execution reminder.

All detailed instructions are in SKILL.md. This hook just reminds
the model to execute immediately and not ask permission.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import is_appfix_active


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if input_data.get("tool_name", "") != "ExitPlanMode":
        sys.exit(0)

    cwd = input_data.get("cwd", "")
    mode = "APPFIX FIX-VERIFY LOOP" if is_appfix_active(cwd) else "AUTONOMOUS EXECUTION"

    context = (
        f"You are in {mode} MODE. Execute the plan NOW.\n"
        "Do NOT ask permission. Do NOT suggest 'next steps'.\n"
        "Continue working until .claude/completion-checkpoint.json passes validation."
    )

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": context,
        }
    }))
    sys.exit(0)


if __name__ == "__main__":
    main()
