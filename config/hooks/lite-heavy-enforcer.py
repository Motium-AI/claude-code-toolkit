#!/usr/bin/env python3
"""
PreToolUse hook to enforce Lite Heavy execution before ExitPlanMode for /build and /repair.

For /build: Blocks ExitPlanMode until ALL 4 agents have been launched.
For /repair: Blocks ExitPlanMode until 3 agents have been launched.

Hook event: PreToolUse
Matcher: ExitPlanMode
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import log_debug
from _state import get_autonomous_state

SKILL_AGENT_REQUIREMENTS = {
    "build": {"heavy_skill_read": True, "first_principles_launched": True, 
              "agi_pilled_launched": True, "dynamic_agents_required": 2},
    "repair": {"heavy_skill_read": True, "research_launched": True,
               "first_principles_launched": True, "dynamic_agents_required": 1},
}

BLOCK_MESSAGE_BUILD = """
LITE HEAVY PLANNING REQUIRED - /build

Before exiting plan mode, you MUST launch ALL 4 Opus agents.

{step1} 1. Read ~/.claude/skills/heavy/SKILL.md
{step2} 2. Launch Task: "First Principles Analysis"
{step3} 3. Launch Task: "AGI-Pilled Analysis"
{step4} 4. Launch 2 dynamic Task agents ({dynamic_count}/2 launched)

Complete ALL missing steps, then ExitPlanMode again.
""".strip()

BLOCK_MESSAGE_REPAIR = """
LITE HEAVY PLANNING REQUIRED - /repair

Before exiting plan mode, you MUST launch ALL 3 Opus agents for debugging.

{step1} 1. Read ~/.claude/skills/appfix/heavy/SKILL.md
{step2} 2. Launch Task: "Research Agent: Root cause analysis"
{step3} 3. Launch Task: "First Principles Analysis"
{step4} 4. Launch 1 dynamic Task agent ({dynamic_count}/1 launched)

Complete ALL missing steps, then ExitPlanMode again.
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

    if tool_name != "ExitPlanMode":
        sys.exit(0)

    state, state_type = get_autonomous_state(cwd, session_id)
    if state_type not in ("build", "repair"):
        sys.exit(0)

    iteration = state.get("iteration", 1)
    if iteration > 1:
        sys.exit(0)

    lite_heavy = state.get("lite_heavy_verification", {})
    heavy_skill_read = lite_heavy.get("heavy_skill_read", False)
    first_principles_launched = lite_heavy.get("first_principles_launched", False)
    agi_pilled_launched = lite_heavy.get("agi_pilled_launched", False)
    research_launched = lite_heavy.get("research_launched", False)
    dynamic_agents_launched = lite_heavy.get("dynamic_agents_launched", 0)

    requirements = SKILL_AGENT_REQUIREMENTS.get(state_type, SKILL_AGENT_REQUIREMENTS["build"])
    dynamic_required = requirements.get("dynamic_agents_required", 2)

    if state_type == "repair":
        all_met = (heavy_skill_read and research_launched and first_principles_launched
                   and dynamic_agents_launched >= dynamic_required)
    else:
        all_met = (heavy_skill_read and first_principles_launched and agi_pilled_launched
                   and dynamic_agents_launched >= dynamic_required)

    if all_met:
        log_debug("Lite Heavy requirements met, allowing ExitPlanMode", hook_name="lite-heavy-enforcer")
        sys.exit(0)

    if state_type == "repair":
        step1 = "OK" if heavy_skill_read else "X"
        step2 = "OK" if research_launched else "X"
        step3 = "OK" if first_principles_launched else "X"
        step4 = "OK" if dynamic_agents_launched >= dynamic_required else "X"
        message = BLOCK_MESSAGE_REPAIR.format(step1=step1, step2=step2, step3=step3, step4=step4,
                                               dynamic_count=dynamic_agents_launched)
    else:
        step1 = "OK" if heavy_skill_read else "X"
        step2 = "OK" if first_principles_launched else "X"
        step3 = "OK" if agi_pilled_launched else "X"
        step4 = "OK" if dynamic_agents_launched >= dynamic_required else "X"
        message = BLOCK_MESSAGE_BUILD.format(step1=step1, step2=step2, step3=step3, step4=step4,
                                              dynamic_count=dynamic_agents_launched)

    log_debug("Blocking ExitPlanMode - Lite Heavy incomplete", hook_name="lite-heavy-enforcer")

    output = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                     "permissionDecisionReason": message}}
    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
