#!/usr/bin/env python3
"""
PostToolUse hook to track Lite Heavy progress for /forge and /burndown skills.

Tracks when:
1. heavy/SKILL.md is read
2. Task agents with "First Principles" or "AGI-Pilled" in description are launched
3. Dynamic Task agents are launched (general-purpose/opus with perspective/analysis/review/expert keywords)

Updates the active autonomous state file (forge-state.json or burndown-state.json)
with lite_heavy_verification status.

Hook event: PostToolUse
Matcher: Read, Task

Exit codes:
  0 - Always (non-blocking tracker)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Add hooks directory to path for shared imports
sys.path.insert(0, str(Path(__file__).parent))
from _common import get_autonomous_state, log_debug, _find_state_file_path


def is_heavy_skill_path(file_path: str) -> bool:
    """Check if the file path is heavy/SKILL.md."""
    if not file_path:
        return False
    return (
        file_path.endswith("heavy/SKILL.md") or
        "/skills/heavy/SKILL.md" in file_path or
        "skills/heavy/SKILL.md" in file_path
    )


def detect_agent_type(task_description: str, subagent_type: str = "", model: str = "") -> str | None:
    """Detect if the Task description indicates a Lite Heavy agent.

    Returns:
        "first_principles", "agi_pilled", "dynamic" (for task-specific perspectives),
        or None (for non-Lite-Heavy tasks like Explore agents).
    """
    if not task_description:
        return None

    desc_lower = task_description.lower()

    if "first principles" in desc_lower or "first-principles" in desc_lower:
        return "first_principles"

    if "agi-pilled" in desc_lower or "agi pilled" in desc_lower or "agipilled" in desc_lower:
        return "agi_pilled"

    # Dynamic agents: general-purpose opus Tasks that aren't FP or AGI-Pilled
    # These are the task-specific perspectives (e.g., "Security Engineer perspective")
    # Exclude Explore, Bash, Plan agents which are codebase exploration, not Lite Heavy
    non_dynamic_types = {"Explore", "Bash", "Plan", "claude-code-guide", "statusline-setup"}
    if subagent_type not in non_dynamic_types:
        if model == "opus" or subagent_type == "general-purpose":
            # Check for "perspective" or "analysis" keywords that indicate Lite Heavy agents
            if ("perspective" in desc_lower or "analysis" in desc_lower or
                    "review" in desc_lower or "expert" in desc_lower):
                return "dynamic"

    return None


def _find_lite_heavy_state_path(cwd: str) -> Path | None:
    """Find the active state file that supports Lite Heavy (forge or burndown)."""
    for filename in ("forge-state.json", "burndown-state.json"):
        path = _find_state_file_path(cwd, filename)
        if path:
            return path
    return None


def update_lite_heavy_state(cwd: str, updates: dict) -> bool:
    """Update the Lite Heavy verification state in the active state file.

    Supports both forge-state.json and burndown-state.json.
    Uses _find_state_file_path to locate the PID-scoped or legacy state file.
    """
    state_path = _find_lite_heavy_state_path(cwd)
    if not state_path:
        return False

    try:
        state = json.loads(state_path.read_text())

        if "lite_heavy_verification" not in state:
            state["lite_heavy_verification"] = {
                "heavy_skill_read": False,
                "first_principles_launched": False,
                "agi_pilled_launched": False,
                "dynamic_agents_launched": 0,
            }

        state["lite_heavy_verification"].update(updates)
        state_path.write_text(json.dumps(state, indent=2))
        return True
    except (json.JSONDecodeError, OSError) as e:
        log_debug(f"Failed to update lite heavy state: {e}", hook_name="lite-heavy-tracker")
        return False


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    cwd = input_data.get("cwd", "") or os.getcwd()
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    session_id = input_data.get("session_id", "")

    # Only process if forge or burndown is active (both use Lite Heavy planning)
    state, state_type = get_autonomous_state(cwd, session_id)
    if state_type not in ("forge", "burndown"):
        sys.exit(0)

    # Only track during first iteration
    iteration = state.get("iteration", 1)
    if iteration > 1:
        sys.exit(0)

    # Track Read of heavy/SKILL.md
    if tool_name == "Read":
        file_path = tool_input.get("file_path", "")
        if is_heavy_skill_path(file_path):
            update_lite_heavy_state(cwd, {"heavy_skill_read": True})
            log_debug("Tracked heavy/SKILL.md read", hook_name="lite-heavy-tracker")

    # Track Task agent launches
    elif tool_name == "Task":
        description = tool_input.get("description", "")
        subagent_type = tool_input.get("subagent_type", "")
        model = tool_input.get("model", "")
        agent_type = detect_agent_type(description, subagent_type, model)

        if agent_type == "first_principles":
            update_lite_heavy_state(cwd, {"first_principles_launched": True})
            log_debug("Tracked First Principles agent launch", hook_name="lite-heavy-tracker")
        elif agent_type == "agi_pilled":
            update_lite_heavy_state(cwd, {"agi_pilled_launched": True})
            log_debug("Tracked AGI-Pilled agent launch", hook_name="lite-heavy-tracker")
        elif agent_type == "dynamic":
            # Increment dynamic agent counter
            state_path = _find_lite_heavy_state_path(cwd)
            try:
                current_state = json.loads(state_path.read_text()) if state_path else {}
                lite_heavy = current_state.get("lite_heavy_verification", {})
                current_count = lite_heavy.get("dynamic_agents_launched", 0)
                update_lite_heavy_state(cwd, {"dynamic_agents_launched": current_count + 1})
                log_debug(
                    f"Tracked dynamic agent launch (now {current_count + 1})",
                    hook_name="lite-heavy-tracker",
                    parsed_data={"description": description}
                )
            except (json.JSONDecodeError, OSError) as e:
                log_debug(f"Failed to increment dynamic agent count: {e}", hook_name="lite-heavy-tracker")

    sys.exit(0)


if __name__ == "__main__":
    main()
