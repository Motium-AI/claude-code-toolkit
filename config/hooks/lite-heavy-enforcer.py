#!/usr/bin/env python3
"""
PreToolUse hook to enforce Lite Heavy execution before ExitPlanMode for /forge.

Blocks ExitPlanMode until ALL 4 agents have been launched:
1. heavy/SKILL.md has been read
2. "First Principles" Task agent has been launched
3. "AGI-Pilled" Task agent has been launched
4. 2 dynamic Task agents have been launched (task-specific perspectives)

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

Before exiting plan mode, you MUST launch ALL 4 Opus agents.

┌─────────────────────────────────────────────────────────────────────────────────┐
│  REQUIRED STEPS:                                                                │
│                                                                                 │
│  {step1}  1. Read ~/.claude/skills/heavy/SKILL.md (get agent prompts)           │
│  {step2}  2. Launch Task: "First Principles Analysis" (from heavy)              │
│  {step3}  3. Launch Task: "AGI-Pilled Analysis" (from heavy)                    │
│  {step4}  4. Launch 2 dynamic Task agents (task-specific perspectives)          │
│           ({dynamic_count}/2 launched)                                          │
│  5. Synthesize ALL 4 agents' responses into your plan                           │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘

⚠️  CRITICAL: Launch ALL 4 agents in a SINGLE message (one message, four Task calls).
Do NOT launch them one at a time. They must run in PARALLEL.

Dynamic agents = task-specific perspectives. Ask:
"For THIS task, who would argue about it at a company meeting?"
Pick 2 perspectives that catch what First Principles and AGI-Pilled miss.
Use "perspective", "analysis", "review", or "expert" in the Task description.

WHY 4 AGENTS?
- First Principles: "What can be deleted? What's over-engineered?"
- AGI-Pilled: "What would god-tier AI implementation look like?"
- Dynamic 1: Domain expertise — "What does [expert] see?"
- Dynamic 2: Adversarial review — "What could go wrong?"

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
    dynamic_agents_launched = lite_heavy.get("dynamic_agents_launched", 0)

    # If all requirements met, allow ExitPlanMode
    all_met = (
        heavy_skill_read
        and first_principles_launched
        and agi_pilled_launched
        and dynamic_agents_launched >= 2
    )
    if all_met:
        log_debug(
            "Lite Heavy requirements met (4 agents), allowing ExitPlanMode",
            hook_name="lite-heavy-enforcer"
        )
        sys.exit(0)

    # Block with specific feedback
    step1 = "✓" if heavy_skill_read else "✗"
    step2 = "✓" if first_principles_launched else "✗"
    step3 = "✓" if agi_pilled_launched else "✗"
    step4 = "✓" if dynamic_agents_launched >= 2 else "✗"

    message = BLOCK_MESSAGE.format(
        step1=step1, step2=step2, step3=step3, step4=step4,
        dynamic_count=dynamic_agents_launched
    )

    log_debug(
        "Blocking ExitPlanMode - Lite Heavy incomplete",
        hook_name="lite-heavy-enforcer",
        parsed_data={
            "heavy_skill_read": heavy_skill_read,
            "first_principles_launched": first_principles_launched,
            "agi_pilled_launched": agi_pilled_launched,
            "dynamic_agents_launched": dynamic_agents_launched,
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
