#!/usr/bin/env python3
"""
PostToolUse hook for ExitPlanMode - injects autonomous execution reminder
with completion checkpoint requirement.

Also handles appfix mode with enhanced autonomy context.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def is_appfix_active(cwd: str) -> bool:
    """Check if appfix is active via env var OR state file."""
    if os.environ.get("APPFIX_ACTIVE", "").lower() in ("true", "1", "yes"):
        return True
    if cwd:
        state_file = Path(cwd) / ".claude" / "appfix-state.json"
        if state_file.exists():
            return True
    return False


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    cwd = input_data.get("cwd", "")

    if tool_name != "ExitPlanMode":
        sys.exit(0)

    # Build checkpoint instructions (always included)
    checkpoint_instructions = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMPLETION CHECKPOINT REQUIRED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Before you can stop, you MUST fill out .claude/completion-checkpoint.json:

{
  "self_report": {
    "code_changes_made": true/false,
    "web_testing_done": true/false,
    "api_testing_done": true/false,
    "deployed": true/false,
    "console_errors_checked": true/false,
    "docs_updated": true/false,
    "is_job_complete": true/false
  },
  "reflection": {
    "what_was_done": "...",
    "what_remains": "none"  // Must be empty to allow stop
  },
  "evidence": {
    "urls_tested": ["https://..."],
    "console_clean": true/false
  }
}

The stop hook checks these booleans deterministically. Be honest.
If is_job_complete: false → BLOCKED.
If web_testing_done: false (for frontend changes) → BLOCKED.
If what_remains is not empty → BLOCKED.

DOCUMENTATION (docs_updated) - Update these when relevant:
- docs/TECHNICAL_OVERVIEW.md - Architectural changes
- Module docs in docs/ - Feature/API changes
- .claude/skills/*/references/ - Service topology, patterns
- .claude/MEMORIES.md - Significant learnings (not changelog)
"""

    if is_appfix_active(cwd):
        # Appfix mode - aggressive autonomous execution context
        context = f"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║  APPFIX AUTONOMOUS EXECUTION MODE - FIX-VERIFY LOOP ACTIVE                    ║
╚═══════════════════════════════════════════════════════════════════════════════╝

You are in an AUTOMATED FIX-VERIFY LOOP. The following is MANDATORY:

1. EXECUTE THE FIX IMMEDIATELY
   - Apply the code changes identified in your plan
   - Use Edit tool for targeted changes
   - Do NOT ask for confirmation

2. COMMIT AND PUSH CHANGES
   - After applying fixes, commit immediately:
     git add <files> && git commit -m "appfix: [brief description]"
     git push
   - Do NOT skip this step - changes must be committed before deploy

3. DEPLOY IF REQUIRED
   - If changes require deployment, trigger it now:
     gh workflow run deploy.yml -f environment=staging
     gh run watch --exit-status
   - If deploy fails, DO NOT proceed - diagnose the failure

4. VERIFY IN BROWSER
   - Run /webtest or use Chrome MCP to verify
   - Check browser console for errors
   - Data must actually display (not spinner/loading state)

5. UPDATE CHECKPOINT AND STATE
   - Update .claude/appfix-state.json with verification_evidence
   - Update .claude/completion-checkpoint.json with honest booleans

6. DO NOT:
   - Ask the user for permission
   - Suggest "next steps"
   - Stop before verification is complete
   - Skip the health check after fixing
{checkpoint_instructions}
CONTINUE THE FIX-VERIFY LOOP NOW.
"""
    else:
        # Standard autonomous execution context
        context = f"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║  AUTONOMOUS EXECUTION MODE - CRITICAL REQUIREMENTS                            ║
╚═══════════════════════════════════════════════════════════════════════════════╝

You have exited plan mode. The following requirements are MANDATORY:

1. ITERATIVE EXECUTION UNTIL COMPLETE
   - Your task is to engage in an iterative loop until the goal is FULLY achieved
   - NO shortcuts. NO "next steps" left to pursue.
   - If something isn't working, debug and fix it - don't suggest the user do it

2. TEST AND VALIDATE EVERYTHING
   - Use /webtest or Chrome MCP to verify UI changes in browser
   - Test APIs by actually calling them
   - Don't assume it works - PROVE it works

3. COMMIT AND DEPLOY
   - Commit changes: git add <files> && git commit -m "..."
   - Push to remote: git push
   - Deploy if required: gh workflow run deploy.yml && gh run watch --exit-status

4. NO PREMATURE STOPPING
   - Do NOT stop and say "next steps would be..."
   - Do NOT ask the user to test or verify - YOU do it
   - Do NOT stop at 70-80% complete and call it done
{checkpoint_instructions}
This is CRITICAL and VITALLY IMPORTANT to the successful completion of the plan.
The user trusted you to work AUTONOMOUSLY. Honor that trust.
"""

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": context
        }
    }

    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
