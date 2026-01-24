#!/usr/bin/env python3
"""
PostToolUse hook for ExitPlanMode - injects autonomous execution reminder.
"""
import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")

    if tool_name != "ExitPlanMode":
        sys.exit(0)

    # Output JSON with additionalContext
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": """
╔═══════════════════════════════════════════════════════════════════════════════╗
║  🚀 AUTONOMOUS EXECUTION MODE - CRITICAL REQUIREMENTS                         ║
╚═══════════════════════════════════════════════════════════════════════════════╝

You have exited plan mode. The following requirements are MANDATORY:

1. ITERATIVE EXECUTION UNTIL COMPLETE
   - Your task is to engage in an iterative loop until the goal is FULLY achieved
   - NO shortcuts. NO "next steps" left to pursue.
   - If something isn't working, debug and fix it - don't suggest the user do it

2. TEST AND VALIDATE EVERYTHING
   - Use /webtest to verify UI changes in browser
   - Test APIs by actually calling them
   - Log in and verify functionality works end-to-end
   - Don't assume it works - PROVE it works

3. PARALLELIZE WITH TASK AGENTS
   - Distribute work to Task agents whenever possible
   - Launch multiple agents in parallel for independent tasks
   - Validate subagent output - don't blindly trust it

4. NO PREMATURE STOPPING
   - Do NOT stop and say "next steps would be..."
   - Do NOT ask the user to test or verify - YOU do it
   - Do NOT stop at 70-80% complete and call it done

This is CRITICAL and VITALLY IMPORTANT to the successful completion of the plan.
The user trusted you to work AUTONOMOUSLY. Honor that trust.
"""
        }
    }

    print(json.dumps(output))
    sys.exit(0)

if __name__ == "__main__":
    main()
