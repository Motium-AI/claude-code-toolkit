#!/usr/bin/env python3
"""
PreToolUse hook to enforce Lite Heavy execution before ExitPlanMode for /forge.

Blocks ExitPlanMode until:
1. heavy/SKILL.md has been read
2. "First Principles" Task agent has been launched
3. "AGI-Pilled" Task agent has been launched

The tracking is done by lite-heavy-tracker.py (PostToolUse hook).
This hook only checks the state and blocks if requirements aren't met.

Hook event: PreToolUse
Matcher: ExitPlanMode

Exit codes:
  0 - Decision made (deny via hookSpecificOutput or silent passthrough)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Add hooks directory to path for shared imports
sys.path.insert(0, str(Path(__file__).parent))
from _common import get_autonomous_state, log_debug


BLOCK_MESSAGE = """
╔═══════════════════════════════════════════════════════════════════════════════╗
║  ⚠️  LITE HEAVY PLANNING REQUIRED - /forge                                    ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Before exiting plan mode, you MUST complete Lite Heavy planning:

┌─────────────────────────────────────────────────────────────────────────────────┐
│  REQUIRED STEPS:                                                                │
│                                                                                 │
│  {step1}  1. Read ~/.claude/skills/heavy/SKILL.md (get agent prompts)           │
│  {step2}  2. Launch Task: "First Principles Analysis" (from heavy)              │
│  {step3}  3. Launch Task: "AGI-Pilled Analysis" (from heavy)                    │
│  4. Synthesize their responses into your plan                                   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘

WHY LITE HEAVY?
- First Principles asks: "What can be deleted? What's over-engineered?"
- AGI-Pilled asks: "What would god-tier AI implementation look like?"
- Together they prevent both over-engineering AND under-ambition

Complete the missing steps, then ExitPlanMode again.
""".strip()


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        log_debug("Failed to parse JSON input", hook_name="lite-heavy-enforcer", error=e)
        sys.exit(0)

    cwd = input_data.get("cwd", "") or os.getcwd()
    tool_name = input_data.get("tool_name", "")
    session_id = input_data.get("session_id", "")

    # Only process ExitPlanMode
    if tool_name != "ExitPlanMode":
        sys.exit(0)

    # Only process if forge is active
    state, state_type = get_autonomous_state(cwd, session_id)
    if state_type != "forge":
        sys.exit(0)

    # Only enforce on first iteration
    iteration = state.get("iteration", 1)
    if iteration > 1:
        sys.exit(0)

    # Check Lite Heavy requirements
    lite_heavy = state.get("lite_heavy_verification", {})
    heavy_skill_read = lite_heavy.get("heavy_skill_read", False)
    first_principles_launched = lite_heavy.get("first_principles_launched", False)
    agi_pilled_launched = lite_heavy.get("agi_pilled_launched", False)

    # If all requirements met, allow ExitPlanMode
    if heavy_skill_read and first_principles_launched and agi_pilled_launched:
        log_debug(
            "Lite Heavy requirements met, allowing ExitPlanMode",
            hook_name="lite-heavy-enforcer"
        )
        sys.exit(0)

    # Block with specific feedback
    step1 = "✓" if heavy_skill_read else "✗"
    step2 = "✓" if first_principles_launched else "✗"
    step3 = "✓" if agi_pilled_launched else "✗"

    message = BLOCK_MESSAGE.format(step1=step1, step2=step2, step3=step3)

    log_debug(
        "Blocking ExitPlanMode - Lite Heavy incomplete",
        hook_name="lite-heavy-enforcer",
        parsed_data={
            "heavy_skill_read": heavy_skill_read,
            "first_principles_launched": first_principles_launched,
            "agi_pilled_launched": agi_pilled_launched,
        }
    )

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": message,
        }
    }

    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
