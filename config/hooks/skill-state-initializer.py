#!/usr/bin/env python3
"""
UserPromptSubmit hook that creates state files for autonomous execution skills.

When the user's prompt matches appfix or godo triggers, this hook immediately
creates the appropriate state file BEFORE Claude starts processing. This ensures
the auto-approval hooks can detect autonomous mode from the very first tool call.

Hook event: UserPromptSubmit

Why this hook exists:
- Auto-approval hooks check for .claude/appfix-state.json or .claude/godo-state.json
- Without the state file, PermissionRequest hooks exit silently (no auto-approval)
- Previously, state file creation was an instruction in SKILL.md that Claude had
  to execute via Bash - but by then, EnterPlanMode's PermissionRequest had already fired
- This hook creates the file BEFORE Claude processes anything, fixing the race condition
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Trigger patterns for each skill
# These should match the triggers defined in the respective SKILL.md files
SKILL_TRIGGERS = {
    "appfix": [
        r"^/appfix\b",           # Slash command
        r"\bfix the app\b",      # Natural language
        r"\bdebug production\b",
        r"\bcheck staging\b",
        r"\bwhy is it broken\b",
        r"\bapp is broken\b",
        r"\bapp is down\b",
        r"\bapp crashed\b",
        r"\bproduction (is )?(down|broken|failing)\b",
        r"\bstaging (is )?(down|broken|failing)\b",
    ],
    "godo": [
        r"^/godo\b",             # Slash command
        r"\bgo do\b",            # Natural language
        r"\bjust do it\b",
        r"\bexecute this\b",
        r"\bmake it happen\b",
    ],
}


def detect_skill(prompt: str) -> str | None:
    """Detect which autonomous skill should be activated based on prompt.

    Returns 'appfix', 'godo', or None.
    """
    prompt_lower = prompt.lower().strip()

    for skill_name, patterns in SKILL_TRIGGERS.items():
        for pattern in patterns:
            if re.search(pattern, prompt_lower, re.IGNORECASE):
                return skill_name

    return None


def create_state_file(cwd: str, skill_name: str) -> bool:
    """Create the state file for the given skill.

    Creates both project-level (.claude/) and user-level (~/.claude/) state files.

    Returns True if successful.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    state_filename = f"{skill_name}-state.json"

    # Project-level state (in cwd/.claude/)
    project_state = {
        "iteration": 1,
        "started_at": now,
        "plan_mode_completed": False,
        "parallel_mode": False,
        "agent_id": None,
        "worktree_path": None,
        "coordinator": True,
        "services": {},
        "fixes_applied": [],
        "verification_evidence": None,
    }

    # Add skill-specific fields
    if skill_name == "godo":
        project_state["task"] = "Detected from user prompt"

    # User-level state (for cross-repo detection)
    user_state = {
        "started_at": now,
        "origin_project": cwd,
    }

    success = True

    # Create project-level state file
    try:
        project_claude_dir = Path(cwd) / ".claude"
        project_claude_dir.mkdir(parents=True, exist_ok=True)
        project_state_path = project_claude_dir / state_filename
        project_state_path.write_text(json.dumps(project_state, indent=2))
    except (OSError, IOError) as e:
        print(f"Warning: Failed to create project state file: {e}", file=sys.stderr)
        success = False

    # Create user-level state file
    try:
        user_claude_dir = Path.home() / ".claude"
        user_claude_dir.mkdir(parents=True, exist_ok=True)
        user_state_path = user_claude_dir / state_filename
        user_state_path.write_text(json.dumps(user_state, indent=2))
    except (OSError, IOError) as e:
        print(f"Warning: Failed to create user state file: {e}", file=sys.stderr)
        success = False

    return success


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)  # Non-blocking on error

    prompt = input_data.get("prompt", "")
    cwd = input_data.get("cwd", os.getcwd())

    if not prompt:
        sys.exit(0)

    # Detect if this prompt triggers an autonomous skill
    skill_name = detect_skill(prompt)

    if not skill_name:
        sys.exit(0)  # No autonomous skill detected

    # Create the state file
    success = create_state_file(cwd, skill_name)

    if success:
        # Output message (added to context for Claude)
        print(f"[skill-state-initializer] Autonomous mode activated: {skill_name}")
        print(f"State file created: .claude/{skill_name}-state.json")
        print("Auto-approval hooks are now active.")

    sys.exit(0)


if __name__ == "__main__":
    main()
